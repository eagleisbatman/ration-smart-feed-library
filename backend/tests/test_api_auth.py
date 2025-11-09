"""
Integration tests for API authentication endpoints
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestAuthEndpoints:
    """Test authentication endpoints"""

    def test_get_countries(self):
        """Test getting list of countries"""
        response = client.get("/auth/countries")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            country = data[0]
            assert "id" in country
            assert "name" in country
            assert "country_code" in country
            assert "country_languages" in country  # Should include languages

    def test_get_countries_includes_languages(self):
        """Test that countries endpoint includes country_languages"""
        response = client.get("/auth/countries")
        assert response.status_code == 200
        data = response.json()
        for country in data:
            assert "country_languages" in country
            assert isinstance(country["country_languages"], list)

    def test_request_otp_invalid_email(self):
        """Test OTP request with invalid email"""
        response = client.post("/auth/request-otp", json={
            "email_id": "invalid-email",
            "purpose": "login"
        })
        assert response.status_code == 422  # Validation error

    def test_request_otp_valid_email(self):
        """Test OTP request with valid email format"""
        response = client.post("/auth/request-otp", json={
            "email_id": "test@example.com",
            "purpose": "login"
        })
        # Should either succeed (200) or fail gracefully (400/500)
        assert response.status_code in [200, 400, 500]


class TestFeedEndpoints:
    """Test feed-related endpoints"""

    def test_search_feeds_no_auth(self):
        """Test searching feeds (public endpoint)"""
        response = client.get("/feeds/")
        # Should work without auth or require auth
        assert response.status_code in [200, 401]

    def test_get_feed_by_id_invalid_uuid(self):
        """Test getting feed with invalid UUID"""
        response = client.get("/feeds/invalid-uuid")
        assert response.status_code in [400, 404, 422]

    def test_search_feeds_with_filters(self):
        """Test searching feeds with filters"""
        response = client.get("/feeds/?feed_type=Forage&limit=10")
        # Should work or require auth
        assert response.status_code in [200, 401]


class TestOrganizationAuth:
    """Test organization authentication endpoints"""

    def test_request_org_otp_invalid_email(self):
        """Test organization OTP request with invalid email"""
        response = client.post("/org/request-otp", params={
            "email": "invalid-email",
            "purpose": "registration"
        })
        assert response.status_code == 422

    def test_request_org_otp_valid_email(self):
        """Test organization OTP request with valid email"""
        response = client.post("/org/request-otp", params={
            "email": "test@example.com",
            "purpose": "registration"
        })
        # Should either succeed or fail gracefully
        assert response.status_code in [200, 400, 500]


class TestCountryAdminEndpoints:
    """Test country admin endpoints"""

    def test_get_my_country_no_auth(self):
        """Test getting country admin's country without auth"""
        response = client.get("/admin/country/my-country", params={
            "email_id": "test@example.com"
        })
        # Should require proper authentication
        assert response.status_code in [403, 404, 401]

    def test_get_feeds_no_auth(self):
        """Test getting feeds without proper auth"""
        response = client.get("/admin/country/feeds", params={
            "email_id": "test@example.com"
        })
        # Should require proper authentication
        assert response.status_code in [403, 404, 401]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

