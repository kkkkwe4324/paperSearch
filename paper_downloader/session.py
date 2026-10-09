from pathlib import Path


def cdp_endpoint(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def profile_path(data_dir: Path) -> Path:
    return data_dir / "browser-profile"


def open_context(playwright, data_dir: Path, *, headless: bool):
    return playwright.chromium.launch_persistent_context(
        str(profile_path(data_dir)),
        headless=headless,
        accept_downloads=True,
    )
