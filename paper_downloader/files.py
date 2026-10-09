from pathlib import Path


def is_valid_pdf(path: Path, minimum_bytes: int = 10_000) -> bool:
    try:
        with path.open("rb") as handle:
            return path.stat().st_size >= minimum_bytes and handle.read(5) == b"%PDF-"
    except OSError:
        return False
