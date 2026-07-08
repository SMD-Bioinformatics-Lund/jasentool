"""Self-contained CDM input generation: parses the subset of JASEN pipeline
outputs needed for CDM (postalignqc, quast, gambitcore, chewbbaca) and
formats them into CDM input records. Independent of bonsai-libs/bonsai-prp.
"""

from importlib import import_module
from pathlib import Path

from .core.registry import get_parser, registered_softwares, registered_version_ranges, run_parser

# auto-import all modules under cdm/parsers to ensure that all parsers are registered
PARSER_DIR = "parsers"
_pkg_dir = Path(__file__).parent.joinpath(PARSER_DIR)
for file in _pkg_dir.glob("*.py"):
    if file.name not in ("__init__.py", "utils.py"):
        import_module(f"{__name__}.{PARSER_DIR}.{file.stem}")

__all__ = ["get_parser", "registered_softwares", "registered_version_ranges", "run_parser"]
