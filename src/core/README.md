# Core Components

This directory contains core business logic components for the Synapic application.

---

## Daminion API Client

**Version**: 2.0.0  
**Status**: ✅ Production Ready

### Quick Start

```python
from src.core.daminion_api import DaminionAPI

with DaminionAPI(
    base_url="https://your-server.daminion.net",
    username="admin",
    password="secret"
) as api:
    # Search items
    items = api.media_items.search(query="city")
    
    # Get collections
    collections = api.collections.get_all()
    
    # Get tag schema
    tags = api.tags.get_all_tags()
```

### Files in This Directory

#### Implementation
- **`daminion_api.py`** - Main API client (use this!)
- **`daminion_client.py`** - ⚠️ DEPRECATED (do not use)

#### Examples & Tests
- **`daminion_api_example.py`** - 9 working examples
- **`test_daminion_api.py`** - 11 automated tests

### Documentation

**📚 All documentation is in `.gemini/` directory**

| Document | Purpose |
|----------|---------|
| **`.gemini/DAMINION_API_INDEX.md`** | **START HERE** - Documentation index |
| `.gemini/DAMINION_API_QUICK_REFERENCE.md` | Quick lookup cheat sheet |
| `.gemini/DAMINION_API_REFERENCE.md` | Complete API reference (900+ lines) |
| `.gemini/DAMINION_API_GUIDE.md` | Developer guide & migration |
| `.gemini/VERSION_HISTORY.md` | Version history & changelog |

### Quick Links

**I want to...**

- **Get started quickly** → `.gemini/DAMINION_API_QUICK_REFERENCE.md`
- **See examples** → `daminion_api_example.py`
- **Test my connection** → `test_daminion_api.py`
- **Learn everything** → `.gemini/DAMINION_API_REFERENCE.md`
- **Migrate old code** → `.gemini/DAMINION_API_GUIDE.md`
- **Understand changes** → `.gemini/VERSION_HISTORY.md`

### Running Tests

```bash
cd src/core

# 1. Update credentials in test_daminion_api.py
# 2. Run tests
python test_daminion_api.py
```

### Running Examples

```bash
cd src/core

# 1. Update credentials in daminion_api_example.py
# 2. Uncomment the examples you want to run
# 3. Run
python daminion_api_example.py
```

---

## Other Core Components

_(Add other core components here as they are developed)_

---

**For complete Daminion API documentation, see `.gemini/DAMINION_API_INDEX.md`**
