import h5py
import s3fs
from typing import Any
import os
import numpy as np


def get_anndata_file_info(file_path: str) -> dict[str, Any]:
  """
    Extract metadata information from an H5AD file and return it as a dictionary.
    """

  info = {'file_size': int(os.path.getsize(file_path)) }

  with h5py.File(file_path, 'r') as f:
    info.update(get_anndata_info(f))

  # Get file size
  return info


def get_anndata_object_info(s3_uri: str) -> dict[str, Any]:
  """
    Extract metadata information from a H5AD object in S3 and return it as a dictionary.
    """
  fs = s3fs.S3FileSystem(anon=False)
  info = {'file_size': int(fs.info(s3_uri)['size']) }

  with fs.open(s3_uri, 'rb') as f:
    with h5py.File(f, 'r') as h5file:
      info.update(get_anndata_info(h5file))

  return info


def get_anndata_info(f: h5py.File) -> dict[str, Any]:
  """
    Extracts key metadata from an AnnData H5AD file object.

    Parameters
    ----------
    f : h5py.File
        An open H5AD file object.
   
    Returns
    -------
    dict[str, Any]
        A dictionary containing:
            - main_groups: List of top-level groups in the file.
            - cell_count: Number of cells (observations).
            - gene_count: Number of genes (variables).
            - obs_contents: List of keys in the 'obs' group.
            - var_contents: List of keys in the 'var' group.
            - x_storage: Dictionary with details about the 'X' matrix, including:
                - components: List of keys in 'X'.
                - format: Sparse matrix format (CSR, CSC, COO, Dense, or Unknown).
                - chunk_size: Chunk size of the 'data' dataset, if available.
            - embeddings: List of keys in the 'obsm' group (cell embeddings).
            - pairwise_relationships: List of keys in the 'obsp' group (pairwise relationships).
            - expression_layers: List of keys in the 'layers' group (expression layers).

    Notes
    -----
    This function is intended to be called with an open h5py.File object representing an AnnData H5AD file.
    It is used internally by file and S3 metadata extraction functions.
    """

  info = {
    "main_groups": list(f.keys()),
    'cell_count': get_cell_count(f),
    'gene_count': get_gene_count(f),
    'obs_contents': list(f['obs'].keys()),
    'var_contents': list(f['var'].keys()),
    'x_storage': {
      'components':
        list(f['X'].keys()),
      'format':
        get_sparse_matrix_format(f),
      'chunk_size': (
        tuple(int(x) for x in f['X']['data'].chunks)
        if hasattr(f['X']['data'], 'chunks') and f['X']['data'].chunks is not None
        else None
      )
    },
    'embeddings': list(f['obsm'].keys()) if 'obsm' in f else [],
    'pairwise_relationships': list(f['obsp'].keys()) if 'obsp' in f else [],
    'expression_layers': list(f['layers'].keys()) if 'layers' in f else []
  }

  return _convert_to_python_types(info)


def get_cell_count(f: h5py.File) -> int:
  """
    Get the number of cells in the dataset by checking the first
    entry in the 'obs' group. If it is a h5py.Group, it is assumed
    to be a categorical variable, in which case it will have a 'codes'
    sub-variable with the number of cells as the first dimension.
  """

  first_obs_key = next(iter(f['obs'].keys()))
  first_obs_entry = f['obs'][first_obs_key]

  if isinstance(first_obs_entry, h5py.Group) and 'codes' in first_obs_entry:
    return first_obs_entry['codes'].shape[0]
  else:
    return len(first_obs_entry)


def get_gene_count(f: h5py.File) -> int:
  """
    Get the number of genes in the dataset by checking the first
    entry in the 'var' group. If it is a h5py.Group, it is assumed
    to be a categorical variable, in which case it will have a 'codes'
    sub-variable with the number of genes as the first dimension.
  """

  n_var = None

  if 'feature_name' in f['var']:
    feature_name = f['var']['feature_name']
    if isinstance(feature_name, h5py.Group) and 'categories' in feature_name:
      n_var = feature_name['categories'].shape[0]
    elif isinstance(feature_name, h5py.Dataset):
      n_var = feature_name.shape[0]
  elif '_index' in f['var']:
    _index = f['var']['_index']
    if isinstance(_index, h5py.Group) and 'categories' in _index:
      n_var = _index['categories'].shape[0]
    elif isinstance(_index, h5py.Dataset):
      n_var = _index.shape[0]

  return n_var


def get_sparse_matrix_format(f: h5py.File) -> str:
  """
    Get the format of the sparse matrix in the dataset.
  """

  x_components = list(f['X'].keys())

  if all(comp in x_components for comp in ['data', 'indices', 'indptr']):
    format_type = 'CSR'
    if 'format' in f['X'].attrs:
      stored_format = f['X'].attrs['format']
      if isinstance(stored_format, bytes):
        stored_format = stored_format.decode('utf-8')
      format_type = stored_format.upper()
    else:
      if 'shape' in f['X'].attrs:
        matrix_shape = f['X'].attrs['shape']
        n_rows = len(f['X']['indptr']) - 1
        if n_rows == matrix_shape[1]:
          format_type = 'CSC'
  elif all(comp in x_components for comp in ['data', 'row', 'col']):
    format_type = 'COO'
  else:
    format_type = 'Dense' if 'data' in x_components else 'Unknown'

  return format_type


def _convert_to_python_types(obj: Any) -> Any:
  """
    Convert numpy types to native Python types for JSON serialization.
    """
  if isinstance(obj, np.integer):
    return int(obj)
  elif isinstance(obj, np.floating):
    return float(obj)
  elif isinstance(obj, np.ndarray):
    return obj.tolist()
  elif isinstance(obj, dict):
    return {key: _convert_to_python_types(value) for key, value in obj.items()}
  elif isinstance(obj, (list, tuple)):
    return [_convert_to_python_types(item) for item in obj]
  return obj
