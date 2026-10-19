import os
import sys

EVAL = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if EVAL not in sys.path:
    sys.path.insert(0, EVAL)
