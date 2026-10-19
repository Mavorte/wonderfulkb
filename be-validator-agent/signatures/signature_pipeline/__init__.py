"""Signature pipeline: detection, role from nearest text, crop, perceptual hash, copy suspicion.

Output matches the `Signature` schema of be-document-processing/contracts/openapi-validator-agent.yaml (call 3).
It states presence, assigned role and suspicion of copying. It never verifies authenticity.
"""
from .interface import detect_signatures
from .models import Detection, Signature, TextLine
from .pipeline import process_case, process_pdf

__all__ = ["Detection", "Signature", "TextLine", "detect_signatures", "process_case", "process_pdf"]
