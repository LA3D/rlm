"""Local tests for strict symbolic prompt + Owlready2 memory tooling."""

from experiments.owl.symbolic_handles import MAX_READ_CHARS, SymbolicBlobStore
from experiments.owl.tools import OwlRLMToolset


def test_blob_store_read_is_bounded():
    store = SymbolicBlobStore()
    ref = store.put("x" * 2000, kind="prompt")

    out = store.read_window(ref, start=0, size=5000)
    assert out["clamped"] is True
    assert out["returned_size"] == MAX_READ_CHARS


def test_prompt_read_window_returns_nested_handle():
    ts = OwlRLMToolset(prompt_text="abcdefghijklmnopqrstuvwxyz")
    out = ts.prompt_read_window(start=0, size=8)
    assert "text" not in out
    assert out["returned_size"] == 8
    assert out["window_ref"]["key"].startswith("prompt_window_")


def test_memory_search_returns_metadata_not_content():
    ts = OwlRLMToolset(prompt_text="short prompt")
    added = ts.memory_add(
        kind="principle",
        title="Use bounded reads",
        summary="Never read full prompt",
        content="This is full memory content payload",
        tags=["rlm", "memory"],
    )

    hits = ts.memory_search("bounded prompt reads", k=3)
    assert len(hits) >= 1
    first = hits[0]
    assert "title" in first
    assert "summary" in first
    assert "content_key" not in first
    assert "content_hash" not in first
    assert first["item_id"] == added["item_id"]


def test_memory_window_read_is_bounded():
    ts = OwlRLMToolset(prompt_text="short prompt")
    added = ts.memory_add(
        kind="episode",
        title="Bad long read",
        summary="Example failure",
        content="A" * 3000,
    )
    item_id = added["item_id"]
    out = ts.memory_read_window(item_id=item_id, start=0, size=9999)
    assert out["returned_size"] == MAX_READ_CHARS
    assert "text" not in out
    assert out["window_ref"]["key"].startswith("memory_window_")
