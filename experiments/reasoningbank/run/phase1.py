"""Phase 1: Closed-Loop Learning (E9-E12).

ReasoningBank proper: retrieve → run → judge → extract → persist.

- E9: Judge + extract (append-only)
- E10: Add consolidation (merge/supersede)
- E11: Add forgetting (bounded bank)
- E12: MaTTS rollouts (N rollouts, select best, contrastive extraction)
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import dspy
from experiments.reasoningbank.core.mem import MemStore, Item
from experiments.reasoningbank.run.rlm import run, Result
from experiments.reasoningbank.ctx.builder import Cfg, Layer

def judge(res:Result) -> dict:
    "Simple LLM-based judgment of trajectory success."
    if not res.converged:
        return {'success': False, 'reason': 'Did not converge'}

    # Use dspy for judgment
    judge_fn = dspy.Predict("answer, sparql -> is_success: bool, reason: str")
    try:
        j = judge_fn(answer=res.answer, sparql=res.sparql or "")
        return {'success': j.is_success, 'reason': j.reason}
    except Exception as e:
        return {'success': False, 'reason': f'Judgment failed: {e}'}

def extract(res:Result, judgment:dict, task:str) -> list[Item]:
    "Extract procedures from successful trajectory."
    if not judgment['success']: return []

    # Use dspy for extraction
    ext = dspy.Predict("task, answer, sparql -> title, procedure")
    try:
        e = ext(task=task, answer=res.answer, sparql=res.sparql or "")
        item = Item(
            id=Item.make_id(e.title, e.procedure),
            title=e.title[:100],  # Cap at 10 words ~= 100 chars
            desc=f"Procedure for: {task[:50]}",
            content=e.procedure,
            src='success',
            tags=[],
        )
        return [item]
    except Exception as ex:
        print(f"  Extraction failed: {ex}")
        return []

def run_closed_loop(
    tasks:list[dict],
    ont:str,
    mem:MemStore,
    do_extract:bool=True,
    consolidate:bool=False,
):
    "Run E9-E12 closed-loop learning."
    cfg = Cfg(l2=Layer(True, 2000))

    for t in tasks:
        print(f"\nTask: {t['id']}")
        res = run(t['query'], ont, cfg, mem)

        j = judge(res)
        status = '✓' if j['success'] else '✗'
        print(f"  {status} Result: {j['reason'][:60]}")

        if do_extract:
            items = extract(res, j, t['query'])
            for item in items:
                if consolidate:
                    # TODO: Check for duplicates/superseding
                    pass
                mem.add(item)
                print(f"  Extracted: {item.title[:60]}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Run Phase 1 closed-loop experiments')
    parser.add_argument('--ont', default='ontology/prov.ttl', help='Ontology path')
    parser.add_argument('--extract', action='store_true', help='Enable extraction')
    parser.add_argument('--consolidate', action='store_true', help='Enable consolidation')
    args = parser.parse_args()

    # Initialize memory
    mem = MemStore()

    # Test tasks
    tasks = [
        {'id': 'entity_lookup', 'query': 'What is Activity?'},
        {'id': 'property_find', 'query': 'What properties does Activity have?'},
        {'id': 'hierarchy', 'query': 'What are the subclasses of Entity?'},
    ]

    run_closed_loop(tasks, args.ont, mem, args.extract, args.consolidate)

    # Save memory
    if args.extract:
        mem.save('experiments/reasoningbank/results/phase1_memory.json')
        print(f"\nMemory saved: {len(mem.all())} items")
