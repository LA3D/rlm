"""Unit tests for SHACL example indexing."""
import pytest
from rdflib import Graph, Namespace, RDF, Literal
from rdflib.namespace import SH

from rlm.shacl_examples import (
    detect_shacl, build_shacl_index, SHACLIndex,
    describe_shape, search_shapes, shape_constraints,
    extract_keywords
)


class TestSHACLDetection:
    """Tests for SHACL content detection."""

    def test_detect_shacl_empty_graph(self):
        """Empty graph should have no SHACL."""
        g = Graph()
        result = detect_shacl(g)
        assert result['has_shacl'] == False
        assert result['paradigm'] == 'none'
        assert result['node_shapes'] == 0
        assert result['property_shapes'] == 0

    def test_detect_shacl_with_node_shape(self):
        """Graph with NodeShape should be detected."""
        g = Graph()
        EX = Namespace("http://example.org/")
        g.add((EX.PersonShape, RDF.type, SH.NodeShape))
        g.add((EX.PersonShape, SH.targetClass, EX.Person))

        result = detect_shacl(g)
        assert result['has_shacl'] == True
        assert result['node_shapes'] == 1
        assert result['paradigm'] == 'validation'

    def test_detect_shacl_with_property_shape(self):
        """Graph with PropertyShape should be detected."""
        g = Graph()
        EX = Namespace("http://example.org/")
        g.add((EX.NamePropertyShape, RDF.type, SH.PropertyShape))

        result = detect_shacl(g)
        assert result['has_shacl'] == True
        assert result['property_shapes'] == 1


class TestKeywordExtraction:
    """Tests for keyword extraction from shapes."""

    def test_extract_from_shape_uri(self):
        """Should extract local name from shape URI."""
        g = Graph()
        EX = Namespace("http://example.org/")
        keywords = extract_keywords(g, EX.PersonShape, [], [])
        assert 'personshape' in keywords

    def test_extract_from_labels(self):
        """Should extract keywords from rdfs:label."""
        g = Graph()
        EX = Namespace("http://example.org/")
        from rdflib import RDFS
        g.add((EX.PersonShape, RDFS.label, Literal("Person Shape")))
        keywords = extract_keywords(g, EX.PersonShape, [], [])
        assert 'person shape' in keywords

    def test_extract_from_target_classes(self):
        """Should extract keywords from target class local names."""
        g = Graph()
        EX = Namespace("http://example.org/")
        target_classes = ["http://example.org/Person"]
        keywords = extract_keywords(g, EX.PersonShape, target_classes, [])
        assert 'person' in keywords

    def test_extract_from_property_paths(self):
        """Should extract keywords from property paths."""
        g = Graph()
        EX = Namespace("http://example.org/")
        props = [{'path': 'http://example.org/name'}, {'path': 'http://example.org/age'}]
        keywords = extract_keywords(g, EX.PersonShape, [], props)
        assert 'name' in keywords
        assert 'age' in keywords


class TestBuildIndex:
    """Tests for SHACL index building."""

    def test_build_index_empty_graph(self):
        """Empty graph should return empty index."""
        g = Graph()
        index = build_shacl_index(g)
        assert len(index.shapes) == 0
        assert index.paradigm == 'none'

    def test_build_index_basic(self):
        """Should index basic NodeShape."""
        g = Graph()
        EX = Namespace("http://example.org/")
        g.add((EX.PersonShape, RDF.type, SH.NodeShape))
        g.add((EX.PersonShape, SH.targetClass, EX.Person))

        index = build_shacl_index(g)
        assert len(index.shapes) == 1
        assert str(EX.PersonShape) in index.shapes
        assert str(EX.Person) in index.targets[str(EX.PersonShape)]

    def test_build_index_with_properties(self):
        """Should index property constraints."""
        g = Graph()
        EX = Namespace("http://example.org/")
        from rdflib import XSD, BNode

        # Create shape with property constraint
        g.add((EX.PersonShape, RDF.type, SH.NodeShape))
        g.add((EX.PersonShape, SH.targetClass, EX.Person))

        prop_node = BNode()
        g.add((EX.PersonShape, SH.property, prop_node))
        g.add((prop_node, SH.path, EX.name))
        g.add((prop_node, SH.datatype, XSD.string))
        g.add((prop_node, SH.minCount, Literal(1)))

        index = build_shacl_index(g)
        props = index.properties[str(EX.PersonShape)]
        assert len(props) == 1
        assert props[0]['path'] == str(EX.name)
        assert props[0]['datatype'] == str(XSD.string)
        assert props[0]['minCount'] == 1

    def test_build_index_keywords(self):
        """Should build keyword index."""
        g = Graph()
        EX = Namespace("http://example.org/")
        from rdflib import RDFS

        g.add((EX.PersonShape, RDF.type, SH.NodeShape))
        g.add((EX.PersonShape, SH.targetClass, EX.Person))
        g.add((EX.PersonShape, RDFS.label, Literal("Person Shape")))

        index = build_shacl_index(g)
        # Check that some keywords were indexed
        assert len(index.keywords) > 0
        # Check that PersonShape is indexed under relevant keywords
        found = False
        for keyword, shapes in index.keywords.items():
            if str(EX.PersonShape) in shapes:
                found = True
                break
        assert found


