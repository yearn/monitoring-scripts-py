"""Structured logging module for monitoring scripts."""

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Return a pre-configured logger for the given protocol or module name."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
