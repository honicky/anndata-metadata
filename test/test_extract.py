import pytest
import h5py
import numpy as np
import tempfile
import os
import json

from anndata_metadata import extract


@pytest.fixture
def minimal_h5ad_file():
  # Create an in-memory HDF5 file with minimal AnnData structure
  with tempfile.NamedTemporaryFile(suffix=".h5ad", delete=False) as tmp:
    with h5py.File(tmp.name, "w") as f:
      # obs group with a dataset
      obs = f.create_group("obs")
      obs.create_dataset(
        "cell_ids", data=np.array(["cell1", "cell2", "cell3"], dtype="S"))
      # var group with a dataset
      var = f.create_group("var")
      var.create_dataset("feature_name", data=np.array(["geneA", "geneB"], dtype="S"))
      # X group with sparse matrix components
      X = f.create_group("X")
      X.create_dataset("data", data=np.array([1, 2, 3]))
      X.create_dataset("indices", data=np.array([0, 1, 2]))
      X.create_dataset("indptr", data=np.array([0, 1, 2, 3]))
      X.attrs["format"] = np.bytes_("csr")
      # obsm, obsp, layers groups
      f.create_group("obsm")
      f.create_group("obsp")
      f.create_group("layers")
    yield tmp.name
    os.remove(tmp.name)


def test_get_cell_count(minimal_h5ad_file):
  with h5py.File(minimal_h5ad_file, "r") as f:
    count = extract.get_cell_count(f)
    assert count == 3


def test_get_gene_count(minimal_h5ad_file):
  with h5py.File(minimal_h5ad_file, "r") as f:
    count = extract.get_gene_count(f)
    assert count == 2


def test_get_sparse_matrix_format(minimal_h5ad_file):
  with h5py.File(minimal_h5ad_file, "r") as f:
    fmt = extract.get_sparse_matrix_format(f)
    assert fmt == "CSR"


def test_get_anndata_file_info_dict(minimal_h5ad_file):
  with h5py.File(minimal_h5ad_file, "r") as f:
    info = extract.get_anndata_info(f)
    assert info["cell_count"] == 3
    assert info["gene_count"] == 2
    assert "main_groups" in info
    assert "x_storage" in info
    assert info["x_storage"]["format"] == "CSR"


def test_get_anndata_file_info_path(minimal_h5ad_file):
  info = extract.get_anndata_file_info(minimal_h5ad_file)
  assert "file_size" in info
  assert info["cell_count"] == 3
  assert info["gene_count"] == 2


def test_get_obs_counts_categorical():
  # Create a temporary HDF5 file with a categorical obs group
  with tempfile.NamedTemporaryFile(suffix=".h5ad") as tmp:
    with h5py.File(tmp.name, "w") as f:
      obs = f.create_group("obs")
      cat = obs.create_group("cell_type")
      cat.create_dataset("categories", data=np.array(["A", "B", "C"], dtype="S"))
      cat.create_dataset("codes", data=np.array([0, 1, 0, 2, 1, 1, 2]))
    with h5py.File(tmp.name, "r") as f:
      counts = extract.get_obs_counts(f, "cell_type")
      # Convert keys to str for comparison (since categories are bytes)
      counts = {str(k): int(v) for k, v in counts.items()}
      assert counts == {"A": 2, "B": 3, "C": 2}


def test_get_obs_counts_dataset():
  # Create a temporary HDF5 file with a non-categorical obs dataset
  with tempfile.NamedTemporaryFile(suffix=".h5ad") as tmp:
    with h5py.File(tmp.name, "w") as f:
      obs = f.create_group("obs")
      obs.create_dataset(
        "batch", data=np.array(["x", "y", "x", "z", "y", "y", "z"], dtype="S"))
    with h5py.File(tmp.name, "r") as f:
      counts = extract.get_obs_counts(f, "batch")
      # Convert keys to str for comparison (since values are bytes)
      counts = {str(k): int(v) for k, v in counts.items()}
      assert counts == {"x": 2, "y": 3, "z": 2}


def test_get_obs_counts_missing_key():
  # Create a temporary HDF5 file with no such obs key
  with tempfile.NamedTemporaryFile(suffix=".h5ad") as tmp:
    with h5py.File(tmp.name, "w") as f:
      obs = f.create_group("obs")
      obs.create_dataset("foo", data=np.array([1, 2, 3]))
    with h5py.File(tmp.name, "r") as f:
      counts = extract.get_obs_counts(f, "bar")
      assert counts == {}


def test_obs_counts_json_string_dict(minimal_h5ad_file):
  with h5py.File(minimal_h5ad_file, "a") as f:
    cat = f["obs"].create_group("cell_type")
    cat.create_dataset("categories", data=np.array(["A", "B"], dtype="S"))
    cat.create_dataset("codes", data=np.array([0, 1, 0, 1, 1]))
    f["obs"].create_dataset(
      "batch", data=np.array(["x", "y", "x", "z", "y"], dtype="S"))

  info = extract.get_anndata_file_info(
    minimal_h5ad_file, obs_to_count=["cell_type", "batch"])

  # Simulate the CLI/Parquet conversion
  obs_counts = {k: json.dumps(v) for k, v in info["obs_counts"].items()}

  assert set(obs_counts.keys()) == {"cell_type", "batch"}
  cell_type_counts = json.loads(obs_counts["cell_type"])
  batch_counts = json.loads(obs_counts["batch"])
  assert cell_type_counts == {"A": 2, "B": 3}
  assert batch_counts == {"x": 2, "y": 2, "z": 1}
