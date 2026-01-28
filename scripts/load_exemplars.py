#!/usr/bin/env python3
"""Load reasoning chain exemplars into memory backend.

Usage:
    python scripts/load_exemplars.py \\
        --exemplar-dir experiments/reasoning_chain_validation/exemplars \\
        --db-path memory.db \\
        --ontology uniprot

    python scripts/load_exemplars.py \\
        --exemplar-dir experiments/reasoning_chain_validation/exemplars \\
        --db-path memory.db \\
        --ontology uniprot \\
        --pattern "*.md"
"""

import sys
import argparse
from pathlib import Path

# Ensure we're in the project root
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    parser = argparse.ArgumentParser(
        description="Load reasoning chain exemplars into memory backend",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Load all exemplars for UniProt
  python scripts/load_exemplars.py \\
      --exemplar-dir experiments/reasoning_chain_validation/exemplars \\
      --db-path memory.db \\
      --ontology uniprot

  # Load only L1 and L2 exemplars
  python scripts/load_exemplars.py \\
      --exemplar-dir experiments/reasoning_chain_validation/exemplars \\
      --db-path memory.db \\
      --ontology uniprot \\
      --pattern "uniprot_l[12]*.md"

  # Load to in-memory database (testing)
  python scripts/load_exemplars.py \\
      --exemplar-dir experiments/reasoning_chain_validation/exemplars \\
      --db-path ":memory:" \\
      --ontology uniprot
        """
    )

    parser.add_argument(
        '--exemplar-dir',
        required=True,
        type=Path,
        help='Directory containing exemplar .md files'
    )

    parser.add_argument(
        '--db-path',
        required=True,
        help='Path to SQLite database (or ":memory:" for in-memory)'
    )

    parser.add_argument(
        '--ontology',
        required=True,
        help='Ontology name (e.g., "uniprot", "prov", "dul")'
    )

    parser.add_argument(
        '--pattern',
        default='*.md',
        help='Glob pattern for exemplar files (default: "*.md")'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Force reload of exemplars even if they already exist'
    )

    parser.add_argument(
        '--list-only',
        action='store_true',
        help='List exemplars that would be loaded without actually loading them'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show curriculum coverage statistics after loading'
    )

    args = parser.parse_args()

    # Import here to avoid import errors if dependencies not installed
    from rlm_runtime.memory.sqlite_backend import SQLiteMemoryBackend
    from rlm_runtime.memory.exemplar_loader import load_exemplars_from_directory

    # Validate exemplar directory
    if not args.exemplar_dir.exists():
        print(f"Error: Exemplar directory not found: {args.exemplar_dir}", file=sys.stderr)
        sys.exit(1)

    # List matching files
    exemplar_files = sorted(args.exemplar_dir.glob(args.pattern))
    if not exemplar_files:
        print(f"Error: No files matching pattern '{args.pattern}' in {args.exemplar_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(exemplar_files)} exemplar files matching '{args.pattern}':")
    for f in exemplar_files:
        print(f"  - {f.name}")
    print()

    if args.list_only:
        print("List-only mode: exiting without loading.")
        sys.exit(0)

    # Connect to database
    print(f"Connecting to database: {args.db_path}")
    backend = SQLiteMemoryBackend(str(args.db_path))

    # Check for existing exemplars
    if not args.force:
        existing = [m for m in backend.get_all_memories() if m.source_type == 'exemplar']
        if existing:
            print(f"\nWarning: Database already contains {len(existing)} exemplars.")
            print("Use --force to reload anyway, or --stats to see coverage.")

            # Check if any match this ontology
            ontology_existing = [
                m for m in existing
                if args.ontology in m.scope.get('ontology', [])
            ]
            if ontology_existing:
                print(f"  {len(ontology_existing)} are for ontology '{args.ontology}'")

    # Load exemplars
    print(f"\nLoading exemplars for ontology '{args.ontology}'...")
    try:
        loaded_ids = load_exemplars_from_directory(
            args.exemplar_dir,
            backend,
            args.ontology,
            pattern=args.pattern
        )

        print(f"\n✓ Successfully loaded {len(loaded_ids)} exemplars")

    except Exception as e:
        print(f"\n✗ Error loading exemplars: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Show statistics if requested
    if args.stats:
        from rlm_runtime.memory.curriculum_retrieval import analyze_curriculum_coverage

        print("\n" + "="*60)
        print("CURRICULUM COVERAGE STATISTICS")
        print("="*60)

        coverage = analyze_curriculum_coverage(backend, args.ontology)

        print(f"\nTotal exemplars: {coverage['total_exemplars']}")

        print("\nBy level:")
        for level in range(1, 6):
            count = coverage['by_level'].get(level, 0)
            status = "✓" if count > 0 else "✗"
            print(f"  {status} Level {level}: {count} exemplar(s)")

        if coverage['missing_levels']:
            print(f"\nMissing levels: {coverage['missing_levels']}")
        else:
            print("\n✓ Full coverage across all levels!")

        print("\nBy ontology:")
        for ont, count in sorted(coverage['by_ontology'].items()):
            print(f"  - {ont}: {count} exemplar(s)")

    print("\n✓ Done!")


if __name__ == '__main__':
    main()
