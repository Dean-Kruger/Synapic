# Daminion API Documentation

**Version**: 2.0.0  
**Status**: ✅ Production Ready  
**Last Updated**: 2026-01-18

---

## 📚 Documentation Structure

All Daminion API documentation is organized in this directory for easy access.

### Quick Navigation

| I want to... | File to read |
|--------------|--------------|
| **Get started quickly** | `DAMINION_API_QUICK_REFERENCE.md` |
| **Learn everything** | `DAMINION_API_REFERENCE.md` |
| **Migrate old code** | `DAMINION_API_GUIDE.md` |
| **Understand changes** | `VERSION_HISTORY.md` |
| **Find anything** | `DAMINION_API_INDEX.md` (master index) |

---

## 📁 Files in This Directory

### Start Here
- **`DAMINION_API_INDEX.md`** - Master documentation index (read this first!)

### Essential Docs
- **`DAMINION_API_QUICK_REFERENCE.md`** - Quick reference cheat sheet (~150 lines)
- **`DAMINION_API_REFERENCE.md`** - Complete API documentation (~900 lines)
- **`DAMINION_API_GUIDE.md`** - Developer guide & migration (~400 lines)
- **`VERSION_HISTORY.md`** - Complete changelog and version history (~800 lines)

### Archive
- **`archive/`** - Archived documentation from development process
  - `DAMINION_API_FIXES.md` - Initial fix attempts (superseded by v2.0)
  - `FIX_SUMMARY.md` - Fix summaries (superseded by v2.0)
  - `TEST_PLAN.md` - Old test plan (superseded by automated tests)
  - `DAMINION_API_REWRITE_SUMMARY.md` - Initial rewrite summary (consolidated into VERSION_HISTORY.md)
  - `DAMINION_API_BEFORE_AFTER.md` - Comparisons (consolidated into VERSION_HISTORY.md)

---

## 🚀 Implementation & Examples

The actual code is in `../src/core/`:

```
src/core/
├── daminion_api.py              # Main API client
├── daminion_api_example.py      # 9 working examples
├── test_daminion_api.py         # 11 automated tests
└── README.md                    # Quick start guide
```

---

## 📖 Reading Order

### For New Developers

1. **`DAMINION_API_INDEX.md`** - Understand the documentation
2. **`DAMINION_API_QUICK_REFERENCE.md`** - Learn basic syntax
3. **`../src/core/daminion_api_example.py`** - Run examples
4. **`../src/core/test_daminion_api.py`** - Test your connection
5. **`DAMINION_API_REFERENCE.md`** - Deep dive as needed

### For Migrating Existing Code

1. **`VERSION_HISTORY.md`** - Understand what changed
2. **`DAMINION_API_GUIDE.md`** - Follow migration guide
3. **`DAMINION_API_REFERENCE.md`** - Look up new method signatures
4. **`../src/core/test_daminion_api.py`** - Validate your migration

### For API Reference

1. **`DAMINION_API_QUICK_REFERENCE.md`** - Quick lookup
2. **`DAMINION_API_REFERENCE.md`** - Detailed documentation
3. **`../src/core/daminion_api_example.py`** - Working examples

---

## 🎯 Quick Start

```python
from src.core.daminion_api import DaminionAPI

# Using context manager (recommended)
with DaminionAPI(
    base_url="https://your-server.daminion.net",
    username="admin",
    password="secret"
) as api:
    # Search for items
    items = api.media_items.search(query="city")
    
    # Get collections
    collections = api.collections.get_all()
    
    # Get tag schema
    tags = api.tags.get_all_tags()
```

For more examples, see `../src/core/daminion_api_example.py`

---

## 📊 What's Included

### Complete Implementation (~1,200 lines)
- ✅ Context manager support
- ✅ 9 specialized sub-APIs
- ✅ 50+ documented methods
- ✅ 100% type hints
- ✅ Comprehensive error handling

### Comprehensive Documentation (~2,500 lines)
- ✅ Complete API reference
- ✅ Quick reference cheat sheet
- ✅ Developer guide
- ✅ Migration guide
- ✅ Version history

### Examples & Tests (~800 lines)
- ✅ 9 working examples
- ✅ 11 automated tests
- ✅ Ready to run and modify

---

## 🔄 Version History

### v2.0.0 (2026-01-18) - Current
- Complete rewrite based on official API
- Modular architecture with 9 sub-APIs
- 100% type hints and documentation
- 85% coverage of commonly-used endpoints
- **Status**: ✅ Production Ready

### v1.x - Deprecated
- Original implementation
- **Status**: ⚠️ Do not use (see `../src/core/daminion_client.py`)

See `VERSION_HISTORY.md` for full changelog.

---

## 📞 Support

- **Official Daminion API**: https://marketing.daminion.net/APIHelp
- **Documentation Index**: `DAMINION_API_INDEX.md`
- **Quick Reference**: `DAMINION_API_QUICK_REFERENCE.md`
- **Full Reference**: `DAMINION_API_REFERENCE.md`

---

## ✅ Organization Benefits

This organization provides:

1. **Clear Separation**
   - Implementation in `src/core/`
   - Documentation in `.gemini/`
   
2. **Easy Discovery**
   - Master index guides you
   - Logical file naming
   
3. **Proper Archiving**
   - Development history preserved
   - Current docs are obvious
   
4. **Professional Structure**
   - Follows best practices
   - Easy for teams to navigate

---

**Last Updated**: 2026-01-18  
**Maintainer**: Synapic Project Team
