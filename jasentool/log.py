"""Centralised logging configuration for jasentool"""
import logging

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """Return a named logger for a jasentool module."""
    return logging.getLogger(name)


def setup_logging(level: int = logging.INFO, log_file: str | None = None) -> None:
    """Configure root logger — call once at program entry.

    Always writes to stderr. If `log_file` is given, also appends formatted
    log records to that file (one handler each, both at `level`). The tqdm
    progress bar does not flow through the logger and therefore won't appear
    in the log file.
    """
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file, mode="a", encoding="utf-8"))
    logging.basicConfig(
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        level=level,
        handlers=handlers,
        force=True,
    )
