# Log File Location Update

**Date**: 2026-01-18  
**Status**: ✅ Complete

---

## Changes Made

### Updated Log Directory

**Before**: Logs written to user's home directory
```python
LOG_DIR = Path.home() / ".synapic" / "logs"
# Location: C:\Users\Dean\.synapic\logs\synapic.log
```

**After**: Logs written to project folder
```python
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
# Location: C:\Users\Dean\Source code\Synapic\logs\synapic.log
```

---

## Files Modified

### 1. `src/utils/logger.py`
- ✅ Changed `LOG_DIR` from `~/.synapic/logs` to `<project>/logs`
- ✅ Added `PROJECT_ROOT` variable for cleaner path resolution
- ✅ Log folder will be auto-created on first run

### 2. `.gitignore`
- ✅ Added `logs/` to prevent committing log files
- ✅ Added `.venv/` to prevent committing virtual environment
- ✅ Added `*.log` pattern for safety

---

## Benefits

### For Development
1. **Easier Access** - Logs are in project folder, not hidden in user directory
2. **Version Control** - Folder ignored, but structure is clear
3. **Portability** - Works the same on all machines
4. **Debugging** - Easier to find and view logs

### For Deployment
1. **Centralized** - All project files in one location
2. **Standard** - Follows common project structure
3. **Clean** - Logs don't pollute user directories

---

## Log File Location

**New location**:
```
C:\Users\Dean\Source code\Synapic\logs\synapic.log
```

**Folder structure**:
```
Synapic/
├── src/
├── tests/
├── logs/              ← New location
│   └── synapic.log   ← Log file created here
├── .gitignore         ← Updated to ignore logs/
└── ...
```

---

## Next Run

The next time you run the application:

1. ✅ `logs/` folder will be created automatically
2. ✅ `synapic.log` will be written to project folder
3. ✅ Old logs in `~/.synapic/logs` will be ignored
4. ✅ Logs won't be committed to git

---

## Verification

After running the app, you can check:

```powershell
# List log files
ls logs/

# View latest log
Get-Content logs/synapic.log -Tail 50

# Open log folder
explorer logs
```

---

## Summary

✅ **Log directory moved** from `~/.synapic/logs` to `<project>/logs`  
✅ **Gitignore updated** to exclude log files  
✅ **Auto-created** on first run  
✅ **Easier access** for development and debugging  

**Ready to use!** Next app run will create logs in the project folder.

---

**Last Updated**: 2026-01-18
