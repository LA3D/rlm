"""BlobRef handle pattern - REPL sees metadata, not payloads.

The key insight: RLM will naturally follow the path of least resistance.
If the easiest function returns the whole blob, you'll get blob-in-history.
If the easiest returns metadata + offsets, you'll get Algorithm-1 behavior.
"""

from dataclasses import dataclass

@dataclass
class Ref:
    "Handle for large data - REPL sees metadata, not payload."
    key: str
    dtype: str   # 'graph', 'results', 'mem', 'text'
    sz: int      # char count
    prev: str    # first 80 chars
    def __repr__(self): return f"Ref({self.key!r}, {self.dtype}, {self.sz} chars)"

class Store:
    "In-memory blob storage for a single run."
    def __init__(self): self._blobs,self._counter = {},0

    def put(self, content:str, dtype:str) -> Ref:
        "Store `content`, return handle."
        k = f"{dtype}_{self._counter}"; self._counter += 1
        self._blobs[k] = content
        return Ref(k, dtype, len(content), content[:80])

    def get(self, k:str) -> str: return self._blobs[k]
    def peek(self, k:str, n:int=200) -> str: return self._blobs[k][:n]
    def slice(self, k:str, start:int, end:int) -> str: return self._blobs[k][start:end]
    def stats(self, k:str) -> dict:
        c = self._blobs[k]
        return {'sz': len(c), 'lines': c.count('\n')+1}
