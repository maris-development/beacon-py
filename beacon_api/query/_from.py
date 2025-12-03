from dataclasses import dataclass
from .node import QueryNode

class From(QueryNode):
    pass

class DatasetFormat(QueryNode):
    pass

@dataclass
class FromTable(From):
    table: str

    def to_dict(self) -> dict:
        return {"from": self.table}

@dataclass
class FromBBFDataset(From):
    paths: list[str]
    
    def to_dict(self) -> dict:
        return {
            "from": {
                "bbf": {
                    "paths": self.paths
                }
            }
        }

@dataclass
class FromParquetDataset(From):
    paths: list[str]
    
    def to_dict(self) -> dict:
        return {
            "from": {
                "parquet": {
                    "paths": self.paths
                }
            }
        }
    
@dataclass
class FromArrowDataset(From):
    paths: list[str]
    
    def to_dict(self) -> dict:
        return {
            "from": {
                "arrow": {
                    "paths": self.paths
                }
            }
        }
        
@dataclass
class FromNetCDFDataset(From):
    paths: list[str]
    
    def to_dict(self) -> dict:
        return {
            "from": {
                "netcdf": {
                    "paths": self.paths
                }
            }
        }
        
@dataclass
class FromCSVDataset(From):
    paths: list[str]
    delimiter: str = ','
    
    def to_dict(self) -> dict:
        return {
                "from": {
                    "csv": {
                        "paths": self.paths,
                        "delimiter": self.delimiter,
                    }
                }
            }

@dataclass
class FromZarrDataset(From):
    paths: list[str]
    statistics_columns: list[str] | None = None
    
    def to_dict(self) -> dict:
        return {
                "from": {
                    "zarr": {
                        "paths": self.paths,
                        "statistics_columns": self.statistics_columns,
                    }
                }
            } 
            