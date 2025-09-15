from .session import BaseBeaconSession
from .query import Query

class Dataset:
    def __init__(self, http_session: BaseBeaconSession, file_path: str):
        self.session = http_session
        self.file_path = file_path

    def get_file_path(self) -> str:
        """Get the file path of the dataset"""
        return self.file_path
    
    def get_file_name(self) -> str:
        """Get the file name of the dataset"""
        return self.file_path.split("/")[-1]

    def get_file_extension(self) -> str:
        """Get the file extension of the dataset"""
        return self.file_path.split(".")[-1]
    
    def __str__(self) -> str:
        return self.file_path

    def __repr__(self) -> str:
        return f"Dataset(file_path={self.file_path})"

    def query(self) -> Query:
        """Create a new query object for this dataset.
        
        Returns:
            Query: A new query object.
        """
        return Query(http_session=self.session, from_file_path=self.file_path)