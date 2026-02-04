"""Download ontology files for discovered federated endpoints.

This script attempts to download ontology/schema files for SPARQL endpoints
discovered from SHACL examples. It uses SPARQL 1.1 Service Description and
VoID to find downloadable ontology files.

Files are kept compressed (.gz) in git to save space. Most RDF libraries
(rdflib, etc.) can read compressed files directly.

Usage:
    python experiments/reasoningbank/tools/download_ontologies.py [--dry-run] [--top N]
"""

import sys
import argparse
import requests
from pathlib import Path
from rdflib import Graph, Namespace
from typing import Optional

sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.prototype.tools.endpoint_tools import EndpointTools

# Namespaces
VOID = Namespace('http://rdfs.org/ns/void#')
DCTERMS = Namespace('http://purl.org/dc/terms/')
FOAF = Namespace('http://xmlns.com/foaf/0.1/')


# Endpoint-specific ontology sources
# These are known sources for ontology files that can be downloaded
ONTOLOGY_SOURCES = {
    'nextprot': {
        'name': 'neXtProt',
        'ontology_url': 'https://rdfportal.org/download/nextprot/20240826/schema.ttl.gz',
        'format': 'turtle',
        'compressed': True,
        'note': 'neXtProt schema only (service discontinued 2024); full data too large'
    },
    'rhea': {
        'name': 'Rhea',
        'ontology_url': 'https://ftp.expasy.org/databases/rhea/rdf/rhea.rdf.gz',
        'format': 'xml',
        'compressed': True,
    },
    'rheadb': {  # Rhea-db variant
        'name': 'Rhea',
        'ontology_url': 'https://ftp.expasy.org/databases/rhea/rdf/rhea.rdf.gz',
        'format': 'xml',
        'compressed': True,
    },
    'bgee': {
        'name': 'Bgee',
        'ontology_url': 'https://biosoda.expasy.org/genex/ontology.ttl',
        'format': 'turtle',
        'compressed': False,
        'note': 'GENEX ontology (89 KB) - gene expression schema, not full data dump'
    },
    'orthodb': {
        'name': 'OrthoDB',
        'ontology_url': 'http://purl.org/net/orth',
        'format': 'xml',
        'compressed': False,
        'note': 'ORTH ontology v2.0 (88 KB)'
    },
    'oma': {
        'name': 'OMA Browser',
        'ontology_url': 'https://raw.githubusercontent.com/qfo/OrthologyOntology/master/oo.owl',
        'format': 'xml',
        'compressed': False,
        'note': 'Orthology Ontology (OO) and LSCR from Quest for Orthologs'
    },
    'omabrowser': {  # OMA Browser variant
        'name': 'OMA Browser',
        'ontology_url': 'https://raw.githubusercontent.com/qfo/OrthologyOntology/master/oo.owl',
        'format': 'xml',
        'compressed': False,
        'note': 'Orthology Ontology (OO) and LSCR from Quest for Orthologs'
    },
    'uniprot': {
        'name': 'UniProt',
        'note': 'Already present in ontology/uniprot/ with core.owl and examples'
    },
    'wikidata': {
        'name': 'Wikidata',
        'ontology_url': 'https://raw.githubusercontent.com/wikimedia/mediawiki-extensions-Wikibase/master/docs/ontology.owl',
        'format': 'xml',
        'compressed': False,
        'note': 'Wikibase system ontology (schema for Wikidata RDF exports), not full Wikidata'
    },
    'qlever': {
        'name': 'Qlever',
        'note': 'Qlever is a Wikidata frontend; use wikidata ontology'
    },
    'glyconnect': {
        'name': 'GlyConnect',
        'ontology_url': 'https://raw.githubusercontent.com/glycoinfo/GlycoCoO/master/ontology/glycocoo.owl',
        'format': 'xml',
        'compressed': False,
        'note': 'Glycoconjugate Ontology (GlycoCoO) v1.1.3'
    },
    'disgenet': {
        'name': 'DisGeNET',
        'note': 'DisGeNET requires registration for downloads'
    },
    'rdf': {
        'name': 'DisGeNET',
        'note': 'DisGeNET requires registration for downloads (rdf.disgenet.org)'
    },
    'stringdb': {
        'name': 'STRING',
        'note': 'STRING database - no standalone ontology available'
    },
    'idsm': {
        'name': 'IDSM',
        'note': 'IDSM uses ChEBI, ChEMBL, and Wikidata ontologies; no standalone ontology'
    },
    'allie': {
        'name': 'Allie',
        'note': 'Allie SPARQL endpoint - no standalone ontology available'
    },
    'nibb': {
        'name': 'NIBB',
        'note': 'NIBB SPARQL endpoint - no standalone ontology available'
    },
    'cordis': {
        'name': 'CORDIS',
        'note': 'CORDIS SPARQL endpoint - no standalone ontology available'
    },
    'bioregistry': {
        'name': 'Bioregistry',
        'note': 'Bioregistry SPARQL endpoint - no standalone ontology available'
    },
    'identifiers.org': {
        'name': 'Identifiers.org',
        'note': 'Identifiers.org SPARQL endpoint - no standalone ontology available'
    },
    'uberon': {
        'name': 'UBERON',
        'ontology_url': 'http://purl.obolibrary.org/obo/uberon.owl',
        'format': 'xml',
        'compressed': False,
        'note': 'Multi-species anatomy ontology (93 MB, compresses to 5.7 MB) - used by Bgee'
    },
}


