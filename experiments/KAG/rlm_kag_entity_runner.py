"""DSPy RLM runner for KAG entity extraction over enriched document graphs.

Loads a pre-built G_doc (Sprint 4 output) as read-only base, then runs an
RLM agent to extract entities, measurements, and claims into G_entity and
G_claim graphs. Ontology knowledge is injected via sense cards in context.

Tool surface: 5 QA read tools + 7 generic write tools = 12 total.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dspy

from experiments.KAG.kag_entity_tools import KagEntityToolset
from experiments.KAG.kag_entity_workspace import KagEntityWorkspace
from experiments.KAG.kag_qa_tools import KagQAToolset
from experiments.KAG.rlm_kag_runner import (
    MAIN_MODEL,
    SUB_MODEL,
    JsonlTrajectoryLogger,
    LeakageMetrics,
    _extract_lm_usage,
    _preview,
    _wrap_tools_with_logging,
)
from experiments.reasoningbank.prototype.tools.dspy_patches import apply_all_patches


# ── Sense cards ──────────────────────────────────────────────────────

SIO_SENSE_CARD = """\
## SIO Entity Types (use with op_create_entity / op_assert_type)
- sio:ChemicalEntity — molecules, compounds, reagents, drugs
- sio:Molecule — specific molecular species (subclass of ChemicalEntity)
- sio:Protein — proteins, antibodies (subclass of Molecule)
- sio:MaterialEntity — physical materials, samples, substrates
- sio:Process — reactions, measurements, procedures, syntheses
- sio:Attribute — properties: mass, temperature, solubility
- sio:MeasuredValue — quantitative observations with numeric value + unit
- sio:Proposition — claims about entities (use in G_claim)
- sio:Evidence — supporting/refuting evidence for propositions (use in G_claim)

## SIO Properties (use with op_add_link / op_set_link)
- sio:has-attribute (entity -> attribute)
- sio:has-measurement-value (entity -> MeasuredValue)
- sio:has-participant (process -> entity)
- sio:has-part / sio:is-part-of (whole-part)
- sio:is-about (proposition -> entity, in G_claim)
- sio:has-evidence / sio:is-evidence-for (proposition <-> evidence, in G_claim)
- sio:refers-to (information entity -> entity)
"""

QUDT_SENSE_CARD = """\
## QUDT Pattern (measurements)
Every measurement is a qudt:QuantityValue or sio:MeasuredValue with:
  qudt:numericValue "1.637"^^xsd:double
  qudt:unit unit:ANGSTROM
  qudt:hasQuantityKind quantitykind:BondLength  (optional)

## Common Quantity Kinds
quantitykind:BondLength, quantitykind:Temperature, quantitykind:Mass,
quantitykind:AmountOfSubstanceConcentration, quantitykind:ActivationEnergy,
quantitykind:EquilibriumConstant, quantitykind:DissociationConstant,
quantitykind:Radioactivity, quantitykind:Time, quantitykind:Energy

## Common Units
unit:ANGSTROM, unit:NanoM, unit:DEG_C, unit:K, unit:MOL-PER-L,
unit:NanoMOL-PER-L, unit:KiloJ-PER-MOL, unit:KiloCAL-PER-MOL,
unit:EV, unit:GM-PER-MOL, unit:KiloGM-PER-MOL, unit:SEC, unit:MIN,
unit:MegaBQ, unit:GigaBQ, unit:PERCENT, unit:L-PER-MOL
"""

PROV_SENSE_CARD = """\
## Provenance (PROV + CiTO)
- prov:wasDerivedFrom — REQUIRED on every entity and claim.
  Links to a G_doc block IRI (e.g., 'ex:b_p003_0005') as provenance anchor.
  Every entity/claim MUST have at least one prov:wasDerivedFrom.
