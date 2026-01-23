#!/usr/bin/env bash
# Benchmark: Simple vs Complex Query Performance
#
# Compare timing for:
# 1. Simple query (should be fast, like user's 30-40s test)
# 2. Complex query (may need exploration)

set -e

# Activate environment
source ~/uvws/.venv/bin/activate

echo "==================================================="
echo "Performance Benchmark: Simple vs Complex Queries"
echo "==================================================="
echo ""

# Create benchmark directory
BENCHMARK_DIR="evals/benchmarks/$(date +%Y%m%d_%H%M%S)_simple_vs_complex"
mkdir -p "$BENCHMARK_DIR"

echo "Results will be saved to: $BENCHMARK_DIR"
echo ""

# Simple query: Just ask for E. coli K12 taxon information
# Should be answerable with 1-2 iterations if working efficiently
echo "1. Running SIMPLE query (bacteria taxa)..."
echo "   Expected: 1-2 iterations, <1 minute"
echo ""

time python -m evals.cli run 'uniprot/taxonomy/uniprot_bacteria_taxa_001' \
  --trials 1 \
  --output "$BENCHMARK_DIR/simple" \
  --enable-trajectory-logging \
  --trajectory-dir "$BENCHMARK_DIR/trajectories" \
  2>&1 | tee "$BENCHMARK_DIR/simple_run.log"

echo ""
echo "2. Running COMPLEX query (E. coli K12 sequences)..."
echo "   Expected: Multiple iterations for exploration"
echo ""

time python -m evals.cli run 'uniprot/taxonomy/uniprot_ecoli_k12_sequences_001' \
  --trials 1 \
  --output "$BENCHMARK_DIR/complex" \
  --enable-trajectory-logging \
  --trajectory-dir "$BENCHMARK_DIR/trajectories" \
  2>&1 | tee "$BENCHMARK_DIR/complex_run.log"

echo ""
echo "==================================================="
echo "Benchmark Complete - Analyzing Timing..."
echo "==================================================="
echo ""

# Analyze trajectory logs
echo "SIMPLE QUERY TIMING:"
echo "===================="
for traj in "$BENCHMARK_DIR/trajectories"/*bacteria_taxa*.jsonl; do
    if [ -f "$traj" ]; then
        python evals/scripts/profile_timing.py "$traj"
    fi
done

echo ""
echo ""
echo "COMPLEX QUERY TIMING:"
echo "====================="
for traj in "$BENCHMARK_DIR/trajectories"/*ecoli_k12*.jsonl; do
    if [ -f "$traj" ]; then
        python evals/scripts/profile_timing.py "$traj"
    fi
done

echo ""
echo "==================================================="
echo "Results saved in: $BENCHMARK_DIR"
echo "==================================================="
