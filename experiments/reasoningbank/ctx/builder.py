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
            # Top-K success + top-K failure retrieval
            k_success, k_failure = 2, 1  # Configurable defaults
            success_hits = mem.search(task, k=k_success, polarity='success')
            failure_hits = mem.search(task, k=k_failure, polarity='failure')
            seed_hits = mem.search(task, k=1, polarity='seed')  # General strategies
            all_ids = [h['id'] for h in success_hits + failure_hits + seed_hits]
            if all_ids:
                items = mem.get(all_ids, max_n=len(all_ids))  # Allow all retrieved
                parts.append(l2_mem.pack(items, self.cfg.l2.budget))
        if self.cfg.l3.on and self.cfg.guide_text:
            parts.append(l3_guide.pack(self.cfg.guide_text, self.cfg.l3.budget))
        return '\n\n'.join(parts)

    def tools(self, store:Store, g_path:str, mem:MemStore=None) -> dict:
        "Build tool dict for dspy.RLM. Includes graph, context, and memory tools."
        # Set module globals
        G._store = store

        # Load graph and store in module
        g = Graph().parse(g_path)
        ref = store.put(g_path, 'graph')
        G._graphs[ref.key] = g

        # DSPy RLM calls tools as: tool(args, kwargs) where:
        #   args = actual arguments (value, list, etc)
        #   kwargs = keyword arguments dict

        # Graph tools (bounded ontology access)
        tools = {
            'g_stats': lambda args, kwargs: G.g_stats(ref),
            'g_query': lambda args, kwargs: G.g_query(ref, args if isinstance(args, str) else (args[0] if args else kwargs.get('q', '')), kwargs.get('limit', 100)),
            'g_sample': lambda args, kwargs: G.g_sample(ref, args if isinstance(args, int) else (args[0] if args else kwargs.get('n', 10))),
            'g_classes': lambda args, kwargs: G.g_classes(ref, args if isinstance(args, int) else (args[0] if args else kwargs.get('limit', 50))),
            'g_props': lambda args, kwargs: G.g_props(ref, args if isinstance(args, int) else (args[0] if args else kwargs.get('limit', 50))),
            'g_describe': lambda args, kwargs: G.g_describe(ref, args if isinstance(args, str) else (args[0] if args else kwargs.get('uri', '')), kwargs.get('limit', 20)),
            # Context tools (bounded blob access)
            'ctx_peek': lambda args, kwargs: store.peek(args if isinstance(args, str) else (args[0] if args else kwargs.get('k', '')), args[1] if isinstance(args, list) and len(args) > 1 else kwargs.get('n', 200)),
            'ctx_slice': lambda args, kwargs: store.slice(args if isinstance(args, str) else (args[0] if args else kwargs.get('k', '')), args[1] if isinstance(args, list) and len(args) > 1 else kwargs.get('start', 0), args[2] if isinstance(args, list) and len(args) > 2 else kwargs.get('end', 100)),
            'ctx_stats': lambda args, kwargs: store.stats(args if isinstance(args, str) else (args[0] if args else kwargs.get('k', ''))),
        }

        # Memory tools (Mode 2: tool-mediated retrieval)
        if mem:
            tools.update({
                'mem_search': lambda args, kwargs: mem.search(
                    args if isinstance(args, str) else (args[0] if args else kwargs.get('q', '')),
                    kwargs.get('k', 6),
                    kwargs.get('polarity', None)
                ),
                'mem_get': lambda args, kwargs: [
                    {'id': o.id, 'title': o.title, 'desc': o.desc, 'content': o.content, 'src': o.src}
                    for o in mem.get(
                        args if isinstance(args, list) else ([args] if args else kwargs.get('ids', [])),
                        kwargs.get('max_n', 3)
                    )
                ],
                'mem_quote': lambda args, kwargs: mem.quote(
                    args if isinstance(args, str) else (args[0] if args else kwargs.get('id', '')),
                    kwargs.get('max_chars', 500)
                ),
            })

        return tools
