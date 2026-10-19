"""Dedup napříč případy: index obsahových hashů, politika šablon, znovupoužití hotové analýzy. Viz README.md."""
from .hashindex import HashIndexError, lookup, register

__all__ = ["lookup", "register", "HashIndexError"]
