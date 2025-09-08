import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services import RickMortyService
from app.models import Character, Location, Episode

# Create test client
client = TestClient(app)

class TestRickMortyAPI:
    """Test suite for Rick & Morty API endpoints"""
    
    def test_root_endpoint(self):
        """Test the root endpoint returns API information"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Rick & Morty API"
        assert data["version"] == "1.0.0"
        assert "endpoints" in data
    
    def test_health_endpoint(self):
        """Test the health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        # During testing without database/Redis, status should be degraded
        assert data["status"] in ["healthy", "degraded"]
        assert "timestamp" in data
        assert "liveness" in data
        assert "readiness" in data
        # Verify external API is working (should be healthy)
        assert data["readiness"]["checks"]["external_api"]["status"] == "healthy"
    
    def test_get_characters_default(self):
        """Test getting characters with default parameters"""
        response = client.get("/api/v1/characters")
        assert response.status_code == 200
        data = response.json()
        assert "info" in data
        assert "results" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) > 0
    
    def test_get_characters_with_filters(self):
        """Test getting characters with filters"""
        response = client.get("/api/v1/characters?status=alive&species=Human")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        # Verify all returned characters are alive and human-related
        for character in data["results"]:
            assert character["status"].lower() == "alive"
            assert "human" in character["species"].lower()
    
    def test_get_characters_invalid_status(self):
        """Test getting characters with invalid status filter"""
        response = client.get("/api/v1/characters?status=invalid")
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Invalid status" in data["detail"]
    
    def test_get_character_by_id(self):
        """Test getting a specific character by ID"""
        response = client.get("/api/v1/characters/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert "name" in data
        assert "status" in data
        assert "species" in data
    
    def test_get_character_invalid_id(self):
        """Test getting a character with invalid ID"""
        response = client.get("/api/v1/characters/99999")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"]
    
    def test_get_multiple_characters(self):
        """Test getting multiple characters by IDs"""
        response = client.get("/api/v1/characters/multiple/1,2,3")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3
        assert data[0]["id"] == 1
        assert data[1]["id"] == 2
        assert data[2]["id"] == 3
    
    def test_get_earth_humans(self):
        """Test getting alive humans from Earth"""
        response = client.get("/api/v1/characters/earth-humans")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Verify all are alive human-related characters from Earth
        for character in data:
            assert character["status"].lower() == "alive"
            assert "human" in character["species"].lower()
            assert character["origin"]["name"].startswith("Earth")


class TestRickMortyService:
    """Test suite for Rick & Morty service layer"""
    
    def setup_method(self):
        """Set up test service instance"""
        self.service = RickMortyService()
    
    def test_service_initialization(self):
        """Test service initialization"""
        assert self.service.base_url == "https://rickandmortyapi.com/api"
        assert self.service.timeout == 10
        assert self.service.max_retries == 3
        assert self.service.base_delay == 1.0
    
    def test_normalize_filter(self):
        """Test filter normalization"""
        assert self.service._normalize_filter("  ALIVE  ") == "alive"
        assert self.service._normalize_filter("Human") == "human"
        assert self.service._normalize_filter(None) is None
        assert self.service._normalize_filter("") == ""
    
    def test_validate_enum(self):
        """Test enum validation"""
        from app.services import CharacterStatus, CharacterGender
        
        assert self.service._validate_enum("alive", CharacterStatus) == True
        assert self.service._validate_enum("dead", CharacterStatus) == True
        assert self.service._validate_enum("invalid", CharacterStatus) == False
        
        assert self.service._validate_enum("male", CharacterGender) == True
        assert self.service._validate_enum("female", CharacterGender) == True
        assert self.service._validate_enum("invalid", CharacterGender) == False


class TestDataModels:
    """Test suite for Pydantic data models"""
    
    def test_character_model(self):
        """Test Character model validation"""
        character_data = {
            "id": 1,
            "name": "Rick Sanchez",
            "status": "Alive",
            "species": "Human",
            "type": "",
            "gender": "Male",
            "origin": {"name": "Earth (C-137)", "url": "https://rickandmortyapi.com/api/location/1"},
            "location": {"name": "Citadel of Ricks", "url": "https://rickandmortyapi.com/api/location/3"},
            "image": "https://rickandmortyapi.com/api/character/avatar/1.jpeg",
            "episode": ["https://rickandmortyapi.com/api/episode/1"],
            "url": "https://rickandmortyapi.com/api/character/1",
            "created": "2017-11-04T18:48:46.250Z"
        }
        
        character = Character(**character_data)
        assert character.id == 1
        assert character.name == "Rick Sanchez"
        assert character.status == "Alive"
        assert character.species == "Human"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
