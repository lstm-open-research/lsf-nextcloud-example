#!/usr/bin/env python3
"""
Custom Git LFS transfer agent for Nextcloud (via WebDAV).
Speaks the LFS custom transfer protocol over stdin/stdout.
"""

import sys
import json
import os
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

NEXTCLOUD_URL      = os.environ["NEXTCLOUD_URL"].rstrip("/")
NEXTCLOUD_USER     = os.environ["NEXTCLOUD_USER"]
NEXTCLOUD_PASSWORD = os.environ["NEXTCLOUD_APP_PASSWORD"]
LFS_PATH           = os.environ.get("NEXTCLOUD_LFS_PATH", "LFS/git-lfs")

# WebDAV base for file operations
DAV_BASE = f"{NEXTCLOUD_URL}/remote.php/dav/files/{NEXTCLOUD_USER}/{LFS_PATH}"

AUTH = (NEXTCLOUD_USER, NEXTCLOUD_PASSWORD)


# ── Protocol helpers ──────────────────────────────────────────────────────────

def send(obj: dict):
    """Write a JSON message to stdout for Git LFS to consume."""
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def log(msg: str):
    """Write debug info to stderr (never stdout — that's reserved for LFS protocol)."""
    sys.stderr.write(f"[nextcloud-agent] {msg}\n")
    sys.stderr.flush()


# ── WebDAV helpers ────────────────────────────────────────────────────────────

def object_url(oid: str) -> str:
    """
    Mirror the layout Git LFS uses internally:
    first 2 chars / next 2 chars / full oid
    e.g. ab/cd/abcd1234...
    """
    return f"{DAV_BASE}/{oid[:2]}/{oid[2:4]}/{oid}"


def ensure_remote_dirs(oid: str):
    """Create the nested directories on Nextcloud if they don't exist."""
    dirs = [
        DAV_BASE,
        f"{DAV_BASE}/{oid[:2]}",
        f"{DAV_BASE}/{oid[:2]}/{oid[2:4]}",
    ]
    for d in dirs:
        resp = requests.request("MKCOL", d, auth=AUTH)
        # 201 = created, 405 = already exists — both are fine
        if resp.status_code not in (201, 405):
            log(f"Warning: MKCOL {d} returned {resp.status_code}")


# ── Core operations ───────────────────────────────────────────────────────────

def upload(oid: str, size: int, path: str):
    log(f"Uploading {oid} ({size} bytes) from {path}")
    ensure_remote_dirs(oid)
    url = object_url(oid)

    try:
        with open(path, "rb") as f:
            resp = requests.put(url, data=f, auth=AUTH)
        if resp.status_code in (200, 201, 204):
            log(f"Upload OK: {oid}")
            send({"event": "complete", "oid": oid})
        else:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        log(f"Upload FAILED: {e}")
        send({
            "event": "complete",
            "oid": oid,
            "error": {"code": 2, "message": str(e)}
        })


def download(oid: str, size: int, path: str):
    log(f"Downloading {oid} to {path}")
    url = object_url(oid)
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    try:
        resp = requests.get(url, auth=AUTH, stream=True)
        if resp.status_code == 200:
            with open(path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            log(f"Download OK: {oid}")
            send({"event": "complete", "oid": oid, "path": path})
        else:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        log(f"Download FAILED: {e}")
        send({
            "event": "complete",
            "oid": oid,
            "error": {"code": 2, "message": str(e)}
        })


# ── Main: LFS custom transfer protocol ───────────────────────────────────────

def main():
    # Step 1: handshake — LFS sends init, we declare our capability
    init_msg = json.loads(sys.stdin.readline())
    log(f"Init: {init_msg}")
    send({"event": "capability", "transfers": ["custom"]})

    # Step 2: process upload/download events until terminate
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        msg = json.loads(line)
        event = msg.get("event")
        log(f"Event: {event}, oid: {msg.get('oid', 'n/a')}")

        if event == "upload":
            upload(msg["oid"], msg["size"], msg["path"])
        elif event == "download":
            download(msg["oid"], msg["size"], msg["path"])
        elif event == "terminate":
            log("Terminating.")
            break


if __name__ == "__main__":
    main()