"""
Integration tests for feed translations endpoints
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestFeedTranslations:
    """Test feed translation endpoints"""

    def test_get_translations_invalid_feed_id(self):
        """Test getting translations for invalid feed ID"""
        response = client.get("/admin/country/feeds/invalid-uuid/translations", params={
            "email_id": "test@example.com"
        })
        # Should return validation error or not found
        assert response.status_code in [400, 404, 403, 422]

    def test_add_translation_missing_data(self):
        """Test adding translation with missing data"""
        response = client.post(
            "/admin/country/feeds/invalid-uuid/translations",
            json={},
            params={"email_id": "test@example.com"}
        )
        # Should return validation error
        assert response.status_code in [400, 403, 404, 422]

    def test_delete_translation_invalid_id(self):
        """Test deleting translation with invalid ID"""
        response = client.delete(
            "/admin/country/feeds/invalid-uuid/translations/invalid-translation-id",
            params={"email_id": "test@example.com"}
        )
        # Should return validation error or not found
        assert response.status_code in [400, 403, 404, 422]


class TestCountryLanguages:
    """Test country languages in countries endpoint"""

    def test_countries_include_languages(self):
        """Test that countries endpoint includes country_languages"""
        response = client.get("/auth/countries")
        assert response.status_code == 200
        countries = response.json()
        
        for country in countries:
            assert "country_languages" in country
            assert isinstance(country["country_languages"], list)
            
            # If languages exist, verify structure
            for lang in country["country_languages"]:
                assert "id" in lang
                assert "language_code" in lang
                assert "language_name" in lang
                assert "is_default" in lang
                assert "is_active" in lang


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

