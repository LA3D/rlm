"""Owlready2-backed symbolic memory with metadata-first retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Dict, Iterable, List, Optional

from owlready2 import DataProperty, FunctionalProperty, Thing, World


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mk_id(kind: str, title: str, summary: str) -> str:
    payload = f"{kind}\n{title}\n{summary}"
    return sha256(payload.encode("utf-8")).hexdigest()[:12]


def _tokenize(text: str) -> set[str]:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    return {tok for tok in cleaned.split() if tok}


@dataclass
class OwlMemItem:
    item_id: str
    kind: str
    title: str
    summary: str
    content_key: str
    content_hash: str
    tags: List[str]
    created_at: str


class OwlSymbolicMemory:
    """Small symbolic memory store with Owlready2 classes and properties."""

    def __init__(self, backend_path: Optional[str] = None) -> None:
        self.world = World()
        if backend_path:
            self.world.set_backend(filename=backend_path)

        self.onto = self.world.get_ontology("http://la3d.local/rlm_owl_memory#")
        with self.onto:
            class MemoryItem(Thing):
                pass

            class Principle(MemoryItem):
                pass

            class Episode(MemoryItem):
                pass

            class item_id(DataProperty, FunctionalProperty):
                domain = [MemoryItem]
                range = [str]

            class kind(DataProperty, FunctionalProperty):
                domain = [MemoryItem]
                range = [str]

            class title(DataProperty, FunctionalProperty):
                domain = [MemoryItem]
                range = [str]

            class summary(DataProperty, FunctionalProperty):
                domain = [MemoryItem]
                range = [str]

            class content_key(DataProperty, FunctionalProperty):
                domain = [MemoryItem]
                range = [str]

            class content_hash(DataProperty, FunctionalProperty):
                domain = [MemoryItem]
                range = [str]

            class tags_csv(DataProperty, FunctionalProperty):
                domain = [MemoryItem]
                range = [str]

            class created_at(DataProperty, FunctionalProperty):
                domain = [MemoryItem]
                range = [str]

        self._classes = {
            "principle": self.onto.Principle,
            "episode": self.onto.Episode,
        }

    def add_item(
        self,
        kind: str,
        title: str,
        summary: str,
        content_key: str,
        content_hash: str,
        tags: Optional[Iterable[str]] = None,
    ) -> dict:
        k = kind.lower().strip()
        cls = self._classes.get(k, self.onto.MemoryItem)
        item_key = _mk_id(k, title, summary)
        iri_name = f"m_{item_key}"
        inst = self._find_by_item_id(item_key)
        if inst is None:
            inst = cls(iri_name)

        tag_list = sorted({t.strip() for t in (tags or []) if t and t.strip()})
        inst.item_id = item_key
        inst.kind = k
        inst.title = title.strip()
        inst.summary = summary.strip()
        inst.content_key = content_key.strip()
        inst.content_hash = content_hash.strip()
        inst.tags_csv = ",".join(tag_list)
        inst.created_at = _now_iso()

        return self.get_item_metadata(item_key)

    def get_item_metadata(self, item_id: str) -> dict:
        inst = self._find_by_item_id(item_id)
        if not inst:
            return {"error": f"item not found: {item_id}"}

        tags_raw = str(getattr(inst, "tags_csv", "") or "")
        tags = [t for t in tags_raw.split(",") if t]
        return {
            "item_id": str(getattr(inst, "item_id", "")),
            "kind": str(getattr(inst, "kind", "")),
            "title": str(getattr(inst, "title", "")),
            "summary": str(getattr(inst, "summary", "")),
            "content_key": str(getattr(inst, "content_key", "")),
            "content_hash": str(getattr(inst, "content_hash", "")),
            "tags": tags,
            "created_at": str(getattr(inst, "created_at", "")),
        }

    def search(self, query: str, k: int = 5, kind: str = "") -> list[dict]:
        q_tokens = _tokenize(query)
        kind_filter = kind.strip().lower()
        scored = []

        for inst in self.onto.MemoryItem.instances():
            inst_kind = str(getattr(inst, "kind", "")).lower()
            if kind_filter and inst_kind != kind_filter:
                continue

            title = str(getattr(inst, "title", ""))
            summary = str(getattr(inst, "summary", ""))
            tags = str(getattr(inst, "tags_csv", "")).replace(",", " ")
            doc_tokens = _tokenize(f"{title} {summary} {tags}")
            score = len(q_tokens & doc_tokens) if q_tokens else 0
            scored.append((score, inst))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [self.get_item_metadata(str(getattr(i, "item_id", ""))) for _, i in scored[: max(k, 0)]]
        for row, (score, _) in zip(top, scored[: max(k, 0)]):
            row["score"] = score
            row.pop("content_key", None)
            row.pop("content_hash", None)
        return top

    def stats(self) -> dict:
        all_items = list(self.onto.MemoryItem.instances())
        n_principle = sum(1 for x in all_items if str(getattr(x, "kind", "")) == "principle")
        n_episode = sum(1 for x in all_items if str(getattr(x, "kind", "")) == "episode")
        return {
            "items_total": len(all_items),
            "principles": n_principle,
            "episodes": n_episode,
        }

    def save(self, path: str) -> None:
        self.onto.save(file=path, format="rdfxml")

    def _find_by_item_id(self, item_id: str):
        for inst in self.onto.MemoryItem.instances():
            if str(getattr(inst, "item_id", "")) == item_id:
                return inst
        return None
