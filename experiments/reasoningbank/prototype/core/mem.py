"""Minimal memory store for experiments.

Two-phase retrieval: search() returns IDs only, get() returns content with hard cap.
"""

from dataclasses import dataclass, field, asdict
from difflib import SequenceMatcher
import json, hashlib

@dataclass
class Item:
    """A reusable procedure.

    src values: 'success', 'failure', 'seed', 'contrastive', 'pattern'
    """
    id: str
    title: str       # ≤10 words
    desc: str        # one sentence
    content: str     # full procedure
    src: str         # 'success' | 'failure' | 'seed' | 'contrastive' | 'pattern'
    tags: list[str] = field(default_factory=list)
    scope: str = ''  # 'general' | 'exception' | '' (backward-compatible)

    @staticmethod
    def make_id(title:str, content:str) -> str:
        "Generate stable ID from `title` + `content`."
        return hashlib.sha256(f"{title}\n{content}".encode()).hexdigest()[:12]


def title_similarity(a: str, b: str) -> float:
    """Compute title similarity using SequenceMatcher (0.0-1.0)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def content_jaccard(a: str, b: str) -> float:
    """Compute Jaccard similarity between word sets (0.0-1.0)."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


class MemStore:
    "Minimal memory store for experiments."
    def __init__(self): self._items = {}

    def add(self, item:Item) -> str:
        "Add `item` to store."
        self._items[item.id] = item
        return item.id

    def search(self, q:str, k:int=6, polarity:str=None) -> list[dict]:
        "Return IDs + titles + descs ONLY. Filter by `polarity` ('success'|'failure'|'seed')."
        # Normalize: lowercase, remove punctuation, split
        import string
        trans = str.maketrans('', '', string.punctuation)
        qwords = set(q.lower().translate(trans).split())
        scored = []
        for item in self._items.values():
            # Filter by polarity if specified
            if polarity and item.src != polarity: continue
            text = f"{item.title} {item.desc} {' '.join(item.tags)}".lower().translate(trans)
            words = set(text.split())
            score = len(qwords & words)
            if score > 0: scored.append((score, item))
        scored.sort(key=lambda x: -x[0])
        return [{'id': o.id, 'title': o.title, 'desc': o.desc, 'src': o.src} for _,o in scored[:k]]

    def get(self, ids:list[str], max_n:int=3) -> list[Item]:
        "Return full items (hard cap enforced)."
        if len(ids) > max_n: raise ValueError(f"Requested {len(ids)} items, max is {max_n}")
        return [self._items[i] for i in ids if i in self._items]

    def quote(self, id:str, max_chars:int=500) -> str:
        "Return bounded excerpt of item content."
        item = self._items.get(id)
        if not item: return ""
        return item.content[:max_chars] + ("..." if len(item.content) > max_chars else "")

    def all(self) -> list[Item]: return list(self._items.values())

    def find_similar(self, item: Item, title_thresh: float = 0.8,
                     content_thresh: float = 0.75) -> Item | None:
        """Find existing item similar to `item`.

        Args:
            item: Item to check for similarity
            title_thresh: Minimum title similarity (0.0-1.0)
            content_thresh: Minimum content Jaccard similarity (0.0-1.0)

        Returns:
            Existing similar Item or None
        """
        for existing in self._items.values():
            if existing.src != item.src:  # Same polarity required
                continue
            if title_similarity(existing.title, item.title) > title_thresh:
                if content_jaccard(existing.content, item.content) > content_thresh:
                    return existing
        return None

    def consolidate(self, items: list[Item], dedup: bool = True) -> list[str]:
        """Add items to memory store with optional deduplication.

        Args:
            items: List of Item objects to add
            dedup: If True, skip near-duplicate items (default: True)

        Returns:
            List of added item IDs
        """
        added = []
        for item in items:
            if dedup and self.find_similar(item):
                continue  # Skip near-duplicate
            self._items[item.id] = item
            added.append(item.id)
        return added

    def save(self, path:str):
        "Save all items to JSON file."
        with open(path, 'w') as f: json.dump([asdict(o) for o in self._items.values()], f)

    def load(self, path:str):
        "Load items from JSON file."
        with open(path) as f:
            for d in json.load(f):
                d.setdefault('scope', '')  # backward compat
                self._items[d['id']] = Item(**d)
