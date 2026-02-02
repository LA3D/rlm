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
from experiments.reasoningbank.ctx.cache import build_with_cache

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

    def build(self, g: Graph, task: str, mem: MemStore = None, g_path: str = None) -> str:
        """Build context string from enabled layers.

        Args:
            g: RDF graph
            task: Query string (for L2 retrieval)
            mem: Memory store (for L2)
            g_path: Optional path to graph file (enables L0/L1 caching)

        Returns:
            Assembled context string
        """
        parts = []

        # L0/L1 with optional caching
        if self.cfg.l0.on:
            if g_path:
                parts.append(build_with_cache(g_path, 'l0', self.cfg.l0.budget, l0_sense.pack))
            else:
                parts.append(l0_sense.pack(g, self.cfg.l0.budget))

        if self.cfg.l1.on:
            if g_path:
                parts.append(build_with_cache(g_path, 'l1', self.cfg.l1.budget, l1_schema.pack))
            else:
                parts.append(l1_schema.pack(g, self.cfg.l1.budget))

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

        def _norm(args, kwargs):
            if args is None:
                args_list = []
            elif isinstance(args, (list, tuple)):
                args_list = list(args)
            else:
                args_list = [args]
            if kwargs is None or not isinstance(kwargs, dict):
                kwargs = {}
            return args_list, kwargs

        def _arg(args_list, idx, default=None):
            return args_list[idx] if len(args_list) > idx else default

        # Graph tools (bounded ontology access)
        tools = {
            'g_stats': lambda args=None, kwargs=None: G.g_stats(ref),
            'g_query': lambda args=None, kwargs=None: (
                lambda a, k: G.g_query(
                    ref,
                    _arg(a, 0, k.get('q', '')),
                    _arg(a, 1, k.get('limit', 100))
                )
            )(*_norm(args, kwargs)),
            'g_sample': lambda args=None, kwargs=None: (
                lambda a, k: G.g_sample(ref, _arg(a, 0, k.get('n', 10)))
            )(*_norm(args, kwargs)),
            'g_classes': lambda args=None, kwargs=None: (
                lambda a, k: G.g_classes(ref, _arg(a, 0, k.get('limit', 50)))
            )(*_norm(args, kwargs)),
            'g_props': lambda args=None, kwargs=None: (
                lambda a, k: G.g_props(ref, _arg(a, 0, k.get('limit', 50)))
            )(*_norm(args, kwargs)),
            'g_describe': lambda args=None, kwargs=None: (
                lambda a, k: G.g_describe(ref, _arg(a, 0, k.get('uri', '')), k.get('limit', 20))
            )(*_norm(args, kwargs)),
            # Context tools (bounded blob access)
            'ctx_peek': lambda args=None, kwargs=None: (
                lambda a, k: {'error': 'missing key'} if not _arg(a, 0, k.get('k', '')) else
                store.peek(_arg(a, 0, k.get('k', '')), _arg(a, 1, k.get('n', 200)))
            )(*_norm(args, kwargs)),
            'ctx_slice': lambda args=None, kwargs=None: (
                lambda a, k: {'error': 'missing key'} if not _arg(a, 0, k.get('k', '')) else
                store.slice(_arg(a, 0, k.get('k', '')),
                            _arg(a, 1, k.get('start', 0)),
                            _arg(a, 2, k.get('end', 100)))
            )(*_norm(args, kwargs)),
            'ctx_stats': lambda args=None, kwargs=None: (
                lambda a, k: {'error': 'missing key'} if not _arg(a, 0, k.get('k', '')) else
                store.stats(_arg(a, 0, k.get('k', '')))
            )(*_norm(args, kwargs)),
        }

        # Memory tools (Mode 2: tool-mediated retrieval)
        if mem:
            tools.update({
                'mem_search': lambda args=None, kwargs=None: (
                    lambda a, k: mem.search(
                        _arg(a, 0, k.get('q', '')),
                        k.get('k', 6),
                        k.get('polarity', None)
                    )
                )(*_norm(args, kwargs)),
                'mem_get': lambda args=None, kwargs=None: (
                    lambda a, k: [
                        {
                            'id': o.id,
                            'title': o.title,
                            'desc': o.desc,
                            'content': (
                                o.content[:(k.get('max_chars', 1000))] +
                                ("..." if len(o.content) > (k.get('max_chars', 1000)) else "")
                            ),
                            'src': o.src
                        }
                        for o in mem.get(
                            _arg(a, 0, k.get('ids', [])) if isinstance(_arg(a, 0, None), list)
                            else ([ _arg(a, 0, None) ] if _arg(a, 0, None) else k.get('ids', [])),
                            k.get('max_n', 3)
                        )
                    ]
                )(*_norm(args, kwargs)),
                'mem_quote': lambda args=None, kwargs=None: (
                    lambda a, k: mem.quote(
                        _arg(a, 0, k.get('id', '')),
                        k.get('max_chars', 500)
                    )
                )(*_norm(args, kwargs)),
            })

        return tools
