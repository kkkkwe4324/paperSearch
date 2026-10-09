import time
from pathlib import Path

from .files import is_valid_pdf
from .providers import normalize_doi, provider_for_doi
from .providers_runtime import AuthRequiredError, download_pdf
from .state import append_state


def read_dois(path: Path) -> list[str]:
    result = []
    seen = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            doi = normalize_doi(line)
        except ValueError:
            continue
        if doi.lower() not in seen:
            result.append(doi)
            seen.add(doi.lower())
    return result


def output_path(output_dir: Path, doi: str) -> Path:
    return output_dir / (doi.replace("/", "_") + ".pdf")


def should_skip(path: Path, *, resume: bool) -> bool:
    return resume and is_valid_pdf(path)


def download_batch(page, input_path: Path, output_dir: Path, state_path: Path, *, delay: float = 6.0, retry_count: int = 3, resume: bool = False) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = {"success": 0, "failed": 0, "skipped": 0, "auth_required": 0}
    for index, doi in enumerate(read_dois(input_path)):
        target = output_path(output_dir, doi)
        if should_skip(target, resume=resume):
            counts["skipped"] += 1
            continue
        if provider_for_doi(doi) not in {"ieee", "acm"}:
            append_state(state_path, {"doi": doi, "status": "failed", "error": "Unsupported provider"})
            counts["failed"] += 1
            continue
        for attempt in range(1, retry_count + 1):
            try:
                size = download_pdf(page, doi, target)
                append_state(state_path, {"doi": doi, "status": "success", "bytes": size})
                counts["success"] += 1
                break
            except AuthRequiredError as exc:
                append_state(state_path, {"doi": doi, "status": "auth_required", "error": str(exc)})
                counts["auth_required"] += 1
                return counts
            except Exception as exc:
                if attempt == retry_count:
                    append_state(state_path, {"doi": doi, "status": "failed", "error": str(exc)})
                    counts["failed"] += 1
                else:
                    time.sleep(2 ** (attempt - 1))
        if index < len(read_dois(input_path)) - 1:
            time.sleep(delay)
    return counts
