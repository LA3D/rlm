"""RLM tool surface for strict symbolic prompt + Owlready2 memory."""

from __future__ import annotations

from hashlib import sha256
from typing import Iterable, Optional

from experiments.owl.owl_memory import OwlSymbolicMemory
from experiments.owl.symbolic_handles import MAX_READ_CHARS, BlobRef, SymbolicBlobStore


class OwlRLMToolset:
    """Handle-only tools. Prompt and memory payloads stay in symbolic storage."""

    def __init__(
        self,
        prompt_text: str,
        blob_store: Optional[SymbolicBlobStore] = None,
        owl_memory: Optional[OwlSymbolicMemory] = None,
    ) -> None:
        self.store = blob_store or SymbolicBlobStore()
        self.mem = owl_memory or OwlSymbolicMemory()
        self.prompt_ref = self.store.put(prompt_text, kind="prompt")

    # Prompt tools
    def prompt_stats(self) -> dict:
        """Return prompt metadata only (no raw prompt payload)."""
        out = self.store.stats(self.prompt_ref)
        out["max_read_chars"] = MAX_READ_CHARS
        return out

    def prompt_read_window(self, start: int = 0, size: int = 128) -> dict:
        """Return bounded window from prompt (strictly capped)."""
        window = self.store.read_window(self.prompt_ref, start=start, size=size)
        return self._window_to_handle(window, kind="prompt_window")

    def prompt_read_chunk(self, chunk_index: int = 0, chunk_size: int = 128) -> dict:
        """Return bounded chunk from prompt (strictly capped)."""
        window = self.store.read_chunk(self.prompt_ref, chunk_index=chunk_index, chunk_size=chunk_size)
        return self._window_to_handle(window, kind="prompt_window")

    # Memory tools
    def memory_add(
        self,
        kind: str,
        title: str,
        summary: str,
        content: str,
        tags: Optional[Iterable[str]] = None,
    ) -> dict:
        """Add memory item. Content is stored symbolically and indexed in OWL."""
        content_ref = self.store.put(content, kind=f"{kind.lower()}_content")
        content_hash = sha256(content.encode("utf-8")).hexdigest()[:16]
        meta = self.mem.add_item(
            kind=kind,
            title=title,
            summary=summary,
            content_key=content_ref.key,
            content_hash=content_hash,
            tags=tags or [],
        )
        meta["content_ref"] = content_ref.to_dict()
        return meta

    def memory_search(self, query: str, k: int = 5, kind: str = "") -> list[dict]:
        """Search by metadata. Returns ids/titles/summaries (not full content)."""
        return self.mem.search(query=query, k=k, kind=kind)

    def memory_stats(self) -> dict:
        """Return memory store counts."""
        return self.mem.stats()

    def memory_item_metadata(self, item_id: str) -> dict:
        """Return full metadata for one item (includes content key/hash, no content)."""
        return self.mem.get_item_metadata(item_id)

    def memory_read_window(self, item_id: str, start: int = 0, size: int = 128) -> dict:
        """Read bounded content window for a specific memory item."""
        meta = self.mem.get_item_metadata(item_id)
        if "error" in meta:
            return meta
        window = self.store.read_window(meta["content_key"], start=start, size=size)
        return self._window_to_handle(window, kind="memory_window")

    def handle_stats(self, ref_or_key: BlobRef | str | dict) -> dict:
        """Return metadata for an arbitrary symbolic handle."""
        return self.store.stats(ref_or_key)

    def handle_read_window(
        self,
        ref_or_key: BlobRef | str | dict,
        start: int = 0,
        size: int = 128,
        include_text: bool = False,
        nest: bool = False,
    ) -> dict:
        """Read a bounded window from any handle.

        Default behavior is metadata-first and non-nesting to avoid handle chains.
        """
        window = self.store.read_window(ref_or_key, start=start, size=size)
        if "error" in window:
            return window
        text = str(window.pop("text", ""))
        if nest:
            window_ref = self.store.put(text, kind="handle_window")
            window["window_ref"] = window_ref.to_dict()
            return window
        window["text_preview"] = text[:80]
        if include_text:
            window["text"] = text
        return window

    def as_tools(self) -> list:
        """DSPy 3.1+ expects a list of callables."""
        return [
            self.prompt_stats,
            self.prompt_read_window,
            self.prompt_read_chunk,
            self.memory_add,
            self.memory_search,
            self.memory_stats,
            self.memory_item_metadata,
            self.memory_read_window,
            self.handle_stats,
            self.handle_read_window,
        ]

    def _window_to_handle(self, window: dict, kind: str) -> dict:
        if "error" in window:
            return window
        text = str(window.pop("text", ""))
        window_ref = self.store.put(text, kind=kind)
        window["window_ref"] = window_ref.to_dict()
        return window
