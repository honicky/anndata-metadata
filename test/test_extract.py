import pytest
import h5py
import numpy as np
import tempfile
import os

from anndata_metadata import extract

@pytest.fixture
def minimal_h5ad_file():
    # Create an in-memory HDF5 file with minimal AnnData structure
    with tempfile.NamedTemporaryFile(suffix=".h5ad", delete=False) as tmp:
        with h5py.File(tmp.name, "w") as f:
            # obs group with a dataset
            obs = f.create_group("obs")
            obs.create_dataset("cell_ids", data=np.array(["cell1", "cell2", "cell3"], dtype="S"))
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
    assert "file_size_gb" in info
    assert info["cell_count"] == 3
    assert info["gene_count"] == 2 