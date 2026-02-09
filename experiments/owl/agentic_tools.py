"""Combined strict-symbolic toolset for prompt/memory + OWL/SHACL workflows."""

from __future__ import annotations

from typing import Optional

from experiments.owl.agentic_ontology import AgenticOntologyWorkspace
from experiments.owl.owl_memory import OwlSymbolicMemory
from experiments.owl.symbolic_handles import SymbolicBlobStore
from experiments.owl.tools import OwlRLMToolset


class AgenticOwlToolset:
    """Tool surface for agentic ontology construction with trajectory-friendly operations."""

    def __init__(
        self,
        prompt_text: str,
        workspace: AgenticOntologyWorkspace,
        blob_store: Optional[SymbolicBlobStore] = None,
        owl_memory: Optional[OwlSymbolicMemory] = None,
        current_cq_id: str = "",
    ) -> None:
        self.base = OwlRLMToolset(
            prompt_text=prompt_text,
            blob_store=blob_store,
            owl_memory=owl_memory,
        )
        self.workspace = workspace
        self.store = self.base.store
        self.mem = self.base.mem
        self.prompt_ref = self.base.prompt_ref
        self.current_cq_id = current_cq_id.strip()
        self._graph_revision = 0
        self._last_validation_revision = -1
        self._validations_without_delta = 0
        self._handle_reads_total = 0
        self._handle_reads_by_key: dict[str, int] = {}
        self._max_handle_reads_per_run = 24
        self._max_reads_per_handle = 3
        self._max_validations_without_delta = 2
        self._report_text_reads = 0
        self._max_report_text_reads = 1
        self._last_signature_counts: dict[str, int] = {}
        self._cq_query_refs: dict[str, dict] = {}
        for row in self.workspace.list_cqs():
            cq_id = row["cq_id"]
            query_ref = self.store.put(self.workspace.cq_query(cq_id), kind=f"cq_query_{cq_id.lower()}")
            self._cq_query_refs[cq_id] = query_ref.to_dict()

    def prompt_stats(self) -> dict:
        return self.base.prompt_stats()

    def prompt_read_window(self, start: int = 0, size: int = 128) -> dict:
        return self.base.prompt_read_window(start=start, size=size)

    def prompt_read_chunk(self, chunk_index: int = 0, chunk_size: int = 128) -> dict:
        return self.base.prompt_read_chunk(chunk_index=chunk_index, chunk_size=chunk_size)

    def memory_add(
        self,
        kind: str,
        title: str,
        summary: str,
        content: str,
        tags: Optional[list[str]] = None,
    ) -> dict:
        return self.base.memory_add(kind=kind, title=title, summary=summary, content=content, tags=tags)

    def memory_search(self, query: str, k: int = 5, kind: str = "") -> list[dict]:
        return self.base.memory_search(query=query, k=k, kind=kind)

    def memory_stats(self) -> dict:
        return self.base.memory_stats()

    def memory_item_metadata(self, item_id: str) -> dict:
        return self.base.memory_item_metadata(item_id=item_id)

    def memory_read_window(self, item_id: str, start: int = 0, size: int = 128) -> dict:
        return self.base.memory_read_window(item_id=item_id, start=start, size=size)

    def handle_stats(self, ref_or_key: dict | str) -> dict:
        return self.base.handle_stats(ref_or_key=ref_or_key)

    def handle_read_window(
        self,
        ref_or_key: dict | str,
        start: int = 0,
        size: int = 128,
        include_text: bool = False,
    ) -> dict:
        key = self._extract_ref_key(ref_or_key)
        kind = self._extract_ref_kind(ref_or_key)
        self._handle_reads_total += 1
        self._handle_reads_by_key[key] = self._handle_reads_by_key.get(key, 0) + 1
        key_reads = self._handle_reads_by_key.get(key, 0)
        if kind == "shacl_report_text" and include_text:
            self._report_text_reads += 1
            if self._report_text_reads > self._max_report_text_reads:
                return {
                    "error": "report_text_read_blocked",
                    "key": key,
                    "report_text_reads": self._report_text_reads,
                    "max_report_text_reads": self._max_report_text_reads,
                    "suggestion": "Use signatures_ref or violations_ref with ontology_signature_index before reading report text.",
                }
        if self._handle_reads_total > self._max_handle_reads_per_run:
            return {
                "error": "handle_read_budget_exceeded",
                "reads_total": self._handle_reads_total,
                "max_reads_total": self._max_handle_reads_per_run,
                "suggestion": "Use cq_query_symbols and ontology_signature_index instead of repeated handle reads.",
            }
        if key_reads > self._max_reads_per_handle:
            return {
                "error": "repeated_handle_read_blocked",
                "key": key,
                "reads_for_key": key_reads,
                "max_reads_for_key": self._max_reads_per_handle,
                "suggestion": "Use cq_query_symbols or ontology_validate_focus to move forward.",
            }
        return self.base.handle_read_window(
            ref_or_key=ref_or_key,
            start=start,
            size=size,
            include_text=include_text,
            nest=False,
        )

    def ontology_stats(self) -> dict:
        return self.workspace.ontology_stats()

    def ontology_node_outgoing(self, node_iri: str, limit: int = 20) -> dict:
        return self.workspace.node_outgoing(node_iri=node_iri, limit=limit)

    def ontology_node_incoming(self, node_iri: str, limit: int = 20) -> dict:
        return self.workspace.node_incoming(node_iri=node_iri, limit=limit)

    def ontology_validate(self, max_results: int = 25) -> dict:
        blocked = self._guard_validation_budget()
        if blocked is not None:
            return blocked
        out = self.workspace.validate_graph(store=self.store, max_results=max_results, include_rows=False)
        return self._annotate_validation_result(out)

    def ontology_validate_preview(self, max_results: int = 10) -> dict:
        blocked = self._guard_validation_budget()
        if blocked is not None:
            return blocked
        out = self.workspace.validate_graph(store=self.store, max_results=max_results, include_rows=True)
        return self._annotate_validation_result(out)

    def ontology_signature_index(self, max_signatures: int = 25) -> dict:
        blocked = self._guard_validation_budget()
        if blocked is not None:
            return blocked
        out = self.workspace.validate_graph(
            store=self.store,
            max_results=max_signatures,
            include_rows=False,
        )
        return self._annotate_validation_result(out)

    def ontology_validate_focus(self, cq_id: str, max_results: int = 25) -> dict:
        cq_mismatch = self._guard_cq_mismatch(cq_id)
        if cq_mismatch is not None:
            return cq_mismatch
        blocked = self._guard_validation_budget()
        if blocked is not None:
            return blocked
        out = self.workspace.validate_focus_for_cq(
            cq_id=cq_id,
            store=self.store,
            max_results=max_results,
            include_rows=False,
        )
        out = self._annotate_validation_result(out)
        if (
            "error" not in out
            and not out.get("conforms", True)
            and int(out.get("validation_results", 0)) == 0
        ):
            global_out = self.workspace.validate_graph(
                store=self.store,
                max_results=min(max(int(max_results), 1), 10),
                include_rows=False,
            )
            out["global_signature_hint"] = {
                "validation_results": global_out.get("validation_results", 0),
                "signatures_total": global_out.get("signatures_total", 0),
                "top_signatures": global_out.get("top_signatures", [])[:5],
                "signatures_ref": global_out.get("signatures_ref", {}),
                "violations_ref": global_out.get("violations_ref", {}),
            }
        return out

    def cq_list(self) -> list[dict]:
        if self.current_cq_id:
            row = next(
                (entry for entry in self.workspace.list_cqs() if entry["cq_id"] == self.current_cq_id),
                None,
            )
            if row is None:
                return []
            out = dict(row)
            out["query_ref"] = self._cq_query_refs.get(row["cq_id"], {})
            return [out]
        rows = []
        for row in self.workspace.list_cqs():
            out = dict(row)
            out["query_ref"] = self._cq_query_refs.get(row["cq_id"], {})
            rows.append(out)
        return rows

    def cq_details(self, cq_id: str) -> dict:
        cq_mismatch = self._guard_cq_mismatch(cq_id)
        if cq_mismatch is not None:
            return cq_mismatch
        details = self.workspace.cq_details(cq_id)
        if "error" in details:
            return details
        details["query_ref"] = self._cq_query_refs.get(cq_id, {})
        details["anchors"] = self.workspace.cq_anchor_nodes(cq_id).get("anchors", [])
        details["query_symbols"] = self.workspace.cq_query_symbols(cq_id)
        details.pop("ask_query", None)
        return details

    def cq_query_symbols(self, cq_id: str) -> dict:
        cq_mismatch = self._guard_cq_mismatch(cq_id)
        if cq_mismatch is not None:
            return cq_mismatch
        return self.workspace.cq_query_symbols(cq_id)

    def cq_anchor_nodes(self, cq_id: str) -> dict:
        cq_mismatch = self._guard_cq_mismatch(cq_id)
        if cq_mismatch is not None:
            return cq_mismatch
        return self.workspace.cq_anchor_nodes(cq_id)

    def cq_node_allowed(self, cq_id: str, node_iri: str) -> dict:
        cq_mismatch = self._guard_cq_mismatch(cq_id)
        if cq_mismatch is not None:
            return cq_mismatch
        return self.workspace.node_allowed_for_cq(cq_id=cq_id, node_iri=node_iri)

    def cq_query_read_window(self, cq_id: str, start: int = 0, size: int = 128) -> dict:
        cq_mismatch = self._guard_cq_mismatch(cq_id)
        if cq_mismatch is not None:
            return cq_mismatch
        query_ref = self._cq_query_refs.get(cq_id)
        if query_ref is None:
            return {"error": f"unknown cq_id: {cq_id}"}
        window = self.store.read_window(query_ref, start=start, size=size)
        if "error" in window:
            return window
        text = str(window.pop("text", ""))
        window_ref = self.store.put(text, kind="cq_query_window")
        window["window_ref"] = window_ref.to_dict()
        return window

    def cq_eval(self, cq_id: str) -> dict:
        cq_mismatch = self._guard_cq_mismatch(cq_id)
        if cq_mismatch is not None:
            return cq_mismatch
        return self.workspace.evaluate_cq(cq_id)

    def operator_catalog(self) -> list[dict]:
        return self.workspace.operator_catalog()

    def op_assert_type(self, node_iri: str, class_iri: str) -> dict:
        blocked = self._guard_mutation_node(node_iri=node_iri)
        if blocked is not None:
            return blocked
        out = self.workspace.op_assert_type(node_iri=node_iri, class_iri=class_iri)
        self._record_mutation(out)
        return out

    def op_set_single_literal(self, node_iri: str, prop_iri: str, value: str) -> dict:
        blocked = self._guard_mutation_node(node_iri=node_iri)
        if blocked is not None:
            return blocked
        out = self.workspace.op_set_single_literal(node_iri=node_iri, prop_iri=prop_iri, value=value)
        self._record_mutation(out)
        return out

    def op_set_single_iri(self, node_iri: str, prop_iri: str, value_iri: str) -> dict:
        blocked = self._guard_mutation_node(node_iri=node_iri)
        if blocked is not None:
            return blocked
        out = self.workspace.op_set_single_iri(node_iri=node_iri, prop_iri=prop_iri, value_iri=value_iri)
        self._record_mutation(out)
        return out

    def op_add_literal(self, node_iri: str, prop_iri: str, value: str) -> dict:
        blocked = self._guard_mutation_node(node_iri=node_iri)
        if blocked is not None:
            return blocked
        out = self.workspace.op_add_literal(node_iri=node_iri, prop_iri=prop_iri, value=value)
        self._record_mutation(out)
        return out

    def op_add_iri_link(self, node_iri: str, prop_iri: str, value_iri: str) -> dict:
        blocked = self._guard_mutation_node(node_iri=node_iri)
        if blocked is not None:
            return blocked
        out = self.workspace.op_add_iri_link(node_iri=node_iri, prop_iri=prop_iri, value_iri=value_iri)
        self._record_mutation(out)
        return out

    def op_remove_literal(self, node_iri: str, prop_iri: str, value: str) -> dict:
        blocked = self._guard_mutation_node(node_iri=node_iri)
        if blocked is not None:
            return blocked
        out = self.workspace.op_remove_literal(node_iri=node_iri, prop_iri=prop_iri, value=value)
        self._record_mutation(out)
        return out

    def op_remove_iri_link(self, node_iri: str, prop_iri: str, value_iri: str) -> dict:
        blocked = self._guard_mutation_node(node_iri=node_iri)
        if blocked is not None:
            return blocked
        out = self.workspace.op_remove_iri_link(node_iri=node_iri, prop_iri=prop_iri, value_iri=value_iri)
        self._record_mutation(out)
        return out

    def op_ensure_mincount_links(
        self,
        node_iri: str,
        prop_iri: str,
        target_class_iri: str,
        n: int,
        prefix: str = "http://la3d.local/agent/generated/",
    ) -> dict:
        blocked = self._guard_mutation_node(node_iri=node_iri)
        if blocked is not None:
            return blocked
        out = self.workspace.op_ensure_mincount_links(
            node_iri=node_iri,
            prop_iri=prop_iri,
            target_class_iri=target_class_iri,
            n=n,
            prefix=prefix,
        )
        self._record_mutation(out)
        return out

    def op_normalize_cardinality(self, node_iri: str, prop_iri: str, keep_value: str = "") -> dict:
        blocked = self._guard_mutation_node(node_iri=node_iri)
        if blocked is not None:
            return blocked
        out = self.workspace.op_normalize_cardinality(
            node_iri=node_iri,
            prop_iri=prop_iri,
            keep_value=keep_value,
        )
        self._record_mutation(out)
        return out

    def op_profile_closure(
        self,
        profile_iri: str,
        resource_count: int = 2,
        resource_prefix: str = "http://la3d.local/agent/generated/resource",
    ) -> dict:
        blocked = self._guard_mutation_node(node_iri=profile_iri)
        if blocked is not None:
            return blocked
        out = self.workspace.op_profile_closure(
            profile_iri=profile_iri,
            resource_count=resource_count,
            resource_prefix=resource_prefix,
        )
        self._record_mutation(out)
        return out

    def graph_snapshot(self, label: str = "working") -> dict:
        return self.workspace.snapshot(store=self.store, label=label)

    def as_tools(self) -> list:
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
            self.ontology_stats,
            self.ontology_node_outgoing,
            self.ontology_node_incoming,
            self.ontology_validate,
            self.ontology_validate_preview,
            self.ontology_signature_index,
            self.ontology_validate_focus,
            self.cq_list,
            self.cq_details,
            self.cq_query_symbols,
            self.cq_anchor_nodes,
            self.cq_node_allowed,
            self.cq_query_read_window,
            self.cq_eval,
            self.operator_catalog,
            self.op_assert_type,
            self.op_set_single_literal,
            self.op_set_single_iri,
            self.op_add_literal,
            self.op_add_iri_link,
            self.op_remove_literal,
            self.op_remove_iri_link,
            self.op_ensure_mincount_links,
            self.op_normalize_cardinality,
            self.op_profile_closure,
            self.graph_snapshot,
        ]

    def _guard_mutation_node(self, node_iri: str) -> Optional[dict]:
        if not self.current_cq_id:
            return None
        verdict = self.workspace.node_allowed_for_cq(self.current_cq_id, node_iri=node_iri)
        if verdict.get("error"):
            return verdict
        if verdict.get("allowed"):
            return None
        return {
            "error": "node_not_allowed_for_current_cq",
            "current_cq_id": self.current_cq_id,
            "node": node_iri,
            "anchors": verdict.get("anchors", []),
            "allowed_node_prefixes": verdict.get("allowed_node_prefixes", []),
            "suggestion": "Use cq_anchor_nodes and cq_query_symbols to select an allowed node.",
        }

    def _record_mutation(self, result: dict) -> None:
        if result.get("error"):
            return
        self._graph_revision += 1
        self._validations_without_delta = 0

    def _guard_validation_budget(self) -> Optional[dict]:
        if self._last_validation_revision == self._graph_revision:
            self._validations_without_delta += 1
        else:
            self._validations_without_delta = 0
        self._last_validation_revision = self._graph_revision
        if self._validations_without_delta <= self._max_validations_without_delta:
            return None
        return {
            "error": "validation_without_graph_delta",
            "graph_revision": self._graph_revision,
            "validations_without_delta": self._validations_without_delta,
            "max_validations_without_delta": self._max_validations_without_delta,
            "suggestion": "Apply an operator delta before validating again.",
        }

    @staticmethod
    def _extract_ref_key(ref_or_key: dict | str) -> str:
        if isinstance(ref_or_key, dict):
            return str(ref_or_key.get("key", ""))
        return str(ref_or_key)

    @staticmethod
    def _extract_ref_kind(ref_or_key: dict | str) -> str:
        if isinstance(ref_or_key, dict):
            return str(ref_or_key.get("kind", ""))
        key = str(ref_or_key)
        if "_" in key:
            return "_".join(key.split("_")[:-1])
        return ""

    def _guard_cq_mismatch(self, cq_id: str) -> Optional[dict]:
        if not self.current_cq_id:
            return None
        if cq_id == self.current_cq_id:
            return None
        return {
            "error": "cq_scope_violation",
            "current_cq_id": self.current_cq_id,
            "requested_cq_id": cq_id,
            "suggestion": "Use the current CQ only in this run context.",
        }

    def _annotate_validation_result(self, result: dict) -> dict:
        if result.get("error"):
            return result
        current: dict[str, int] = {}
        for entry in result.get("top_signatures", []):
            signature = str(entry.get("signature", ""))
            if not signature:
                continue
            current[signature] = int(entry.get("count", 0))
        deltas = []
        for signature in sorted(set(self._last_signature_counts) | set(current)):
            before = self._last_signature_counts.get(signature, 0)
            after = current.get(signature, 0)
            if before == after:
                continue
            deltas.append(
                {
                    "signature": signature,
                    "before": before,
                    "after": after,
                    "delta": after - before,
                }
            )
        deltas.sort(key=lambda row: abs(int(row["delta"])), reverse=True)
        result["signature_deltas"] = deltas[:10]
        result["signature_delta_summary"] = {
            "changed_signatures": len(deltas),
            "before_total": sum(self._last_signature_counts.values()),
            "after_total": sum(current.values()),
        }
        self._last_signature_counts = current
        return result
