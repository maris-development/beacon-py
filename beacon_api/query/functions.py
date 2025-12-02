from .select import *
import numpy as np
from numpy.typing import DTypeLike

# Ensure compatibility with Python 3.11+ for Self type
try:
    from typing import Optional
    from typing import List
    from typing import Union
    from typing import Tuple
except ImportError:
    from typing_extensions import Optional
    from typing_extensions import List
    from typing_extensions import Union
    from typing_extensions import Tuple


class Functions:
    @staticmethod
    def concat(args: List[Union[str, Select]], alias: str) -> SelectFunction:
        """
        Constructs a CONCAT function, concatenating the selected columns or arguments.
        Args:
            args (list[str  |  Select]): List of column names (str) or Select objects to concatenate.
            alias (str): Alias name for the resulting select expression.
        """
        
        select_args = []
        for arg in args:
            if isinstance(arg, str):
                select_args.append(SelectColumn(column=arg))
            elif isinstance(arg, Select):
                select_args.append(arg)
        return SelectFunction("concat", args=select_args, alias=alias)
    
    @staticmethod
    def coalesce(args: List[Union[str, Select]], alias: str) -> SelectFunction:
        """
        Constructs a COALESCE function, returning the first non-null value from the selected columns or arguments.
        Args:
            args (list[str  |  Select]): List of column names (str) or Select objects to coalesce.
            alias (str): Alias name for the resulting select expression.

        Returns:
            SelectFunction: SelectFunction representing the COALESCE operation.
        """
        select_args = []
        for arg in args:
            if isinstance(arg, str):
                select_args.append(SelectColumn(column=arg))
            elif isinstance(arg, Select):
                select_args.append(arg)
        return SelectFunction("coalesce", args=select_args, alias=alias)
    
    @staticmethod
    def try_cast_to_type(arg: Union[str, Select], to_type: DTypeLike, alias: str) -> SelectFunction:
            """
            Attempts to cast the input column or argument to the specified data type.
            Args:
                arg: Column name (str) or Select object to cast.
                to_type: Target data type (compatible with numpy dtype). Eg. np.int64, np.float64, np.datetime64, np.str_
                alias: Alias name for the resulting select expression.
            Returns:
                SelectFunction representing the cast operation.
            """
            dtype = np.dtype(to_type)  # normalize everything into a np.dtype
            arrow_type = None
            if np.issubdtype(dtype, np.integer):
                print("This is an integer dtype:", dtype)
                arrow_type = "Int64"
            elif np.issubdtype(dtype, np.floating):
                arrow_type = "Float64"
            elif np.issubdtype(dtype, np.datetime64):
                arrow_type = 'Timestamp(Nanosecond, None)'
            elif np.issubdtype(dtype, np.str_):
                arrow_type = 'Utf8'
            else:
                raise ValueError(f"Unsupported type for cast_to_type: {to_type}")
            
            if isinstance(arg, str):
                arg = SelectColumn(column=arg)
                return SelectFunction("try_arrow_cast", args=[arg, SelectLiteral(value=arrow_type)], alias=alias)
            elif isinstance(arg, Select):
                return SelectFunction("try_arrow_cast", args=[arg, SelectLiteral(value=arrow_type)], alias=alias)
        
    @staticmethod
    def cast_byte_to_char(arg: Union[str, Select], alias: str) -> SelectFunction:
        """Maps byte values to char.

        Args:
            arg (str | Select): column name (str) or Select object containing the byte value.
            alias (str): Alias name for the resulting select expression/column.

        Returns:
            SelectFunction: SelectFunction representing the cast operation.
        """
        if isinstance(arg, str):
            arg = SelectColumn(column=arg)
        return SelectFunction("cast_int8_as_char", args=[arg], alias=alias)

    @staticmethod
    def map_wod_quality_flag_to_sdn_scheme(arg: Union[str, Select], alias: str) -> SelectFunction:
        """Maps WOD quality flags to the SDN scheme.

        Args:
            arg (str | Select): column name (str) or Select object containing the WOD quality flag.
            alias (str): Alias name for the resulting select expression/column.

        Returns:
            SelectFunction: SelectFunction representing the mapping operation.
        """
        if isinstance(arg, str):
            arg = SelectColumn(column=arg)
        return SelectFunction("map_wod_quality_flag", args=[arg], alias=alias)

    @staticmethod
    def map_pressure_to_depth(arg: Union[str, Select], latitude_column: Union[str, Select], alias: str) -> SelectFunction:
        """Maps pressure values to depth based on latitude using teos-10.

        Args:
            arg (str | Select): column name (str) or Select object containing the pressure value.
            latitude_column (str | Select): column name (str) or Select object containing the latitude value.
            alias (str): Alias name for the resulting select expression/column.

        Returns:
            SelectFunction: SelectFunction representing the pressure-to-depth mapping operation.
        """
        if isinstance(arg, str):
            arg = SelectColumn(column=arg)
        if isinstance(latitude_column, str):
            latitude_column = SelectColumn(column=latitude_column)
        return SelectFunction("pressure_to_depth_teos_10", args=[arg, latitude_column], alias=alias)
