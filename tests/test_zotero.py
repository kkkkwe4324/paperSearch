import pytest

from paper_downloader.zotero import ZoteroClient, ZoteroError


COLLECTIONS = [
    {"data": {"key": "ROOT1234", "name": "10投机解码", "parentCollection": False}},
    {"data": {"key": "CHILD123", "name": "05.7 边云协同投机解码", "parentCollection": "ROOT1234"}},
    {"data": {"key": "OTHER123", "name": "06 卫星计算与网络", "parentCollection": False}},
]
ITEM = {"data": {"key": "PAPER123", "version": 7, "title": "A Paper", "DOI": "10.1145/example.1", "itemType": "journalArticle", "collections": ["OTHER123"]}}


class FakeTransport:
    def __init__(self):
        self.item = {"data": dict(ITEM["data"])}
        self.calls = []
        self.denied = False
        self.conflict = False

    def __call__(self, method, path, payload=None, headers=None):
        self.calls.append((method, path, payload, headers or {}))
        if path == "":
            return None, {"Zotero-Server-ID": "SERVER123"}
        if path == "users/0/collections":
            return COLLECTIONS, {}
        if path == "users/0/items":
            return self.item if isinstance(self.item, list) else [self.item], {}
        if path == "users/0/items/PAPER123" and method == "GET":
            return self.item, {}
        if path == "local/authorize":
            if self.denied:
                raise ZoteroError("authorization denied", status=403)
            return {"key": "secret-local-key"}, {}
        if path == "users/0/items/PAPER123" and method == "PATCH":
            if self.conflict:
                raise ZoteroError("version conflict", status=412)
            self.item = {"data": {**self.item["data"], "version": 8, "collections": payload["collections"]}}
            return None, {}
        raise AssertionError((method, path))


def test_live_parentage_overrides_misleading_numeric_prefix():
    client = ZoteroClient(transport=FakeTransport())
    assert client.collection_paths()["CHILD123"] == "10投机解码 / 05.7 边云协同投机解码"


def test_match_uses_exact_doi_and_rejects_duplicates():
    transport = FakeTransport()
    client = ZoteroClient(transport=transport)
    assert client.match_item(doi="https://doi.org/10.1145/EXAMPLE.1")["key"] == "PAPER123"
    assert client.match_item(doi="10.1145/example.2") is None
    transport.item = [ITEM, {"data": {**ITEM["data"], "key": "SECOND12"}}]
    with pytest.raises(ZoteroError, match="ambiguous"):
        client.match_item(doi="10.1145/example.1")


def test_plan_adds_parent_and_apply_preserves_existing_membership():
    transport = FakeTransport()
    client = ZoteroClient(transport=transport)
    plan = client.make_plan("PAPER123", ["CHILD123"], "cross-cloud SD method")
    assert set(plan["add_collections"]) == {"ROOT1234", "CHILD123"}
    assert "secret" not in str(plan)
    result = client.apply_plan(plan)
    assert set(result["collections"]) == {"OTHER123", "ROOT1234", "CHILD123"}
    patch = next(call for call in transport.calls if call[0] == "PATCH")
    assert set(patch[2]["collections"]) == {"OTHER123", "ROOT1234", "CHILD123"}
    assert patch[3]["If-Unmodified-Since-Version"] == "7"
    assert patch[3]["Zotero-API-Key"] == "secret-local-key"


def test_apply_skips_write_when_item_is_already_in_target_collections():
    transport = FakeTransport()
    transport.item["data"]["collections"] = ["OTHER123", "ROOT1234", "CHILD123"]
    client = ZoteroClient(transport=transport)
    plan = client.make_plan("PAPER123", ["CHILD123"], "already routed")
    result = client.apply_plan(plan)
    assert "CHILD123" in result["collections"]
    assert not any(call[0] in ("POST", "PATCH") for call in transport.calls)


@pytest.mark.parametrize("change", ["stale", "denied", "conflict"])
def test_apply_stops_on_stale_or_denied_write(change):
    transport = FakeTransport()
    client = ZoteroClient(transport=transport)
    plan = client.make_plan("PAPER123", ["CHILD123"], "reason")
    if change == "stale":
        transport.item["data"]["version"] = 8
    elif change == "denied":
        transport.denied = True
    else:
        transport.conflict = True
    with pytest.raises(ZoteroError):
        client.apply_plan(plan)
    if change == "stale":
        assert not any(call[0] == "PATCH" for call in transport.calls)
