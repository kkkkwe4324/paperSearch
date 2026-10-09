from paper_downloader.session import cdp_endpoint, profile_path


def test_profile_path_is_app_specific(tmp_path):
    assert profile_path(tmp_path).name == "browser-profile"
    assert profile_path(tmp_path).parent == tmp_path


def test_cdp_endpoint_uses_local_port():
    assert cdp_endpoint(9333) == "http://127.0.0.1:9333"
