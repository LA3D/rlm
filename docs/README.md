# RLM Documentation

This directory contains design documents, implementation guides, and project planning materials for the RLM (Recursive Language Models) + RDF/SPARQL integration project.

## Quick Navigation

### 📋 Planning Documents
Start here to understand the project vision and approach.

- **[trajectory.md](planning/trajectory.md)** - Master plan for RLM + Ontologies integration (THE source of truth)
- **[approach.md](planning/approach.md)** - Overall development approach and philosophy

### 🏗️ Design Documents
Architecture decisions and design patterns.

- **[progressive-disclosure.md](design/progressive-disclosure.md)** - Core context engineering pattern for RLMs
- **[ontology-patterns.md](design/ontology-patterns.md)** - Ontology design patterns for navigation
- **[ontology-affordances.md](design/ontology-affordances.md)** - How RDF/OWL/SHACL enable progressive disclosure
- **[shacl-integration.md](design/shacl-integration.md)** - SHACL integration architecture
- **[annotation-indexing.md](design/annotation-indexing.md)** - Annotation indexing design

### 📚 Usage Guides
How to use the implemented features.

- **[dataset-memory.md](guides/dataset-memory.md)** - Using RDF Dataset-based session memory
- **[testing.md](guides/testing.md)** - Step-by-step testing guide

### 📝 Task Documents
Specific implementation tasks and summaries (numbered series).

- **[00-core-alignment.md](tasks/00-core-alignment.md)** - Aligning `00_core.ipynb` with rlmpaper protocol
- **[04-shacl-summary.md](tasks/04-shacl-summary.md)** - Stage 4 SHACL implementation summary

### 📖 Reference Materials
Supporting documentation and comparisons.

- **[implementations.md](reference/implementations.md)** - Comparison of RLM implementations
- **[eval-framework.md](reference/eval-framework.md)** - Evaluation framework design

### 🗄️ Archive
Historical materials, session notes, and blog drafts.

- **[sessions/](archive/sessions/)** - Session summaries and completion reports
- **[blog-drafts/](archive/blog-drafts/)** - Blog post drafts
- **[testing/](archive/testing/)** - Historical testing documentation

## Project Structure

```
rlm/
├── nbs/                    # nbdev notebooks (source of truth for code)
├── rlm/                    # Generated Python library (auto-generated)
├── docs/                   # ← You are here
│   ├── planning/           # Strategic planning documents
│   ├── design/             # Architecture and patterns
│   ├── guides/             # Usage documentation
│   ├── tasks/              # Implementation tasks
│   ├── reference/          # Supporting materials
│   └── archive/            # Historical content
├── tests/                  # Test suite
├── ontology/               # RDF/OWL ontologies
└── rlmpaper/               # Reference implementation (git submodule)
```

## Key Concepts

### RLM (Recursive Language Models)
An architecture where:
- Large context lives in the execution environment (REPL), not in the LLM context
- The root LLM iteratively emits small REPL actions
- Heavy reading/summarization is delegated to sub-LLMs
- System converges by returning `FINAL(...)` or `FINAL_VAR(...)`

### Progressive Disclosure
A context engineering pattern where agents:
- Incrementally discover relevant context through exploration
- Maintain lightweight references, fetch dynamically during execution
- Use high-signal metadata (counts, summaries) to guide navigation
- Avoid loading everything upfront

### Bounded Views
Functions that return limited, contextual slices of data:
- `res_head(results, 10)` - First 10 rows
- `res_where(results, 'name', pattern='Alice')` - Filtered rows
- `res_group(results, 'category')` - Aggregated counts
- `describe_shape(index, shape_uri, limit=10)` - SHACL shape preview

## Implementation Stages

The project follows a staged implementation approach (see [trajectory.md](planning/trajectory.md) for details):

1. **Stage 1** - Core RLM with claudette backend
2. **Stage 1.5** - Fuller integration with Solveit
3. **Stage 2** - Bounded view primitives
4. **Stage 2.5** - Procedural memory loop
5. **Stage 3** - SPARQL handles and work-bound queries
6. **Stage 4** - SHACL as retrieval scaffolding ✓ **COMPLETE**
7. **Stage 5** - Full trajectory with ontology affordances (future)
8. **Stage 6** - Evaluation framework (future)

## Documentation Philosophy

This project follows a **documentation-driven** approach:

1. Design documents capture architectural decisions before implementation
2. Task documents guide specific implementations
3. Notebooks serve as literate programming (code + inline docs)
4. Usage guides help users understand how to use features
5. Archives preserve historical context without cluttering active docs

## Contributing

When adding new documentation:

1. **Planning docs** - Only add if proposing major architectural changes
2. **Design docs** - Add when making significant design decisions
3. **Task docs** - Create for each implementation stage or major feature
4. **Guides** - Add when users need practical how-to documentation
5. **Archive** - Move completed session notes and outdated content here

Keep documentation:
- **Concise** - Remove redundancy, focus on key information
- **Actionable** - Include concrete examples and code snippets
- **Current** - Archive or update outdated content
- **Cross-referenced** - Link to related documents

## External Resources

- [rlmpaper repository](https://github.com/alexzhang13/rlm) - Reference implementation
- [nbdev documentation](https://nbdev.fast.ai/) - Literate programming framework
- [claudette documentation](https://claudette.answer.ai/) - Claude API wrapper
- [Anthropic: Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [fast.ai style guide](https://docs.fast.ai/dev/style.html) - Code conventions

## Questions?

- For project overview: Start with [trajectory.md](planning/trajectory.md)
- For architecture decisions: Check [design/](design/)
- For usage help: See [guides/](guides/)
- For implementation details: See [tasks/](tasks/)
- For code examples: See notebooks in `nbs/`
