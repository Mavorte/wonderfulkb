"""Klasifikace dokumentu: model vrací štítek, popis a jistotu; pravidla jen potvrzují.

Použití: `from classify import classify_document`. Pro vizuální přepis viz `classify.prompt`.
"""
from .classifier import classify_document, classify_document_detailed
from .prompt import LABEL_OUTPUT_SCHEMA, build_label_prompt_section, parse_label_output
from .rules import load_taxonomy

__all__ = ["classify_document", "classify_document_detailed", "load_taxonomy",
           "build_label_prompt_section", "LABEL_OUTPUT_SCHEMA", "parse_label_output"]
