"""MOO type constants and error codes for conformance tests."""

from enum import Enum, IntEnum


class MooError(str, Enum):
    """MOO error codes as strings (for YAML compatibility).

    These match the error names used in MOO code (E_TYPE, E_DIV, etc.)
    and can be used directly in YAML expect.error fields.
    """
    E_NONE = "E_NONE"
    E_TYPE = "E_TYPE"
    E_DIV = "E_DIV"
    E_PERM = "E_PERM"
    E_PROPNF = "E_PROPNF"
    E_VERBNF = "E_VERBNF"
    E_VARNF = "E_VARNF"
    E_INVIND = "E_INVIND"
    E_RECMOVE = "E_RECMOVE"
    E_MAXREC = "E_MAXREC"
    E_RANGE = "E_RANGE"
    E_ARGS = "E_ARGS"
    E_NACC = "E_NACC"
    E_INVARG = "E_INVARG"
    E_QUOTA = "E_QUOTA"
    E_FLOAT = "E_FLOAT"
    E_FILE = "E_FILE"
    E_EXEC = "E_EXEC"
    E_INTRPT = "E_INTRPT"


# Error code to numeric value mapping (matches MOO internals)
ERROR_CODES = {
    "E_NONE": 0,
    "E_TYPE": 1,
    "E_DIV": 2,
    "E_PERM": 3,
    "E_PROPNF": 4,
    "E_VERBNF": 5,
    "E_VARNF": 6,
    "E_INVIND": 7,
    "E_RECMOVE": 8,
    "E_MAXREC": 9,
    "E_RANGE": 10,
    "E_ARGS": 11,
    "E_NACC": 12,
    "E_INVARG": 13,
    "E_QUOTA": 14,
    "E_FLOAT": 15,
    "E_FILE": 16,
    "E_EXEC": 17,
    "E_INTRPT": 18,
}


class MooType(IntEnum):
    """MOO type codes (matches typeof() return values)."""
    TYPE_INT = 0
    TYPE_OBJ = 1
    TYPE_STR = 2
    TYPE_ERR = 3
    TYPE_LIST = 4
    TYPE_CLEAR = 5  # Internal
    TYPE_NONE = 6   # Internal
    TYPE_CATCH = 7  # Internal
    TYPE_FINALLY = 8  # Internal
    TYPE_FLOAT = 9
    TYPE_MAP = 10
    TYPE_ITER = 11  # Internal
    TYPE_ANON = 12
    TYPE_WAIF = 13
    TYPE_BOOL = 14


# Type name mapping for YAML
TYPE_NAMES = {
    "int": MooType.TYPE_INT,
    "obj": MooType.TYPE_OBJ,
    "str": MooType.TYPE_STR,
    "err": MooType.TYPE_ERR,
    "list": MooType.TYPE_LIST,
    "float": MooType.TYPE_FLOAT,
    "map": MooType.TYPE_MAP,
    "anon": MooType.TYPE_ANON,
    "waif": MooType.TYPE_WAIF,
    "bool": MooType.TYPE_BOOL,
}


# Special object constants
NOTHING = -1
AMBIGUOUS_MATCH = -2
FAILED_MATCH = -3


def is_error_value(value) -> bool:
    """Check if a value represents a MOO error."""
    if isinstance(value, str) and value.startswith("E_"):
        return value in ERROR_CODES
    return False


def parse_error(value: str) -> MooError | None:
    """Parse an error string to MooError enum."""
    if isinstance(value, str) and value.startswith("E_"):
        try:
            return MooError(value)
        except ValueError:
            return None
    return None
