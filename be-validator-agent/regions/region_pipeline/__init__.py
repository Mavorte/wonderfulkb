"""Regiony dokumentu: odstavce s polohou a textem (viz be-validator-agent/docs/regiony-dokumentu-navrh.md)."""
from .segment import document_regions, regions_for_pdf, segment_page

__all__ = ["document_regions", "regions_for_pdf", "segment_page"]
