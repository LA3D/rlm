"""Minimal memory store for experiments.

Two-phase retrieval: search() returns IDs only, get() returns content with hard cap.
"""

from dataclasses import dataclass, field, asdict
import json, hashlib

@dataclass
class Item:
    "A reusable procedure."
    id: str
    title: str       # ≤10 words
    desc: str        # one sentence
    content: str     # full procedure
    src: str         # 'success' | 'failure' | 'seed'
    tags: list[str] = field(default_factory=list)

    @staticmethod
    def make_id(title:str, content:str) -> str:
        "Generate stable ID from `title` + `content`."
        return hashlib.sha256(f"{title}\n{content}".encode()).hexdigest()[:12]

class MemStore:
    "Minimal memory store for experiments."
    def __init__(self): self._items = {}

    def add(self, item:Item) -> str:
        "Add `item` to store."
        self._items[item.id] = item
        return item.id

    def search(self, q:str, k:int=5) -> list[dict]:
        "Return IDs + titles + descs ONLY (not content)."
        # Simple: score by word overlap
        qwords = set(q.lower().split())
        scored = []
        for item in self._items.values():
            words = set(f"{item.title} {item.desc} {' '.join(item.tags)}".lower().split())
            score = len(qwords & words)
            if score > 0: scored.append((score, item))
        scored.sort(key=lambda x: -x[0])
        return [{'id': o.id, 'title': o.title, 'desc': o.desc} for _,o in scored[:k]]

    def get(self, ids:list[str], max_n:int=3) -> list[Item]:
        "Return full items (hard cap enforced)."
        if len(ids) > max_n: raise ValueError(f"Requested {len(ids)} items, max is {max_n}")
        return [self._items[i] for i in ids if i in self._items]

    def all(self) -> list[Item]: return list(self._items.values())

    def save(self, path:str):
        "Save all items to JSON file."
        with open(path, 'w') as f: json.dump([asdict(o) for o in self._items.values()], f)

    def load(self, path:str):
        "Load items from JSON file."
        with open(path) as f:
            for d in json.load(f): self._items[d['id']] = Item(**d)
