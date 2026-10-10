import random
import re
import time
from pathlib import Path

from .files import is_valid_pdf
from .providers import normalize_doi, provider_for_doi
from .providers_runtime import AuthRequiredError, download_pdf
from .policy import RATE_LIMIT_COOLDOWNS, TRANSIENT_DELAYS, classify_failure
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
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", doi).replace("..", "_")
    return output_dir / (safe + ".pdf")


def should_skip(path: Path, *, resume: bool) -> bool:
    return resume and is_valid_pdf(path)


def download_batch(page, input_path: Path, output_dir: Path, state_path: Path, *, delay: float = 15.0, max_delay: float = 30.0, retry_count: int = 3, resume: bool = False, sleep=time.sleep, random_fn=random.uniform) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    dois = read_dois(input_path)
    counts = {"success": 0, "failed": 0, "skipped": 0, "auth_required": 0, "rate_limited": 0}
    for index, doi in enumerate(dois):
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
            except AuthRequiredError:
                append_state(state_path, {"doi": doi, "status": "auth_required", "error": "authentication required"})
                counts["auth_required"] += 1
                return counts
            except Exception as exc:
                category = classify_failure(getattr(exc, "status", None), str(exc))
                if category == "rate_limited":
                    append_state(state_path, {"doi": doi, "status": "rate_limited", "error": "provider rate limit"})
                    counts["rate_limited"] += 1
                    return counts
                if attempt == retry_count:
                    append_state(state_path, {"doi": doi, "status": "failed", "error": "transient download failure"})
                    counts["failed"] += 1
                else:
                    sleep(TRANSIENT_DELAYS[attempt - 1])
        if index < len(dois) - 1:
            sleep(random_fn(delay, max_delay))
    return counts
