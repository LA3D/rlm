"""Context layer caching for faster experiment iteration.

L0 (sense card) and L1 (schema constraints) are built from static ontology
files and don't change between runs. Cache them to disk to avoid rebuilding.
"""

from pathlib import Path
import hashlib
from rdflib import Graph


def cache_key(ont_path: str, layer: str, budget: int) -> str:
    """Generate cache key from ontology path + layer + budget.

    Args:
        ont_path: Path to ontology file
        layer: Layer name ('l0' or 'l1')
        budget: Character budget

    Returns:
        Cache key (hash of file content + layer + budget)
    """
    # Hash the file content to detect changes
    with open(ont_path, 'rb') as f:
        file_hash = hashlib.md5(f.read()).hexdigest()[:8]

    return f"{layer}_{file_hash}_{budget}"


def cache_path(ont_path: str, layer: str, budget: int) -> Path:
    """Get cache file path for a layer.

    Args:
        ont_path: Path to ontology file
        layer: Layer name ('l0' or 'l1')
        budget: Character budget

    Returns:
        Path to cache file
    """
    ont_dir = Path(ont_path).parent
    cache_dir = ont_dir / '.cache'
    cache_dir.mkdir(exist_ok=True)

    key = cache_key(ont_path, layer, budget)
    return cache_dir / f"{key}.txt"


def load_cached(ont_path: str, layer: str, budget: int) -> str | None:
    """Load cached layer content if available.

    Args:
        ont_path: Path to ontology file
        layer: Layer name ('l0' or 'l1')
        budget: Character budget

    Returns:
        Cached content or None if cache miss
    """
    cache_file = cache_path(ont_path, layer, budget)
    if cache_file.exists():
        return cache_file.read_text()
    return None


def save_cached(ont_path: str, layer: str, budget: int, content: str):
    """Save layer content to cache.

    Args:
        ont_path: Path to ontology file
        layer: Layer name ('l0' or 'l1')
        budget: Character budget
        content: Layer content to cache
    """
    cache_file = cache_path(ont_path, layer, budget)
    cache_file.write_text(content)


def build_with_cache(ont_path: str, layer: str, budget: int, builder_fn,
                     **extra_kwargs) -> str:
    """Build layer content with caching.

    Args:
        ont_path: Path to ontology file
        layer: Layer name ('l0' or 'l1')
        budget: Character budget
        builder_fn: Function that builds the layer (takes graph, budget, **extra_kwargs)
        **extra_kwargs: Additional keyword args passed to builder_fn
            (e.g., endpoint_meta). When present, caching is skipped since
            the cache key doesn't account for these parameters.

    Returns:
        Layer content (from cache or freshly built)
    """
    # Skip cache when extra kwargs are provided (cache key doesn't cover them)
    if not extra_kwargs:
        cached = load_cached(ont_path, layer, budget)
        if cached is not None:
            return cached

    # Cache miss or cache bypass - build from scratch
    g = Graph().parse(ont_path)
    content = builder_fn(g, budget, **extra_kwargs)

    # Only cache when no extra kwargs (stable result)
    if not extra_kwargs:
        save_cached(ont_path, layer, budget, content)

    return content


def clear_cache(ont_path: str):
    """Clear all cached layers for an ontology.

    Args:
        ont_path: Path to ontology file
    """
    ont_dir = Path(ont_path).parent
    cache_dir = ont_dir / '.cache'
    if cache_dir.exists():
        for cache_file in cache_dir.glob('*.txt'):
            cache_file.unlink()
        print(f"Cleared cache: {cache_dir}")
