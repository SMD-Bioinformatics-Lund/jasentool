import re
from pathlib import Path

from jasentool.database import Database

PACKAGE = Path(__file__).parent.parent / "jasentool"
MONGO_WRITES = re.compile(
    r"\.(insert_one|insert_many|update_one|update_many|replace_one|delete_one|delete_many"
    r"|find_one_and_\w+|bulk_write|create_index|create_indexes|drop_collection|drop_database"
    r"|drop_index|drop_indexes|rename_collection|aggregate)\("
)


def test_no_mongodb_write_calls_in_jasentool():
    hits = [
        f"{path.relative_to(PACKAGE.parent)}:{lineno}: {line.strip()}"
        for path in sorted(PACKAGE.rglob("*.py"))
        for lineno, line in enumerate(path.read_text().splitlines(), start=1)
        if MONGO_WRITES.search(line)
    ]
    assert hits == []


def test_database_only_exposes_reads():
    public = {name for name in vars(Database) if not name.startswith("_")}
    assert public == {"uri", "db", "initialize", "find", "find_one",
                      "get_pvl", "get_mlst", "get_cgmlst", "get_meta_fields"}
