# Testing Guide

This directory contains the test suite for the Tailor Python sidecar.

## Structure

```
tests/
├── conftest.py              # Pytest configuration and fixtures
├── test_constants.py        # Tests for constants module
├── test_exceptions.py       # Tests for exception hierarchy
├── test_json_rpc.py         # Tests for JSON-RPC utilities
└── test_path_utils.py       # Tests for path utilities
```

## Running Tests

### Install Dependencies

```bash
pixi install
```

### Run All Tests

```bash
pixi run test
```

### Run Specific Test File

```bash
pixi run pytest tests/test_constants.py -v
```

### Run Tests by Marker

```bash
# Run only unit tests
pixi run pytest tests/ -m unit

# Run integration tests
pixi run pytest tests/ -m integration

# Run all except slow tests
pixi run pytest tests/ -m "not slow"
```

### With Coverage

```bash
pixi run pytest tests/ --cov=. --cov-report=html
```

The coverage report will be generated in `htmlcov/index.html`.

## Test Markers

- `@pytest.mark.unit` - Unit tests (fast, isolated)
- `@pytest.mark.integration` - Integration tests (slower, may need external resources)
- `@pytest.mark.slow` - Slow running tests

## Writing Tests

### Test File Naming

- Test files must start with `test_`
- Test classes must start with `Test`
- Test functions must start with `test_`

### Example Test

```python
import pytest
from my_module import my_function

@pytest.mark.unit
class TestMyFunction:
    """Tests for my_function."""
    
    def test_basic_case(self):
        """Test basic functionality."""
        result = my_function(input_value)
        assert result == expected_value
    
    def test_error_case(self):
        """Test error handling."""
        with pytest.raises(MyError):
            my_function(bad_input)
```

### Using Fixtures

Use `tmp_path` fixture for temporary directories:

```python
def test_file_creation(tmp_path):
    """Test creating a file."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")
    assert test_file.exists()
```

## Current Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| `constants.py` | 6 tests | 100% |
| `exceptions.py` | 10 tests | ~90% |
| `utils/json_rpc.py` | 10 tests | ~95% |
| `utils/path_utils.py` | 14 tests | ~85% |
| **Total** | **40+ tests** | **~90%** |

## TODO

- [ ] Add tests for `logging_config.py`
- [ ] Add tests for `PluginBase` (api/plugin_base.py)
- [ ] Add tests for `EventEmitter`
- [ ] Add tests for `WebSocketServer` (mocked)
- [ ] Add tests for `VaultBrain` (mocked)
- [ ] Add integration tests for plugin loading
- [ ] Add integration tests for command execution
- [ ] Set up CI/CD to run tests automatically

## Continuous Testing

For development with auto-rerun on file changes:

```bash
pixi add pytest-watch
pixi run ptw tests/
```

This will automatically run tests when you modify files.
