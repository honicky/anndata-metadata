import argparse
import os
import sys
import json
import pandas as pd
import s3fs
import logging

from src.anndata_metadata.extract import get_anndata_file_info, get_anndata_object_info

# Check if a given path is an S3 URI
def is_s3_path(path):
    return path.startswith("s3://")

# List .h5ad or extensionless files in an S3 directory
def list_s3_files(s3_uri):
    fs = s3fs.S3FileSystem(anon=False)
    if not s3_uri.endswith('/'):
        s3_uri += '/'
    bucket_prefix = s3_uri[5:]
    if '/' in bucket_prefix:
        bucket, prefix = bucket_prefix.split('/', 1)
    else:
        bucket, prefix = bucket_prefix, ''
    files = fs.ls(f"{bucket}/{prefix}")
    # Only return .h5ad or extensionless files
    return [
        f"s3://{file}" for file in files
        if file.endswith('.h5ad') or '.' not in os.path.basename(file)
    ]

# List .h5ad or extensionless files in a local directory
def list_local_files(directory):
    return [
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, f)) and (f.endswith('.h5ad') or '.' not in f)
    ]

def encode_obs_counts(info):
    if "obs_counts" in info and isinstance(info["obs_counts"], dict):
        info["obs_counts"] = {k: json.dumps(v) for k, v in info["obs_counts"].items()}
    return info

def process_files(files, info_func, obs_to_count, logger):
    results = []
    for f in files:
        logger.info(f"Processing {f}...")
        try:
            info = info_func(f, obs_to_count=obs_to_count)
            info['filename'] = f
            info = encode_obs_counts(info)
            results.append(info)
        except Exception as e:
            logger.error(f"Error processing {f}: {e}")
    return results

def write_output(results, output, logger):
    df = pd.DataFrame(results)
    if output == "-":
        logger.info(df.to_parquet(index=False))
    else:
        df.to_parquet(output, index=False)
        logger.info(f"Wrote output to {output}")

def write_single_output(info, output, logger):
    info = encode_obs_counts(info)
    if output == "-":
        logger.info(json.dumps(info, indent=2))
    else:
        with open(output, "w") as f:
            json.dump(info, f, indent=2)
        logger.info(f"Wrote output to {output}")

def main():
    # Set up logging with timestamps
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    logger = logging.getLogger(__name__)

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Extract AnnData metadata from file(s) or S3 object(s).")
    parser.add_argument("input_path", help="Input file, directory, S3 URI, or S3 directory URI")
    parser.add_argument("output", help="Output filename (JSON for single file, Parquet for directory, '-' for stdout)")
    parser.add_argument(
        "-o", "--obs",
        action="append",
        default=None,
        help="Observation column to count (can be specified multiple times)"
    )
    parser.add_argument(
        "-c", "--count",
        type=int,
        default=None,
        help="Maximum number of files to process (for directories/S3 directories)"
    )
    args = parser.parse_args()

    input_path = args.input_path
    output = args.output
    obs_to_count = args.obs  # This will be a list or None
    max_count = args.count

    # Decide S3 or local
    if is_s3_path(input_path):
        fs = s3fs.S3FileSystem(anon=False)
        is_dir = fs.isdir
        list_files = list_s3_files
        info_func = get_anndata_object_info
    else:
        is_dir = os.path.isdir
        list_files = list_local_files
        info_func = get_anndata_file_info

    # Directory or file
    if is_dir(input_path):
        files = list_files(input_path)
        if max_count is not None:
            files = files[:max_count]
        results = process_files(files, info_func, obs_to_count, logger)
        write_output(results, output, logger)
    else:
        info = info_func(input_path, obs_to_count=obs_to_count)
        write_single_output(info, output, logger)

if __name__ == "__main__":
    main()