import argparse
import os
import sys
import json
import pandas as pd
import s3fs

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

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Extract AnnData metadata from file(s) or S3 object(s).")
    parser.add_argument("input_path", help="Input file, directory, S3 URI, or S3 directory URI")
    parser.add_argument("output", help="Output filename (JSON for single file, Parquet for directory, '-' for stdout)")
    args = parser.parse_args()

    input_path = args.input_path
    output = args.output

    # Handle S3 input paths
    if is_s3_path(input_path):
        fs = s3fs.S3FileSystem(anon=False)
        if fs.isdir(input_path):
            # If input is an S3 directory, process all valid files in it
            files = list_s3_files(input_path)
            results = []
            for f in files:
                try:
                    info = get_anndata_object_info(f)
                    info['filename'] = f
                    results.append(info)
                except Exception as e:
                    print(f"Error processing {f}: {e}", file=sys.stderr)
            df = pd.DataFrame(results)
            if output == "-":
                print(df.to_parquet(index=False))
            else:
                df.to_parquet(output, index=False)
        else:
            # If input is a single S3 file
            info = get_anndata_object_info(input_path)
            if output == "-":
                print(json.dumps(info, indent=2))
            else:
                with open(output, "w") as f:
                    json.dump(info, f, indent=2)
    else:
        # Handle local input paths
        if os.path.isdir(input_path):
            # If input is a local directory, process all valid files in it
            files = list_local_files(input_path)
            results = []
            for f in files:
                try:
                    info = get_anndata_file_info(f)
                    info['filename'] = f
                    results.append(info)
                except Exception as e:
                    print(f"Error processing {f}: {e}", file=sys.stderr)
            df = pd.DataFrame(results)
            if output == "-":
                print(df.to_parquet(index=False))
            else:
                df.to_parquet(output, index=False)
        else:
            # If input is a single local file
            info = get_anndata_file_info(input_path)
            if output == "-":
                print(json.dumps(info, indent=2))
            else:
                with open(output, "w") as f:
                    json.dump(info, f, indent=2)

if __name__ == "__main__":
    main()