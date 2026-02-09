#!/bin/bash
# Download SPAR ontologies for KAG document understanding

set -e  # Exit on error

echo "Downloading SPAR ontologies to ../rlm/ontology/..."
echo

# Essential SPAR ontologies
echo "📥 Downloading DoCO (Document Components)..."
curl -L -o doco.ttl https://sparontologies.github.io/doco/current/doco.ttl

echo "📥 Downloading DEO (Discourse Elements)..."
curl -L -o deo.ttl https://sparontologies.github.io/deo/current/deo.ttl

echo "📥 Downloading FaBiO (Bibliographic Types)..."
curl -L -o fabio.ttl https://sparontologies.github.io/fabio/current/fabio.ttl

echo "📥 Downloading Literal (Text Reification)..."
curl -L -o literal.ttl https://sparontologies.github.io/literal/current/literal.ttl

# External (W3C)
echo "📥 Downloading PROV-O (W3C Provenance)..."
curl -L -o prov-o.ttl https://www.w3.org/ns/prov.ttl

# Pattern Ontology (may need different URL)
echo "📥 Attempting to download Pattern Ontology..."
curl -L -o po.ttl http://www.essepuntato.it/2008/12/pattern || \
    echo "⚠️  Pattern Ontology download failed - may need manual download"

echo
echo "✅ Download complete!"
echo
echo "Downloaded ontologies:"
ls -lh *.ttl

echo
echo "Usage:"
echo "  - These ontologies are used by experiments/KAG/"
echo "  - Agents will import these to understand document structure"
echo "  - See README.md for details"
