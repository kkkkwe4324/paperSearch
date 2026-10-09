from pathlib import Path
import os


def cdp_endpoint(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def profile_path(data_dir: Path) -> Path:
    return data_dir / "browser-profile"


def _find_chrome() -> Path:
    candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ]
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    if local_app_data:
        candidates.append(local_app_data / "Google/Chrome/Application/chrome.exe")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("未找到本机 Google Chrome")


def chrome_command(data_dir: Path, port: int, *, chrome: str | None = None) -> list[str]:
    return [
        chrome or str(_find_chrome()),
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={profile_path(data_dir)}",
        "--no-first-run",
        "--no-default-browser-check",
        "about:blank",
    ]


def open_context(playwright, data_dir: Path, *, headless: bool):
    return playwright.chromium.launch_persistent_context(
        str(profile_path(data_dir)),
        headless=headless,
        accept_downloads=True,
    )