def download_file(url: str, dest: Path, timeout: int = 60) -> bool:
    """Download a file from URL to destination.

    Args:
        url: Source URL
        dest: Destination file path
        timeout: Request timeout in seconds

    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"  Downloading from: {url}")
        resp = requests.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()

        # Create parent directory
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Write to file
        with open(dest, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"  ✓ Saved to: {dest}")
        return True

    except Exception as e:
        print(f"  ✗ Download failed: {e}")
        return False


def download_ontology_for_endpoint(endpoint: dict, ontology_dir: Path, dry_run: bool = False) -> bool:
    """Download ontology for a specific endpoint.

    Args:
        endpoint: Endpoint dict with name and url
        ontology_dir: Base ontology directory
        dry_run: If True, only show what would be downloaded

    Returns:
        True if downloaded (or would download in dry-run), False otherwise
    """
    name = endpoint['name'].lower().replace('-', '').replace(' ', '')

    # Check if we have configuration for this endpoint
    if name not in ONTOLOGY_SOURCES:
        print(f"  ⚠ No known ontology source for {endpoint['name']}")
        return False

    config = ONTOLOGY_SOURCES[name]
    target_dir = ontology_dir / name

    if 'ontology_url' not in config:
        print(f"  ⚠ {config.get('note', 'No downloadable ontology')}")
        return False

    if dry_run:
        print(f"  Would download: {config['ontology_url']}")
        print(f"  Would save to: {target_dir}/")
        if config.get('note'):
            print(f"  Note: {config['note']}")
        return True

    # Download
    url = config['ontology_url']
    filename = url.split('/')[-1]
    dest = target_dir / filename

    print(f"  Target: {target_dir}/")
    if config.get('note'):
        print(f"  Note: {config['note']}")

    return download_file(url, dest)


def main():
    parser = argparse.ArgumentParser(
        description='Download ontologies for discovered SPARQL endpoints'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be downloaded without actually downloading'
    )
    parser.add_argument(
        '--top',
        type=int,
        default=10,
        help='Only download ontologies for top N endpoints by example count'
    )
    parser.add_argument(
        '--skip-large',
        action='store_true',
        help='Skip large files (>1GB)'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("ONTOLOGY DOWNLOAD TOOL")
    print("=" * 70)

    # Discover endpoints
    tools = EndpointTools()
    ref = tools.federated_endpoints('ontology/uniprot')
    endpoints = tools.endpoints_list(ref.key, limit=50)

    ontology_dir = Path('ontology')

    # Get all endpoints (primary + federated)
    all_endpoints = []
    if endpoints.get('primary'):
        all_endpoints.append(endpoints['primary'])
    all_endpoints.extend(endpoints['federated'])

    # Sort by example count
    all_endpoints.sort(key=lambda e: -e['example_count'])

    # Take top N
    top_endpoints = all_endpoints[:args.top]

    print(f"\nProcessing top {args.top} endpoints by example count:")
    print(f"Dry run: {args.dry_run}")
    print()

    # Download ontologies
    success_count = 0
    for i, ep in enumerate(top_endpoints, 1):
        print(f"{i}. {ep['name']} ({ep['example_count']} examples)")

        # Check if already exists
        name_lower = ep['name'].lower().replace('-', '').replace(' ', '')
        target_dir = ontology_dir / name_lower

        if target_dir.exists() and not args.dry_run:
            print(f"  ✓ Already have: {target_dir}/")
            success_count += 1
            continue

        # Try to download
        if download_ontology_for_endpoint(ep, ontology_dir, args.dry_run):
            success_count += 1

        print()

    # Summary
    print("=" * 70)
    print(f"Summary: {success_count}/{len(top_endpoints)} ontologies available")
    print("=" * 70)

    if args.dry_run:
        print("\nRe-run without --dry-run to actually download files")


if __name__ == '__main__':
    main()
