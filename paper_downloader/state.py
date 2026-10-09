import json
from pathlib import Path


def append_state(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def latest_state(path: Path) -> dict[str, dict]:
    result: dict[str, dict] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            if record.get("doi"):
                result[record["doi"]] = record
    return result
