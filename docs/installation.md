# Installation

Install the published wheel straight from PyPI:

```bash
pip install beacon-api
```

!!! warning "Upgrade PyArrow if you are on 19.0.0"
    PyArrow 19.0.0 shipped with a known regression in the Parquet reader. The SDK already pins `pyarrow>=17.0.0,!=19.0.0`, but if you installed PyArrow separately make sure you are on ≥19.0.1.

## Requirements

- Python 3.10 or newer
- Internet access to reach your Beacon Node

Check your Python version with:

```bash
python --version
```

## What gets installed?

The default installation already brings along: `pandas`, `pyarrow`, `xarray`, `dask`, `fsspec`, `geopandas`, `zarr`, and `netCDF4`. That means features such as `to_geo_pandas_dataframe`, `to_zarr`, or `to_nd_netcdf` work out of the box—no optional extras required.



## Upgrading

```bash
pip install --upgrade beacon-api
```

You can combine this with [`pipx runpip`](https://pipx.pypa.io/stable/docs/#runpip) or environment managers (Conda, uv, Rye, …) if you prefer isolation.