- cito:cites — links a claim to a bibliography entry in G_doc.
"""


def _build_entity_context(
    workspace: KagEntityWorkspace,
    qa_toolset: KagQAToolset,
) -> str:
    """Assemble entity extraction context: G_doc overview + sense cards."""
    graph_context = qa_toolset.build_context()
    stats = workspace.stats()
    doc_stats = stats["doc"]

    lines = [
        graph_context,
        "",
        f"## G_doc Stats: {doc_stats['triples']} triples",
        "",
        SIO_SENSE_CARD,
        QUDT_SENSE_CARD,
        PROV_SENSE_CARD,
    ]
    return "\n".join(lines)


def _build_entity_task() -> str:
    """Task prompt for entity extraction agent."""
    return (
        "Extract key entities, measurements, and claims from the document graph.\n"
        "\n"
        "## Graph Architecture\n"
        "You have access to THREE graph layers:\n"
        "- G_doc (read-only): document structure. Use g_search, g_section_content,\n"
        "  g_node_detail, g_figure_info, g_node_refs to navigate.\n"
        "- G_entity (writable): extracted entities + measurements.\n"
        "  Write with: op_create_entity, op_set_literal, op_add_link (graph='entity')\n"
        "- G_claim (writable): scientific claims + evidence.\n"
        "  Write with: op_create_entity, op_set_literal, op_add_link (graph='claim')\n"
        "\n"
        "## Extraction Strategy\n"
        "1. Search G_doc for key entities: chemical compounds, proteins, materials\n"
        "2. For each entity found:\n"
        "   a. op_create_entity('ex:name_NN', 'sio:ChemicalEntity', graph='entity')\n"
        "   b. op_set_literal('ex:name_NN', 'rdfs:label', 'compound name')\n"
        "   c. op_add_link('ex:name_NN', 'prov:wasDerivedFrom', 'ex:b_pNNN_NNNN')\n"
        "3. For measurements (bond lengths, temperatures, concentrations, K_D, etc.):\n"
        "   a. op_create_entity('ex:meas_NN', 'sio:MeasuredValue', graph='entity')\n"
        "   b. op_set_literal('ex:meas_NN', 'rdfs:label', 'ΔG at 298K for compound X')\n"
        "   c. op_set_literal('ex:meas_NN', 'qudt:numericValue', '1.637', 'xsd:double')\n"
        "   d. op_set_link('ex:meas_NN', 'qudt:unit', 'unit:ANGSTROM')  ← MUST use op_set_link (IRI)\n"
        "   e. op_add_link('ex:meas_NN', 'prov:wasDerivedFrom', 'ex:b_pNNN_NNNN')\n"
        "   f. op_add_link('ex:entity_NN', 'sio:has-measurement-value', 'ex:meas_NN')\n"
        "4. For claims (key findings, conclusions):\n"
        "   a. op_create_entity('ex:claim_NN', 'sio:Proposition', graph='claim')\n"
        "   b. op_set_literal('ex:claim_NN', 'rdfs:label', 'claim text', graph='claim')\n"
        "   c. op_add_link('ex:claim_NN', 'sio:is-about', 'ex:entity_NN', graph='claim')\n"
        "   d. op_add_link('ex:claim_NN', 'prov:wasDerivedFrom', 'ex:b_pNNN_NNNN', graph='claim')\n"
        "\n"
        "## SHACL Rules (enforced by validate_graph)\n"
        "- Every entity MUST have rdfs:label + prov:wasDerivedFrom (including MeasuredValue!)\n"
        "- Every MeasuredValue MUST ALSO have qudt:numericValue + qudt:unit + rdfs:label\n"
        "  (label the measurement, e.g. 'C-CN bond length' or 'equilibrium constant Keq')\n"
        "- qudt:unit MUST be an IRI, NEVER a literal string.\n"
        "  CORRECT: op_set_link(mv_iri, 'qudt:unit', 'unit:KiloCAL-PER-MOL')\n"
        "  WRONG:   op_set_literal(mv_iri, 'qudt:unit', 'kcal/mol')  ← will fail SHACL\n"
        "- Every Proposition MUST have rdfs:label + sio:is-about + prov:wasDerivedFrom\n"
        "- Every Evidence MUST have rdfs:label + sio:is-evidence-for + prov:wasDerivedFrom\n"
        "\n"
        "## IRI Format (CRITICAL)\n"
        "ALL node IRIs must use the 'ex:' prefix. ALL property/class IRIs must use\n"
        "their namespace prefix (sio:, qudt:, prov:, rdfs:, unit:, quantitykind:).\n"
        "NEVER pass bare strings like 'TCNE' — always 'ex:tcne_01'.\n"
        "NEVER use sio:has-attribute with literal strings — use rdfs:label for names.\n"
        "\n"
        "## Naming Convention\n"
        "Use descriptive entity IDs with ex: prefix: 'ex:tcne', 'ex:bond_tcne_cn', 'ex:keq_tmannbu'.\n"
        "Measurement IDs: 'ex:meas_bondlen_01', 'ex:meas_temp_01'.\n"
        "Claim IDs: 'ex:claim_01', 'ex:evidence_01'.\n"
        "\n"
        "## Completion Protocol\n"
        "When done extracting, call: finalize_graph('summary of extracted entities')\n"
        "- If status='READY': all graphs conform. Call SUBMIT(answer='summary')\n"
        "- If status='NOT_READY': fix violations, then call finalize_graph again\n"
        "Do NOT call SUBMIT directly — always go through finalize_graph first.\n"
        "You may call validate_graph() mid-extraction for progress checks.\n"
        "\n"
        "## Goal\n"
        "Extract the most important entities (chemicals, proteins, materials),\n"
        "key measurements (with values and units), and central claims.\n"
        "Ground every assertion to a G_doc block via prov:wasDerivedFrom.\n"
        "Focus on quality over quantity — 5-15 well-grounded entities are better\n"
        "than 50 poorly grounded ones.\n"
    )


def run_rlm_kag_entity(
    graph_dir: str,
    out_dir: str = "experiments/KAG/results",
    run_name: str = "kag_entity",
    model: str = MAIN_MODEL,
    sub_model: str = SUB_MODEL,
    max_iters: int = 20,
    max_calls: int = 50,
) -> dict[str, Any]:
    """Run DSPy RLM agent to extract entities from an enriched KAG graph."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Set ANTHROPIC_API_KEY for live RLM runs.")

    apply_all_patches()
    dspy.configure(lm=dspy.LM(model, api_key=api_key, temperature=0.0))

    graph_path = Path(graph_dir)
    ttl_path = graph_path / "knowledge_graph.ttl"
    content_store_path = graph_path / "content_store.jsonl"
    if not ttl_path.exists():
        raise ValueError(f"knowledge_graph.ttl not found in {graph_path}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{run_name}_{ts}"
    run_out = Path(out_dir) / run_id
    run_out.mkdir(parents=True, exist_ok=True)

    logger = JsonlTrajectoryLogger(run_out / "trajectory.jsonl")
    leakage = LeakageMetrics()
    operator_counts: dict[str, int] = {}

    # Build workspace and toolset
    ws = KagEntityWorkspace(
        str(ttl_path),
        str(content_store_path) if content_store_path.exists() else None,
    )
    qa = KagQAToolset(str(ttl_path), str(content_store_path))
    toolset = KagEntityToolset(ws, qa)

    logger.log("run_start", {
        "run_id": run_id,
        "graph_dir": str(graph_path),
        "model": model,
        "sub_model": sub_model,
        "max_iters": max_iters,
        "max_calls": max_calls,
        "doc_stats": ws.stats()["doc"],
    })

    # Build context and task
    context = _build_entity_context(ws, qa)
    task = _build_entity_task()

    # Build tool dict for logging wrapper
    tool_dict = {t.__name__: t for t in toolset.as_tools()}
    wrapped_dict = _wrap_tools_with_logging(
        raw_tools=tool_dict,
        logger=logger,
        run_id=run_id,
        leakage=leakage,
        operator_counts=operator_counts,
    )
    wrapped_tools = list(wrapped_dict.values())

    # Sub-LM for code execution
    sub_lm = dspy.LM(sub_model, api_key=api_key, temperature=0.0)

    # DSPy RLM — context includes G_doc overview + sense cards
    rlm = dspy.RLM(
        "context, task -> answer",
        tools=wrapped_tools,
        max_iterations=max_iters,
        max_llm_calls=max_calls,
        max_output_chars=10000,
        sub_lm=sub_lm,
    )

    logger.log("iteration", {
        "run_id": run_id,
        "phase": "rlm_start",
        "context_length": len(context),
        "task_length": len(task),
    })

    history_before = len(dspy.settings.lm.history) if hasattr(dspy.settings.lm, "history") else 0
    out = rlm(context=context, task=task)
    history_after = len(dspy.settings.lm.history) if hasattr(dspy.settings.lm, "history") else history_before

    lm_usage = _extract_lm_usage(history_before, history_after)

    # Extract trajectory
    trajectory = getattr(out, "trajectory", None)
    iteration_count = len(trajectory) if trajectory else 0

    # Log trajectory entries with error classification
    sandbox_crashes = 0
    tool_binding_errors = 0
    if trajectory:
        for idx, entry in enumerate(trajectory):
            reasoning = (entry.get("reasoning", "") if isinstance(entry, dict)
                         else getattr(entry, "reasoning", "")) or ""
            code = (entry.get("code", "") if isinstance(entry, dict)
                    else getattr(entry, "code", "")) or ""
            output = (entry.get("output", "") if isinstance(entry, dict)
                      else getattr(entry, "output", "")) or ""
            output_str = str(output)[:2000]
            has_error = "[Error]" in output_str
            error_type = None
            if has_error:
                if "NameError" in output_str or "is not defined" in output_str:
                    error_type = "tool_binding_lost"
                    tool_binding_errors += 1
                elif "Unhandled async error" in output_str:
                    error_type = "sandbox_crash"
                    sandbox_crashes += 1
                elif "TypeError" in output_str:
                    error_type = "type_error"
                else:
                    error_type = "unknown"
            logger.log("iteration", {
                "run_id": run_id,
                "iteration": idx + 1,
                "reasoning": str(reasoning)[:2000],
                "code": str(code)[:4000],
                "output": output_str,
                "has_error": has_error,
                "error_type": error_type,
            })

    # Validate final state
    validation = ws.validate_graph("all")

    # Serialize entity and claim graphs
    graph_paths = ws.serialize(str(run_out))

    # Build summary
    final_stats = ws.stats()
    summary = {
        "run_id": run_id,
        "graph_dir": str(graph_path),
        "out_dir": str(run_out),
        "answer": str(getattr(out, "answer", "")),
        "validation": validation,
        "stats": final_stats,
        "iterations": iteration_count,
        "operator_counts": operator_counts,
        "lm_usage": lm_usage,
        "leakage": {
            "stdout_chars": leakage.stdout_chars,
            "large_returns": leakage.large_returns,
        },
        "errors": {
            "sandbox_crashes": sandbox_crashes,
            "tool_binding_errors": tool_binding_errors,
        },
        "artifacts": {
            "trajectory_jsonl": str(run_out / "trajectory.jsonl"),
            "summary_json": str(run_out / "summary.json"),
            **{f"g_{k}_ttl": v for k, v in graph_paths.items()},
        },
    }

    summary_path = run_out / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    logger.log("run_complete", {
        "run_id": run_id,
        "conforms": validation.get("conforms", False),
        "entity_triples": final_stats["entity"]["triples"],
        "claim_triples": final_stats["claim"]["triples"],
        "iterations": iteration_count,
        "total_cost": lm_usage.get("total_cost", 0.0),
        "sandbox_crashes": sandbox_crashes,
        "tool_binding_errors": tool_binding_errors,
    })

    return summary
