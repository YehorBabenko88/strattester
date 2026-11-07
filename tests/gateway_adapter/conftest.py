"""Expose this directory's test-only support under pytest package collection.

Stdlib discovery already adds its start directory. Pytest package collection
does not; both runners must exercise the same committed sibling support module.
"""
from pathlib import Path
import sys

directory=str(Path(__file__).resolve().parent)
if directory not in sys.path:
    sys.path.insert(0,directory)
