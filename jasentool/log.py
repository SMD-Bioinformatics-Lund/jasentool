"""Centralised logging configuration for jasentool"""
import logging
import sys

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """Return a named logger for a jasentool module."""
    return logging.getLogger(name)


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger to write to stdout — call once per subcommand.

    Logs go to stdout (not stderr) so a plain `> log.txt` shell redirect
    captures them without needing `2>&1`. Trade-off: any subcommand that
    also prints data to stdout (e.g. `find`'s pprint dump) will share the
    stream with log records.
    """
    logging.basicConfig(
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        level=level,
        stream=sys.stdout,
        force=True,
    )
