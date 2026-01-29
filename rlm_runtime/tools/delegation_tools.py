"""Sub-LLM delegation tools for strategic reasoning.

Implements llm_query() for delegating semantic analysis and strategic
decisions to a smaller, faster model during RLM exploration.

Based on Prime Intellect RLM architecture where sub-LLMs handle
verbose semantic tasks while main model stays strategic.
"""

from typing import Any


def make_llm_query_tool(sub_lm: Any) -> callable:
    """Create llm_query tool for strategic sub-LLM delegation.

    Args:
        sub_lm: DSPy LM instance for sub-model

    Returns:
        Callable llm_query function for use in RLM namespace

    Examples:
        # Disambiguation during search
        best = llm_query("Which of these is the main Protein class?", str(results))

        # Query validation before execution
        is_valid = llm_query("Does this SPARQL look correct?", query)

        # Result filtering
        relevant = llm_query("Which properties are most important?", str(props))

        # Synthesis
        answer = llm_query("Summarize findings", str(evidence))
    """

    def llm_query(prompt: str, context: str = "") -> str:
        """Delegate semantic analysis to sub-LLM.

        Use for strategic decisions that require semantic understanding:
        - Disambiguation: "Which of these entities matches?"
        - Validation: "Does this query look correct?"
        - Filtering: "Which results are most relevant?"
        - Synthesis: "Summarize these findings"

        DO NOT use for:
        - Facts that can be found via tools (use search_entity, sparql_select)
        - Simple string operations (use Python)
        - Counting/math (use Python)

        Args:
            prompt: Question or instruction for sub-LLM
            context: Optional context data (results, queries, etc.)

        Returns:
            Sub-LLM response as string

        Examples:
            # Disambiguate search results
            results = search_entity("Protein", limit=5)
            best_match = llm_query(
                "Which of these is the main Protein class (not a specific protein)?",
                context=str(results)
            )

            # Validate SPARQL before execution
            query = "SELECT ?x WHERE { ?x rdf:type up:Protein }"
            validation = llm_query(
                "Does this SPARQL query look correct? Check for common errors.",
                context=query
            )

            # Filter properties by relevance
            props = sparql_select("SELECT ?p ?o WHERE { <Protein> ?p ?o }")
            important = llm_query(
                "Which properties are most important for understanding this class?",
                context=str(props[:20])
            )

            # Synthesize final answer
            evidence = {...}
            answer = llm_query(
                "Write a concise answer explaining what Protein is",
                context=str(evidence)
            )
        """
        # Build full prompt
        if context:
            # Truncate context if too long (prevent token overflow)
            max_context = 4000
            if len(context) > max_context:
                context = context[:max_context] + f"\n...[truncated at {max_context} chars]"

            full_prompt = f"{prompt}\n\nContext:\n{context}"
        else:
            full_prompt = prompt

        # Call sub-LLM
        # DSPy LM returns list of completions, we take first
        try:
            response = sub_lm(full_prompt)
            # Handle both list and string responses
            if isinstance(response, list):
                return response[0] if response else ""
            return str(response)
        except Exception as e:
            return f"[llm_query error: {e}]"

    # Add metadata for documentation
    llm_query.__doc__ = llm_query.__doc__
    llm_query.__name__ = "llm_query"

    return llm_query


def make_llm_batch_tool(sub_lm: Any) -> callable:
    """Create llm_batch tool for parallel sub-LLM delegation.

    This is an advanced feature for processing multiple prompts in parallel.
    Start with llm_query() first before using this.

    Args:
        sub_lm: DSPy LM instance for sub-model

    Returns:
        Callable llm_batch function for use in RLM namespace

    Examples:
        # Parallel analysis of multiple aspects
        results = llm_batch([
            "Which properties link to other classes?",
            "Which properties are for labels/descriptions?",
            "Which properties are deprecated?"
        ], context=str(all_props))

        # Multiple disambiguation questions
        candidates = search_entity("Activity", limit=10)
        analyses = llm_batch([
            "Which is the main Activity class?",
            "Are there subclasses of Activity?",
            "Which are domain-specific activities?"
        ], context=str(candidates))
    """

    def llm_batch(prompts: list[str], context: str = "") -> list[str]:
        """Execute multiple sub-LLM queries in parallel.

        Args:
            prompts: List of prompts to execute
            context: Optional shared context for all prompts

        Returns:
            List of responses (same order as prompts)

        Note:
            Current implementation is sequential. True parallel execution
            would require async DSPy support.
        """
        responses = []
        for prompt in prompts:
            full_prompt = f"{prompt}\n\nContext:\n{context}" if context else prompt
            try:
                response = sub_lm(full_prompt)
                if isinstance(response, list):
                    responses.append(response[0] if response else "")
                else:
                    responses.append(str(response))
            except Exception as e:
                responses.append(f"[error: {e}]")

        return responses

    return llm_batch
