# Backend API Tests

## Running Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run specific test file
pytest tests/test_api_auth.py -v

# Run with coverage
pytest --cov=app --cov-report=html

# Run only integration tests
pytest -m integration

# Run only unit tests
pytest -m unit
```

## Test Files

- `test_api_auth.py` - Tests for authentication endpoints and feed search
- `test_feed_translations.py` - Tests for feed translation CRUD operations

## Test Coverage

Tests cover:
- Authentication endpoints (OTP, registration, login)
- Feed search and retrieval
- Feed translation endpoints
- Country languages API
- Organization authentication
- Error handling and validation

## Writing New Tests

Follow the existing test structure:

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestFeatureName:
    def test_endpoint_name(self):
        response = client.get("/endpoint")
        assert response.status_code == 200
        data = response.json()
        assert "expected_field" in data
```