class TestBoundedViews:
    """Tests for bounded view functions."""

    @pytest.fixture
    def sample_index(self):
        """Create a sample index for testing."""
        return SHACLIndex(
            shapes=['http://example.org/PersonShape', 'http://example.org/OrgShape'],
            targets={
                'http://example.org/PersonShape': ['http://example.org/Person'],
                'http://example.org/OrgShape': ['http://example.org/Organization']
            },
            properties={
                'http://example.org/PersonShape': [
                    {'path': 'http://example.org/name', 'datatype': 'http://www.w3.org/2001/XMLSchema#string'},
                    {'path': 'http://example.org/age', 'datatype': 'http://www.w3.org/2001/XMLSchema#integer'}
                ],
                'http://example.org/OrgShape': []
            },
            keywords={
                'person': ['http://example.org/PersonShape'],
                'personshape': ['http://example.org/PersonShape'],
                'org': ['http://example.org/OrgShape'],
                'organization': ['http://example.org/OrgShape'],
                'orgshape': ['http://example.org/OrgShape']
            }
        )

    def test_describe_shape(self, sample_index):
        """Should describe a shape with bounded properties."""
        result = describe_shape(sample_index, 'http://example.org/PersonShape')
        assert result['uri'] == 'http://example.org/PersonShape'
        assert len(result['properties']) == 2
        assert result['property_count'] == 2
        assert result['truncated'] == False
        assert 'http://example.org/Person' in result['targets']

    def test_describe_shape_with_limit(self, sample_index):
        """Should truncate properties based on limit."""
        result = describe_shape(sample_index, 'http://example.org/PersonShape', limit=1)
        assert len(result['properties']) == 1
        assert result['property_count'] == 2
        assert result['truncated'] == True

    def test_describe_shape_not_found(self, sample_index):
        """Should return error for unknown shape."""
        result = describe_shape(sample_index, 'http://example.org/UnknownShape')
        assert 'error' in result

    def test_search_shapes(self, sample_index):
        """Should find shapes by keyword."""
        results = search_shapes(sample_index, 'person')
        assert len(results) == 1
        assert results[0]['uri'] == 'http://example.org/PersonShape'
        assert 'http://example.org/Person' in results[0]['targets']

    def test_search_shapes_multiple_matches(self, sample_index):
        """Should find multiple shapes if keyword matches multiple."""
        results = search_shapes(sample_index, 'org')
        assert len(results) == 1
        assert results[0]['uri'] == 'http://example.org/OrgShape'

    def test_search_shapes_with_limit(self, sample_index):
        """Should respect limit parameter."""
        results = search_shapes(sample_index, 'shape', limit=1)
        assert len(results) <= 1

    def test_search_shapes_case_insensitive(self, sample_index):
        """Should be case insensitive."""
        results = search_shapes(sample_index, 'PERSON')
        assert len(results) >= 1

    def test_shape_constraints(self, sample_index):
        """Should format constraints as human-readable text."""
        result = shape_constraints(sample_index, 'http://example.org/PersonShape')
        assert 'PersonShape' in result
        assert 'name' in result
        assert 'age' in result
        assert 'type=string' in result
        assert 'type=integer' in result

    def test_shape_constraints_no_properties(self, sample_index):
        """Should handle shapes with no properties."""
        result = shape_constraints(sample_index, 'http://example.org/OrgShape')
        assert 'OrgShape' in result
        assert 'no property constraints' in result

    def test_shape_constraints_not_found(self, sample_index):
        """Should handle unknown shapes."""
        result = shape_constraints(sample_index, 'http://example.org/UnknownShape')
        assert 'not found' in result


class TestDCATAP:
    """Integration tests with DCAT-AP shapes."""

    @pytest.fixture
    def dcat_graph(self):
        """Load DCAT-AP shapes if available."""
        from pathlib import Path
        dcat_path = Path('ontology/dcat-ap/dcat-ap-SHACL.ttl')
        if dcat_path.exists():
            g = Graph()
            g.parse(dcat_path)
            return g
        return None

    def test_dcat_detection(self, dcat_graph):
        """Should detect SHACL in DCAT-AP."""
        if dcat_graph is None:
            pytest.skip("DCAT-AP shapes not available")

        result = detect_shacl(dcat_graph)
        assert result['has_shacl'] == True
        assert result['node_shapes'] > 0

    def test_dcat_indexing(self, dcat_graph):
        """Should build index from DCAT-AP."""
        if dcat_graph is None:
            pytest.skip("DCAT-AP shapes not available")

        index = build_shacl_index(dcat_graph)
        assert len(index.shapes) > 0
        assert len(index.keywords) > 0

    def test_dcat_search_dataset(self, dcat_graph):
        """Should find Dataset shape in DCAT-AP."""
        if dcat_graph is None:
            pytest.skip("DCAT-AP shapes not available")

        index = build_shacl_index(dcat_graph)
        results = search_shapes(index, 'dataset')
        assert len(results) > 0
