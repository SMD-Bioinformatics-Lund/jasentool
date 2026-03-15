"""Centralised logging configuration for jasentool"""
import logging

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def get_logger(name: str) -> logging.Logger:
    """Return a named logger for a jasentool module."""
    return logging.getLogger(name)

def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger — call once at program entry."""
    logging.basicConfig(format=LOG_FORMAT, datefmt=DATE_FORMAT, level=level)
