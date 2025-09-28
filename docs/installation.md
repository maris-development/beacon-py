# Installation

To install the `beacon_api` package, you can use pip. Run the following command in your terminal:

```bash
pip install beacon_api
```

!!! warning "Upgrade pyarrow if using 19.0.0"
    
    If you are using pyarrow 19.0.0, please upgrade to at least 19.0.1 due to a known issue.
    ```bash
    pip install --upgrade pyarrow
    ```


Make sure you have Python 3.7 or higher installed on your system. You can check your Python version by running:

```bash
python --version
```

Some features of the `beacon_api` package may require additional dependencies. You can install these optional dependencies using:

GeoPandas support:

```bash
pip install beacon_api[geopandas]
```

Zarr support:

```bash
pip install beacon_api[zarr]
```

Query Profiling support:

```bash
pip install beacon_api[profiling]
```
