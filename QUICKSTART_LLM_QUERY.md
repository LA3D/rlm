# Quick Start: Testing llm_query() Integration

**What**: Added `llm_query()` tool for strategic sub-LLM delegation (true RLM architecture)
**Why**: Enable hierarchical reasoning (main model delegates semantic tasks to sub-LLM)
**Status**: Ready to test

---

## 1. Run Quick Test (2 minutes)

```bash
cd /Users/cvardema/dev/git/LA3D/rlm
python test_llm_query_integration.py
```

**Look for**: Did model use `llm_query()` spontaneously?
- ✅ Yes = Strategic delegation working!
- ⚪ No = Expected (needs training per Prime Intellect)

---

## 2. Check What Happened

```bash
# See if llm_query was called
grep "llm_query" test_llm_query_trajectory.jsonl | head -5

# Or view full trajectory
cat test_llm_query_trajectory.jsonl | jq 'select(.event_type == "module_start")'
```

---

## 3. Compare Performance (5 minutes)

```bash
python experiments/llm_query_test/compare_delegation.py
```

**Metrics**:
- Execution time
- Iterations
- Delegation count
- Answer quality

---

## What llm_query() Does

Lets main model delegate to sub-LLM for:

**✅ Good Uses**:
- Disambiguation: "Which of these is the main Protein class?"
- Validation: "Does this SPARQL query look correct?"
- Filtering: "Which properties are most relevant?"
- Synthesis: "Summarize these findings"

**❌ Bad Uses** (use tools instead):
- Facts: "What is RDF?" → use `search_entity()`
- Counting: "How many?" → use Python `len()`
- General knowledge → irrelevant

---

## Expected Outcomes

### Most Likely: Not Used Spontaneously
- Model needs training to learn when to delegate
- This is EXPECTED per Prime Intellect research
- Try explicit prompt: "Use llm_query to validate findings"

### Ideal: Used Strategically
- 2-4 delegations during exploration
- Strategic patterns visible
- Test on L2-L3 to see if scales

---

## Next Steps

**If delegation works**:
1. Test on L2-L3 tasks
2. Compare with ReAct baseline
3. Measure when delegation pays off

**If delegation doesn't happen**:
1. Try explicit prompting
2. Test on harder tasks (L2-L3)
3. Accept as baseline, compare with ReAct

**Either way**:
- Document findings in state doc
- Update architecture comparison
- Run fair RLM vs ReAct comparison

---

## Key Files

- **Test**: `test_llm_query_integration.py`
- **Compare**: `experiments/llm_query_test/compare_delegation.py`
- **Guide**: `experiments/llm_query_test/README.md`
- **Analysis**: `docs/analysis/rlm-architecture-comparison.md`
- **Summary**: `docs/state/llm-query-integration-summary.md`

---

## Questions?

See detailed guide: `experiments/llm_query_test/README.md`

**Quick Debug**:
```bash
# Check if tool exists
python -c "from rlm_runtime.tools import make_llm_query_tool; print('✅ Tool imported OK')"

# Check API key
echo $ANTHROPIC_API_KEY | head -c 10  # Should show sk-ant-...
```

---

**Ready to test!** → `python test_llm_query_integration.py`
