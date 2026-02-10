"""Handle-first storage for KAG RLM experiments."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Dict, Union


MAX_READ_CHARS = 256


@dataclass(frozen=True)
class BlobRef:
    """Symbolic handle to stored text."""

    key: str
    kind: str
    size: int
    preview: str

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "kind": self.kind,
            "size": self.size,
            "preview": self.preview,
        }


def make_content_ref_id(kind: str, payload: str) -> str:
    """Stable lightweight ref id used in graph literals."""
    digest = sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{kind}:{digest}"


class SymbolicBlobStore:
    """In-memory blob store that never exposes unbounded payload reads."""

    def __init__(self) -> None:
        self._blobs: Dict[str, str] = {}
        self._counter = 0

    def put(self, text: str, kind: str = "text") -> BlobRef:
        key = f"{kind}_{self._counter}"
        self._counter += 1
        self._blobs[key] = text
        return BlobRef(key=key, kind=kind, size=len(text), preview=text[:80])

    def stats(self, ref_or_key: Union[BlobRef, str, dict]) -> dict:
        key = self._unwrap_key(ref_or_key)
        text = self._blobs.get(key)
        if text is None:
            return {"error": f"unknown key: {key}"}
        return {
            "key": key,
            "size": len(text),
            "lines": text.count("\n") + 1,
            "preview": text[:80],
        }

    def read_window(
        self, ref_or_key: Union[BlobRef, str, dict], start: int = 0, size: int = 128
    ) -> dict:
        key = self._unwrap_key(ref_or_key)
        text = self._blobs.get(key)
        if text is None:
            return {"error": f"unknown key: {key}"}

        safe_size = min(max(size, 1), MAX_READ_CHARS)
        safe_start = max(start, 0)
        end = min(safe_start + safe_size, len(text))
        window = text[safe_start:end]
        return {
            "key": key,
            "start": safe_start,
            "end": end,
            "requested_size": size,
            "returned_size": len(window),
            "clamped": size > MAX_READ_CHARS,
            "text": window,
        }

    def _unwrap_key(self, ref_or_key: Union[BlobRef, str, dict]) -> str:
        if isinstance(ref_or_key, BlobRef):
            return ref_or_key.key
        if isinstance(ref_or_key, dict):
            return str(ref_or_key.get("key", ""))
        return str(ref_or_key)

