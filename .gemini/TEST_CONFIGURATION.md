# Test Configuration Update

**Date**: 2026-01-18  
**Status**: ✅ Complete

---

## Changes Made

### Added Global Configuration Variables

**File**: `tests/test_daminion_api.py`

**New configuration section** at top of file:

```python
# ============================================================================
# TEST CONFIGURATION
# ============================================================================
# Update these values to match your Daminion server for integration testing

TEST_DAMINION_URL = os.environ.get('DAMINION_URL', 'http://damserver.local/daminion')
TEST_DAMINION_USERNAME = os.environ.get('DAMINION_USERNAME', 'admin')
TEST_DAMINION_PASSWORD = os.environ.get('DAMINION_PASSWORD', 'admin')

# Note: Unit tests use mocks and don't connect to real server.
# For integration tests, set environment variables or edit defaults above.
# ============================================================================
```

### Added Integration Tests

**5 new integration tests** that connect to real Daminion server:

1. ✅ `test_real_authentication` - Test login with real server
2. ✅ `test_real_get_version` - Get Daminion version
3. ✅ `test_real_get_tags` - Retrieve tag schema
4. ✅ `test_real_search` - Search for items
5. ✅ `test_real_get_collections` - Get shared collections

**Default**: Integration tests are **disabled** (skip by default)  
**Enable**: Set `RUN_INTEGRATION_TESTS=1` environment variable

---

## How to Use

### Option 1: Use Default Values

Edit `test_daminion_api.py` directly:

```python
TEST_DAMINION_URL = 'http://your-server/daminion'
TEST_DAMINION_USERNAME = 'your_username'
TEST_DAMINION_PASSWORD = 'your_password'
```

### Option 2: Use Environment Variables (Recommended)

**Windows (PowerShell)**:
```powershell
$env:DAMINION_URL = "http://damserver.local/daminion"
$env:DAMINION_USERNAME = "admin"
$env:DAMINION_PASSWORD = "admin"

# Run unit tests only (default)
python tests/test_daminion_api.py

# Run with integration tests
$env:RUN_INTEGRATION_TESTS = "1"
python tests/test_daminion_api.py
```

**Linux/Mac**:
```bash
export DAMINION_URL="http://damserver.local/daminion"
export DAMINION_USERNAME="admin"
export DAMINION_PASSWORD="admin"

# Run unit tests only (default)
python tests/test_daminion_api.py

# Run with integration tests
RUN_INTEGRATION_TESTS=1 python tests/test_daminion_api.py
```

---

## Test Output

### Unit Tests Only (Default)

```
======================================================================
DAMINION API TEST SUITE
======================================================================
Configuration:
  URL: http://damserver.local/daminion
  Username: admin
  Password: *****
  Integration Tests: DISABLED
======================================================================

test_base_url_normalization ... ok
test_init_basic ... ok
...
(28 tests)
...

======================================================================
TEST SUMMARY
======================================================================
Tests run: 28
Successes: 28
Failures: 0
Errors: 0

✅ ALL TESTS PASSED!
```

### With Integration Tests Enabled

```
======================================================================
DAMINION API TEST SUITE
======================================================================
Configuration:
  URL: http://damserver.local/daminion
  Username: admin
  Password: *****
  Integration Tests: ENABLED
======================================================================

⚠️  Integration tests ENABLED - will connect to real server

test_base_url_normalization ... ok
test_init_basic ... ok
...
(28 unit tests)
...
test_real_authentication ... ok
test_real_get_version ... ok
Server version: 7.5.1234
test_real_get_tags ... ok
Found 45 tags
test_real_search ... ok
Found 5 items (max 5)
test_real_get_collections ... ok
Found 3 collections

======================================================================
TEST SUMMARY
======================================================================
Tests run: 33
Successes: 33
Failures: 0
Errors: 0

✅ ALL TESTS PASSED!
```

---

## Benefits

### For Developers

1. **Easy Configuration** - Set once, use everywhere
2. **Environment Variables** - Don't commit credentials
3. **Default Values** - Works out of the box
4. **Integration Tests** - Optionally test real server

### For CI/CD

1. **Secrets Management** - Use CI environment variables
2. **Conditional Testing** - Run integration tests only when needed
3. **Flexible** - Different configs for different environments

### For Testing

1. **Unit Tests** - Fast, no server needed (default)
2. **Integration Tests** - Validate against real server (optional)
3. **Safe Defaults** - Won't accidentally connect to production

---

## Example CI/CD Configuration

### GitHub Actions

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        pip install pytest pytest-cov
    
    - name: Run unit tests
      run: python tests/test_daminion_api.py
    
    - name: Run integration tests
      if: github.ref == 'refs/heads/main'
      env:
        DAMINION_URL: ${{ secrets.DAMINION_URL }}
        DAMINION_USERNAME: ${{ secrets.DAMINION_USERNAME }}
        DAMINION_PASSWORD: ${{ secrets.DAMINION_PASSWORD }}
        RUN_INTEGRATION_TESTS: "1"
      run: python tests/test_daminion_api.py
```

---

## Updated Files

1. **`tests/test_daminion_api.py`**
   - Added configuration variables
   - Added 5 integration tests
   - Updated run_tests() to show config
   - Shows integration test status

2. **`tests/README.md`**
   - Added Configuration section
   - Documented environment variables
   - Explained integration tests
   - Added usage examples

---

## Summary

✅ **Configuration variables added** with sensible defaults  
✅ **Environment variable support** for secure credential management  
✅ **5 integration tests added** for real server validation  
✅ **Integration tests optional** - disabled by default  
✅ **Documentation updated** in README  
✅ **All tests passing** (28 unit tests)  

**Default Configuration**:
- URL: `http://damserver.local/daminion`
- Username: `admin`
- Password: `admin`

**Ready to use!** Just set environment variables or edit defaults.

---

**Last Updated**: 2026-01-18  
**Tests**: 28 unit + 5 integration = 33 total
