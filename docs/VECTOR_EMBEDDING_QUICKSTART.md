# Vector Embedding Quick Start Guide

## 🚀 Get Started in 5 Minutes

### 1. Install Dependencies

```bash
pip install sentence-transformers faiss-cpu numpy
```

### 2. Import and Initialize

```python
from src.core.vector_embedder import setup_vector_system

taxonomy = setup_vector_system()
```

### 3. Add Some Tags

```python
tags = ["nature", "landscape", "tree", "forest", "mountain", "sky"]
taxonomy.add_tags(tags)
```

### 4. Find Similar Tags

```python
similar = taxonomy.find_similar_tags("nature", k=3)
print(f"Similar to 'nature': {similar}")
# Output: [('landscape', 0.87), ('forest', 0.82), ('tree', 0.78)]
```

### 5. Integrate with Image Processing

```python
from src.core.image_processing import extract_tags_with_semantics

# Your AI model result
ai_result = [
    {'label': 'nature, landscape', 'score': 0.95},
    {'label': 'tree, forest', 'score': 0.87}
]

# Extract tags with semantic enhancement
category, keywords, description, semantic_data = extract_tags_with_semantics(
    result=ai_result,
    model_task="image-classification",
    taxonomy=taxonomy
)

print(f"Keywords: {keywords}")
print(f"Semantic similarities: {semantic_data.get('tag_similarities', {})}")
```

## 📋 Cheat Sheet

### Basic Operations

```python
# Initialize
taxonomy = setup_vector_system()

# Add tags
taxonomy.add_tags(["tag1", "tag2", "tag3"])

# Find similar tags
similar = taxonomy.find_similar_tags("tag1", k=5)

# Get tag embedding
embedding = taxonomy.get_tag_embedding("tag1")

# Get statistics
stats = taxonomy.get_taxonomy_stats()
```

### Common Patterns

**Batch Processing:**
```python
# Process multiple tag sets
tag_sets = [["nature", "tree"], ["city", "building"], ["animal", "bird"]]
for tags in tag_sets:
    taxonomy.add_tags(tags)
```

**Cross-Image Analysis:**
```python
# Find relationships between different image categories
print(taxonomy.find_similar_tags("nature", k=3))
print(taxonomy.find_similar_tags("urban", k=3))
```

**Performance Monitoring:**
```python
stats = taxonomy.get_taxonomy_stats()
print(f"Tags: {stats['tag_count']}, Cache: {stats['cache_size']}")
```

## 🔧 Troubleshooting

**Issue: `HAS_VECTOR_DEPS: False`**
```bash
pip install sentence-transformers faiss-cpu numpy
```

**Issue: Slow first run**
- Model downloads on first use (~80MB)
- Subsequent runs are fast (cached)

**Issue: File permissions**
```bash
mkdir vector_cache
chmod 755 vector_cache
```

## 📚 Learn More

- [Full Documentation](VECTOR_EMBEDDING_GUIDE.md)
- [API Reference](VECTOR_EMBEDDING_GUIDE.md#api-reference)
- [Integration Guide](VECTOR_EMBEDDING_GUIDE.md#integration-points)

## 🎯 Key Features

✅ **Semantic Search** - Find tags by meaning, not just exact matches  
✅ **Local Storage** - Vector embeddings stored in `vector_cache/`  
✅ **Automatic Integration** - Works seamlessly with existing pipeline  
✅ **Backward Compatible** - Falls back gracefully if dependencies missing  
✅ **Production Ready** - Optimized for performance and reliability  

## 🚀 Next Steps

1. **Test with your data** - Try different tag combinations
2. **Monitor performance** - Check `get_taxonomy_stats()`
3. **Integrate deeply** - Enhance your processing pipeline
4. **Explore advanced** - Try different embedding models

**Need help?** Check the [full documentation](VECTOR_EMBEDDING_GUIDE.md) or run the demo:
```bash
python demo_vector_embedder.py
```