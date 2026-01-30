"""Layer Cake Context Builder - Primary experimental control surface.

Assembles context from enabled layers (L0-L3), each with explicit budget.
This is where experiments toggle which knowledge representations help.
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from dataclasses import dataclass, field
from rdflib import Graph
from experiments.reasoningbank.core.blob import Store, Ref
from experiments.reasoningbank.core.mem import MemStore
from experiments.reasoningbank.core import graph as G
from experiments.reasoningbank.packers import l0_sense, l1_schema, l2_mem, l3_guide

@dataclass
class Layer:
    "Layer configuration: enabled + budget."
    on: bool = False
    budget: int = 0

@dataclass
class Cfg:
    "Context configuration - toggles for layer cake."
    l0: Layer = field(default_factory=lambda: Layer(False, 600))
    l1: Layer = field(default_factory=lambda: Layer(False, 1000))
    l2: Layer = field(default_factory=lambda: Layer(False, 2000))
    l3: Layer = field(default_factory=lambda: Layer(False, 1000))
    guide_text: str = ""  # Full guide for L3

class Builder:
    "Assembles layer cake context for injection."
    def __init__(self, cfg:Cfg): self.cfg = cfg

    def build(self, g:Graph, task:str, mem:MemStore=None) -> str:
        "Build context string from enabled layers."
        parts = []
        if self.cfg.l0.on: parts.append(l0_sense.pack(g, self.cfg.l0.budget))
        if self.cfg.l1.on: parts.append(l1_schema.pack(g, self.cfg.l1.budget))
        if self.cfg.l2.on and mem:
            hits = mem.search(task, k=3)
            if hits:
                items = mem.get([h['id'] for h in hits])
                parts.append(l2_mem.pack(items, self.cfg.l2.budget))
        if self.cfg.l3.on and self.cfg.guide_text:
            parts.append(l3_guide.pack(self.cfg.guide_text, self.cfg.l3.budget))
        return '\n\n'.join(parts)

    def tools(self, store:Store, g_path:str) -> dict:
        "Build tool dict for dspy.RLM."
        # Set module globals
        G._store = store

        # Load graph and store in module
        g = Graph().parse(g_path)
        ref = store.put(g_path, 'graph')
        G._graphs[ref.key] = g

        # Return bounded tools with correct DSPy signatures
        # DSPy calls tools with (args, kwargs) so we need to accept those
        return {
            'g_stats': lambda *args, **kwargs: G.g_stats(ref),
            'g_query': lambda *args, **kwargs: G.g_query(ref, args[0] if args else kwargs.get('q', ''), kwargs.get('limit', 100)),
            'g_sample': lambda *args, **kwargs: G.g_sample(ref, args[0] if args else kwargs.get('n', 10)),
            'g_classes': lambda *args, **kwargs: G.g_classes(ref, args[0] if args else kwargs.get('limit', 50)),
            'g_props': lambda *args, **kwargs: G.g_props(ref, args[0] if args else kwargs.get('limit', 50)),
            'g_describe': lambda *args, **kwargs: G.g_describe(ref, args[0] if args else kwargs.get('uri', ''), kwargs.get('limit', 20)),
            'ctx_peek': lambda *args, **kwargs: store.peek(args[0] if args else kwargs.get('k', ''), args[1] if len(args) > 1 else kwargs.get('n', 200)),
            'ctx_slice': lambda *args, **kwargs: store.slice(args[0] if args else kwargs.get('k', ''), args[1] if len(args) > 1 else kwargs.get('start', 0), args[2] if len(args) > 2 else kwargs.get('end', 100)),
            'ctx_stats': lambda *args, **kwargs: store.stats(args[0] if args else kwargs.get('k', '')),
        }
