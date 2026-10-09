from paper_downloader.state import append_state, latest_state


def test_latest_state_uses_last_record(tmp_path):
    path = tmp_path / "state.jsonl"
    append_state(path, {"doi": "10.1109/x", "status": "failed"})
    append_state(path, {"doi": "10.1109/x", "status": "success"})
    assert latest_state(path)["10.1109/x"]["status"] == "success"
