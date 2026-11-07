"""Safe topic routing through Zotero's official local API."""

import json
import re
import urllib.error
import urllib.request


class ZoteroError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _normalize_doi(value: str) -> str:
    return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value.strip(), flags=re.I).casefold()


def _normalize_title(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold()))


class ZoteroClient:
    def __init__(self, transport=None):
        self.transport = transport or self._http

    @staticmethod
    def _http(method, path, payload=None, headers=None):
        url = "http://127.0.0.1:23119/api/" + path
        request_headers = {"User-Agent": "paper-downloader/0.1", **(headers or {})}
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request, timeout=10) as response:
                raw = response.read()
                data = json.loads(raw) if raw.strip().startswith((b"{", b"[")) else None
                return data, dict(response.headers)
        except urllib.error.HTTPError as exc:
            message = {401: "Zotero write authorization failed", 403: "Zotero local API is disabled or write access was denied", 409: "Zotero library is locked", 412: "Zotero item changed; make a new plan"}.get(exc.code, f"Zotero API returned HTTP {exc.code}")
            raise ZoteroError(message, status=exc.code) from exc
        except urllib.error.URLError as exc:
            raise ZoteroError("Zotero local API is unavailable; open Zotero and enable local API access") from exc

    def server_id(self) -> str:
        _, headers = self.transport("GET", "")
        server_id = next((value for key, value in headers.items() if key.lower() == "zotero-server-id"), None)
        if not server_id:
            raise ZoteroError("Zotero local API did not provide a server ID")
        return server_id

    def list_collections(self) -> list[dict]:
        data, _ = self.transport("GET", "users/0/collections")
        return [entry["data"] for entry in data]

    def collection_paths(self) -> dict[str, str]:
        by_key = {entry["key"]: entry for entry in self.list_collections()}
        result = {}

        def path(key, seen):
            if key in result:
                return result[key]
            if key in seen or key not in by_key:
                raise ZoteroError(f"invalid Zotero collection parentage at {key}")
            entry = by_key[key]
            parent = entry.get("parentCollection")
            result[key] = (path(parent, seen | {key}) + " / " if parent else "") + entry["name"]
            return result[key]

        for key in by_key:
            path(key, set())
        return result

    def get_item(self, key: str) -> dict:
        item, _ = self.transport("GET", f"users/0/items/{key}")
        return item["data"]

    def match_item(self, *, doi: str | None = None, title: str | None = None) -> dict | None:
        if not doi and not title:
            raise ValueError("provide a verified DOI or title")
        rows, _ = self.transport("GET", "users/0/items")
        items = [entry["data"] for entry in rows if entry["data"].get("itemType") not in ("attachment", "note")]
        matches = [item for item in items if doi and _normalize_doi(item.get("DOI", "")) == _normalize_doi(doi)]
        if not matches and title:
            matches = [item for item in items if _normalize_title(item.get("title", "")) == _normalize_title(title)]
        if len(matches) > 1:
            raise ZoteroError("ambiguous Zotero match; review duplicate items or paper versions")
        return matches[0] if matches else None

    def make_plan(self, item_key: str, target_keys: list[str], reason: str) -> dict:
        if not reason.strip() or not target_keys:
            raise ValueError("a target collection and evidence-based reason are required")
        collections = {entry["key"]: entry for entry in self.list_collections()}
        paths = self.collection_paths()
        proposed = set()
        for key in target_keys:
            if key not in collections:
                raise ZoteroError(f"unknown Zotero collection key: {key}")
            while key:
                proposed.add(key)
                key = collections[key].get("parentCollection") or None
        item = self.get_item(item_key)
        return {
            "schema": 1,
            "server_id": self.server_id(),
            "item_key": item_key,
            "item_version": item["version"],
            "title": item.get("title", ""),
            "doi": item.get("DOI", ""),
            "existing_collections": item.get("collections", []),
            "add_collections": sorted(proposed),
            "collection_paths": {key: paths[key] for key in proposed},
            "reason": reason.strip(),
        }

    def apply_plan(self, plan: dict) -> dict:
        if plan.get("schema") != 1 or not plan.get("reason"):
            raise ZoteroError("invalid Zotero routing plan")
        server_id = self.server_id()
        if server_id != plan.get("server_id"):
            raise ZoteroError("Zotero library changed; make a new plan")
        item = self.get_item(plan["item_key"])
        if item["version"] != plan["item_version"] or set(item.get("collections", [])) != set(plan["existing_collections"]):
            raise ZoteroError("Zotero item changed since the preview; make a new plan")
        paths = self.collection_paths()
        if any(paths.get(key) != value for key, value in plan["collection_paths"].items()):
            raise ZoteroError("Zotero collection tree changed; make a new plan")
        targets = set(plan["add_collections"])
        if targets != set(plan["collection_paths"]):
            raise ZoteroError("invalid Zotero routing plan collections")
        union = sorted(set(item.get("collections", [])) | targets)
        if set(union) == set(item.get("collections", [])):
            return item
        auth, _ = self.transport("POST", "local/authorize", {"appName": "paper-downloader"}, {"Zotero-Server-ID": server_id})
        key = auth["key"]
        self.transport("PATCH", f"users/0/items/{plan['item_key']}", {"collections": union}, {
            "Zotero-Server-ID": server_id,
            "Zotero-API-Key": key,
            "If-Unmodified-Since-Version": str(item["version"]),
        })
        confirmed = self.get_item(plan["item_key"])
        if not set(union).issubset(set(confirmed.get("collections", []))):
            raise ZoteroError("Zotero write was not confirmed by readback")
        return confirmed
