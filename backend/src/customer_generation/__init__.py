"""Customer generation contracts and deterministic sampling; no runtime model calls."""
from .sampling import generate_population
from .validation import ContractError, validate_intake, validate_evidence, validate_specification

__all__ = ["generate_population", "ContractError", "validate_intake", "validate_evidence", "validate_specification"]
