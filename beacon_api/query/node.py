from dataclasses import asdict, dataclass

@dataclass
class QueryNode:
    def to_dict(self) -> dict:
        # asdict(self) walks nested dataclasses too
        return asdict(self)
