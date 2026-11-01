"""On-disk cache for the expensive startup steps: chunk embeddings (.npy) and verified amendments (.json).

Every entry is named by a hash of everything that produced it: the PDF files' bytes, the model names and the settings
or prompts involved. Change any PDF (or model, or prompt) and the key changes, so the entry is rebuilt automatically.
Set SPIT_NO_CACHE=1 to ignore existing entries and rebuild (the fresh results are still written).
"""
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

from .config import CACHE_DIR, DOCS_DIR


def enabled() -> bool:
    return os.getenv("SPIT_NO_CACHE", "").strip().lower() not in ("1", "true", "yes")


def digest(*parts) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(json.dumps(p, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()[:24]


def pdf_fingerprint(docs_dir: Path = DOCS_DIR) -> list:
    """(file name, sha256 of its bytes) for every PDF that could be loaded."""
    out = []
    for f in sorted(Path(docs_dir).glob("*.pdf")):
        out.append((f.name, hashlib.sha256(f.read_bytes()).hexdigest()))
    return out


def _path(kind: str, key: str, ext: str) -> Path:
    return Path(CACHE_DIR) / f"{kind}-{key}.{ext}"


def load_json(kind: str, key: str):
    p = _path(kind, key, "json")
    if not enabled() or not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"[cache] ignoring unreadable {p.name}: {e}", file=sys.stderr)
        return None
    print(f"[cache] loaded {p.name}", file=sys.stderr)
    return data


def save_json(kind: str, key: str, data) -> None:
    _write(_path(kind, key, "json"), lambda tmp: tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                                                 encoding="utf-8"))


def load_array(kind: str, key: str, rows: int):
    p = _path(kind, key, "npy")
    if not enabled() or not p.is_file():
        return None
    try:
        arr = np.load(p)
    except (OSError, ValueError) as e:
        print(f"[cache] ignoring unreadable {p.name}: {e}", file=sys.stderr)
        return None
    if arr.shape[0] != rows:
        return None
    print(f"[cache] loaded {p.name}", file=sys.stderr)
    return arr


def save_array(kind: str, key: str, arr) -> None:
    def write(tmp: Path):
        with tmp.open("wb") as f:
            np.save(f, arr)
    _write(_path(kind, key, "npy"), write)


def _write(path: Path, writer) -> None:
    """Write via a temp file and rename, so a crash never leaves a half-written entry behind."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        writer(tmp)
        os.replace(tmp, path)
    except OSError as e:  # a read-only disk only costs speed
        print(f"[cache] could not write {path.name}: {e}", file=sys.stderr)
