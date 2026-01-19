# Answer Quality Rubric

Evaluate the agent's answer on a scale of 0-10 based on these criteria:

## Criteria

### 1. Correctness (0-3 points)
- **3 points**: All factual claims are accurate and verifiable from the evidence
- **2 points**: Most claims are accurate, minor errors or imprecisions
- **1 point**: Some accurate information mixed with errors
- **0 points**: Mostly incorrect or hallucinated information

### 2. Completeness (0-3 points)
- **3 points**: Fully addresses the question with appropriate depth
- **2 points**: Addresses main aspects but missing some details
- **1 point**: Partially addresses the question
- **0 points**: Does not address the question

### 3. Groundedness (0-2 points)
- **2 points**: All claims are traceable to REPL observations
- **1 point**: Most claims grounded, some may be inferred
- **0 points**: Makes claims without supporting evidence

### 4. Clarity (0-2 points)
- **2 points**: Clear, well-organized, easy to understand
- **1 point**: Understandable but could be clearer
- **0 points**: Confusing or poorly organized

## Scoring

- **8-10**: Excellent - Accurate, complete, grounded, clear
- **6-7**: Good - Minor issues but fundamentally sound
- **4-5**: Acceptable - Some issues but usable
- **2-3**: Poor - Significant issues
- **0-1**: Failure - Incorrect or does not address the question

## Example Evaluation

**Task**: What is prov:InstantaneousEvent?

**Answer**: "InstantaneousEvent is a class in PROV-O representing an event that occurs at a specific instant in time. According to the ontology, it is a subclass of prov:Event. The search_entity() call found the URI http://www.w3.org/ns/prov#InstantaneousEvent."

**Evaluation**:
- Correctness: 3/3 - Accurate description
- Completeness: 2/3 - Could mention more properties
- Groundedness: 2/2 - Cites search_entity result
- Clarity: 2/2 - Clear and organized

**Total**: 9/10 - Excellent
