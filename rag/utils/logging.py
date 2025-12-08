"""
RAG Logging
============

Logging utilities for RAG module.
"""

import logging


def get_logger(name: str) -> logging.Logger:
    """Get a logger for RAG module."""
    logger = logging.getLogger(f"symbolu.rag.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
