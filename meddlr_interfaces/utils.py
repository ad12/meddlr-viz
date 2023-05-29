import torch
import h5py
from meddlr.utils import env
import pandas as pd
import meerkat as mk
from tqdm.auto import tqdm


def is_url(path):
    return (
        isinstance(path, str)
        and path.startswith("http://")
        or path.startswith("https://")
    )


def build_slice_df(paths, pbar: bool = False):
    """Build a dataframe containing the slices to visualize."""

    def _load_data(row):
        path = row["path"]
        sl = row["sl"]
        with h5py.File(path, "r") as f:
            kspace = torch.as_tensor(f["kspace"][sl])
            maps = torch.as_tensor(f["maps"][sl])
            target = torch.as_tensor(f["target"][sl]) if "target" in f else None
        out = {"kspace": kspace, "maps": maps, "target": target}

    pm = env.get_path_manager()

    records = []
    for path in tqdm(paths, disable=not pbar):
        path = pm.get_local_path(path)
        with h5py.File(path, "r") as f:
            num_slices = f["kspace"].shape[0]
        for sl in range(num_slices):
            records.append({"path": path, "sl": sl})

    df = pd.DataFrame.from_records(records)
    df = mk.DataFrame.from_pandas(df)
    df = mk.defer(df, _load_data)

    # Set formatters
    df["kspace"].formatters = TensorFormatterGroup().defer()
    df["maps"].formatters = TensorFormatterGroup().defer()
    df["target"].formatters = TensorFormatterGroup().defer()
    return df
