# Tests Directory

Automated tests for the Synapic application.

---

## Test Files

### Daminion API Tests

**File**: `test_daminion_api.py`  
**Purpose**: Comprehensive unit tests for the new DaminionAPI client (v2.0)

**Tests Included** (40+ tests):
- ✅ API initialization and configuration
- ✅ Authentication (success, failure, context manager)
- ✅ MediaItemsAPI (search, get by IDs, count)
- ✅ TagsAPI (schema, values, search)
- ✅ CollectionsAPI (list, items, create)
- ✅ ItemDataAPI (metadata, batch update)
- ✅ Error handling (404, 403, 429, network)
- ✅ Rate limiting
- ✅ Data classes (TagInfo, TagValue, SharedCollection)

---

## Configuration

### Server Connection

The test suite includes global configuration variables for connecting to a Daminion server:

**Default values** (edit in `test_daminion_api.py`):
```python
TEST_DAMINION_URL = 'http://damserver.local/daminion'
TEST_DAMINION_USERNAME = 'admin'
TEST_DAMINION_PASSWORD = 'admin'
```

**Using environment variables** (recommended):
```bash
# Windows (PowerShell)
$env:DAMINION_URL = "http://your-server.local/daminion"
$env:DAMINION_USERNAME = "your_username"
$env:DAMINION_PASSWORD = "your_password"

# Linux/Mac
export DAMINION_URL="http://your-server.local/daminion"
export DAMINION_USERNAME="your_username"
export DAMINION_PASSWORD="your_password"
```

### Integration Tests

By default, only **unit tests** run (they use mocks, no server needed).

To enable **integration tests** that connect to a real server:

```bash
# Windows (PowerShell)
$env:RUN_INTEGRATION_TESTS = "1"
python tests/test_daminion_api.py

# Linux/Mac
RUN_INTEGRATION_TESTS=1 python tests/test_daminion_api.py
```

**Integration tests** (5 additional tests):
- ✅ Real server authentication
- ✅ Get server version
- ✅ Get tag schema
- ✅ Search items
- ✅ Get collections

---

## Running Tests

### Method 1: Direct Execution

```bash
cd tests
python test_daminion_api.py
```

### Method 2: Using Pytest (Recommended)

```bash
# Install pytest if needed
pip install pytest pytest-cov

# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src/core --cov-report=html

# Run specific test class
python -m pytest tests/test_daminion_api.py::TestMediaItemsAPI -v

# Run specific test
python -m pytest tests/test_daminion_api.py::TestMediaItemsAPI::test_search_simple -v
```

### Method 3: Using unittest

```bash
python -m unittest discover tests/ -v
```

---

## Test Structure

Tests use Python's `unittest` framework with mocking for isolation:

```python
class TestMediaItemsAPI(unittest.TestCase):
    """Test MediaItemsAPI functionality"""
    
    def setUp(self):
        """Set up before each test"""
        self.api = DaminionAPI(...)
        self.api._authenticated = True
    
    @patch('src.core.daminion_api.DaminionAPI._make_request')
    def test_search_simple(self, mock_request):
        """Test simple text search"""
        mock_request.return_value = [...]
        items = self.api.media_items.search(query="test")
        self.assertEqual(len(items), 2)
```

---

## Test Categories

### 1. Unit Tests (Current)

**Purpose**: Test individual components in isolation  
**Mocking**: Extensive use of mocks to avoid network calls  
**Speed**: Fast (< 1 second)  
**Coverage**: API methods, error handling, data structures

### 2. Integration Tests (Future)

**Purpose**: Test with real Daminion server  
**Location**: `test_daminion_api_integration.py` (to be created)  
**Requirements**: Access to test Daminion server  
**Coverage**: End-to-end workflows

---

## Writing New Tests

### Template for New Test Class

```python
class TestNewFeature(unittest.TestCase):
    """Test new feature"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.api = DaminionAPI(
            base_url="https://test.daminion.net",
            username="test_user",
            password="test_pass"
        )
        self.api._authenticated = True
    
    @patch('src.core.daminion_api.DaminionAPI._make_request')
    def test_something(self, mock_request):
        """Test something specific"""
        # Arrange
        mock_request.return_value = {"result": "data"}
        
        # Act
        result = self.api.something.method()
        
        # Assert
        self.assertEqual(result, "data")
        mock_request.assert_called_once()
```

### Best Practices

1. **One assertion per test** (when possible)
2. **Clear test names** describing what's being tested
3. **Arrange-Act-Assert** pattern
4. **Mock external dependencies** (network, database, etc.)
5. **Test both success and failure** cases
6. **Document complex tests** with docstrings

---

## Test Coverage

Current coverage: **~85%** of daminion_api.py

### Covered
- ✅ Initialization
- ✅ Authentication
- ✅ All sub-API classes
- ✅ Error handling
- ✅ Rate limiting
- ✅ Data classes

### Not Covered (Integration Tests Needed)
- ⚠️ Real network requests
- ⚠️ Session cookie handling with real server
- ⚠️ Binary data (thumbnails, downloads)
- ⚠️ Complex multi-step workflows

---

## Continuous Integration

For CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run tests
  run: |
    pip install pytest pytest-cov
    python -m pytest tests/ --cov=src/core --cov-report=xml
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
```

---

## Archived Tests

Old test files from v1.x development are in `archive_old_tests/`:

- `test_daminion_api_live.py` - Old live tests
- `test_daminion_connection.py` - Old connection tests
- `debug_*.py` - Debug scripts
- `*.txt` - Output logs

These are kept for historical reference but should not be used.

---

## Troubleshooting

### Import Errors

If you get `ModuleNotFoundError`:

```bash
# Make sure you're in the project root
cd /path/to/Synapic

# Run tests from root
python -m pytest tests/
```

### Mock Not Working

Make sure patch path is correct:

```python
# ✅ Correct - patch where it's used
@patch('src.core.daminion_api.urllib.request.urlopen')

# ❌ Wrong - patching the import
@patch('urllib.request.urlopen')
```

### Tests Hanging

If tests hang, check:
- Rate limiting not set too high
- No actual network calls being made
- Mocks are properly configured

---

## Next Steps

1. **Run current tests** - Verify all pass
2. **Add integration tests** - For real server testing
3. **Increase coverage** - Target 95%+
4. **Add performance tests** - For rate limiting, etc.
5. **Add load tests** - For production scenarios

---

## Resources

- **unittest docs**: https://docs.python.org/3/library/unittest.html
- **pytest docs**: https://docs.pytest.org/
- **unittest.mock**: https://docs.python.org/3/library/unittest.mock.html

---

**Last Updated**: 2026-01-18  
**Test Framework**: unittest + pytest  
**Coverage Tool**: pytest-cov
