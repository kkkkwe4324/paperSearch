from paper_downloader.session import cdp_endpoint, chrome_command, profile_path


def test_profile_path_is_app_specific(tmp_path):
    assert profile_path(tmp_path).name == "browser-profile"
    assert profile_path(tmp_path).parent == tmp_path


def test_cdp_endpoint_uses_local_port():
    assert cdp_endpoint(9333) == "http://127.0.0.1:9333"


def test_chrome_command_uses_shared_local_profile_and_loopback_cdp(tmp_path):
    command = chrome_command(tmp_path, 9333, chrome="chrome.exe")

    assert command[0] == "chrome.exe"
    assert "--remote-debugging-address=127.0.0.1" in command
    assert "--remote-debugging-port=9333" in command
    assert f"--user-data-dir={profile_path(tmp_path)}" in command
    assert not any("remote-allow-origins" in item for item in command)
