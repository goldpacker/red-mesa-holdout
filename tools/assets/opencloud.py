#!/usr/bin/env python3
"""Minimal Roblox Open Cloud Assets API client (upload + poll).

Credentials come from the environment (ROBLOX_OPEN_CLOUD_KEY,
ROBLOX_CREATOR_USER_ID), normally loaded from .env.local. The key is never
printed or written anywhere.

    python3 tools/assets/opencloud.py upload <file> <assetType> <displayName>
    python3 tools/assets/opencloud.py get <assetId>

Prints the final JSON (operation response) on stdout.
"""
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = "https://apis.roblox.com/assets/v1"
CONTENT_TYPES = {
    ".fbx": "model/fbx",
    ".glb": "model/gltf-binary",
    ".gltf": "model/gltf+json",
    ".rbxm": "model/x-rbxm",
    ".rbxmx": "model/x-rbxm",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tga": "image/tga",
    ".bmp": "image/bmp",
}


class OpenCloudError(RuntimeError):
    pass


def _key() -> str:
    key = os.environ.get("ROBLOX_OPEN_CLOUD_KEY")
    if not key:
        raise OpenCloudError("ROBLOX_OPEN_CLOUD_KEY not set (source .env.local)")
    return key


def _creator() -> str:
    uid = os.environ.get("ROBLOX_CREATOR_USER_ID")
    if not uid:
        raise OpenCloudError("ROBLOX_CREATOR_USER_ID not set (source .env.local)")
    return uid


def _request(method: str, url: str, body: bytes | None = None, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("x-api-key", _key())
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as err:
        detail = err.read().decode(errors="replace")[:500]
        raise OpenCloudError(f"HTTP {err.code} {method} {url.split('?')[0]}: {detail}") from None


def _multipart(fields: list[tuple[str, str | None, str, bytes]]) -> tuple[bytes, str]:
    boundary = "----rmh" + uuid.uuid4().hex
    out = bytearray()
    for name, filename, ctype, data in fields:
        out += f"--{boundary}\r\n".encode()
        disp = f'form-data; name="{name}"'
        if filename:
            disp += f'; filename="{filename}"'
        out += f"Content-Disposition: {disp}\r\nContent-Type: {ctype}\r\n\r\n".encode()
        out += data + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def poll(operation_path: str, timeout: float = 300) -> dict:
    op_id = operation_path.split("/")[-1]
    deadline = time.time() + timeout
    delay = 1.0
    while time.time() < deadline:
        op = _request("GET", f"{BASE}/operations/{op_id}")
        if op.get("done"):
            if "error" in op:
                raise OpenCloudError(f"operation failed: {json.dumps(op['error'])}")
            return op.get("response", op)
        time.sleep(delay)
        delay = min(delay * 1.5, 8)
    raise OpenCloudError(f"operation {op_id} timed out")


def upload(path: str, asset_type: str, display_name: str, description: str = "Red Mesa Holdout asset") -> dict:
    ext = os.path.splitext(path)[1].lower()
    ctype = CONTENT_TYPES.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"
    meta = {
        "assetType": asset_type,
        "displayName": display_name[:50],
        "description": description,
        "creationContext": {"creator": {"userId": _creator()}},
    }
    with open(path, "rb") as fh:
        data = fh.read()
    body, btype = _multipart([
        ("request", None, "application/json", json.dumps(meta).encode()),
        ("fileContent", os.path.basename(path), ctype, data),
    ])
    op = _request("POST", f"{BASE}/assets", body, {"Content-Type": btype})
    if op.get("done"):
        return op.get("response", op)
    return poll(op["path"])


def get(asset_id: str) -> dict:
    return _request("GET", f"{BASE}/assets/{asset_id}")


def main(argv: list[str]) -> int:
    if len(argv) >= 4 and argv[0] == "upload":
        print(json.dumps(upload(argv[1], argv[2], argv[3]), indent=2))
        return 0
    if len(argv) == 2 and argv[0] == "get":
        print(json.dumps(get(argv[1]), indent=2))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except OpenCloudError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
