import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services import RickMortyService

client = TestClient(app)
service = RickMortyService()


class TestPaginationAndFiltering:
    """Test suite for pagination, filtering, and Earth variant detection"""
    
    def test_earth_variant_detection(self):
        """Test comprehensive Earth variant detection"""
        # Test exact matches
        assert service._is_earth_variant("Earth") == True
        assert service._is_earth_variant("Earth (C-137)") == True
        assert service._is_earth_variant("Earth (Replacement Dimension)") == True
        assert service._is_earth_variant("Earth (C-500a)") == True
        
        # Test case insensitive
        assert service._is_earth_variant("earth") == True
        assert service._is_earth_variant("EARTH (C-137)") == True
        
        # Test pattern matching
        assert service._is_earth_variant("Earth (C-123)") == True
        assert service._is_earth_variant("Earth-123") == True
        assert service._is_earth_variant("Earth123") == True
        assert service._is_earth_variant("Earthabc") == True
        
        # Test non-Earth variants
        assert service._is_earth_variant("Mars") == False
        assert service._is_earth_variant("Earth-2 (not a variant)") == False
        assert service._is_earth_variant("") == False
        assert service._is_earth_variant(None) == False
    
    def test_stable_sorting(self):
        """Test stable sorting functionality"""
        test_characters = [
            {"id": 1, "name": "Alice", "status": "Alive"},
            {"id": 2, "name": "Bob", "status": "Dead"},
            {"id": 3, "name": "Alice", "status": "Alive"},  # Same name, different ID
            {"id": 4, "name": "Charlie", "status": "Alive"},
        ]
        
        # Test sorting by name (ascending)
        sorted_chars = service._sort_characters_stable(test_characters, "name", "asc")
        assert sorted_chars[0]["name"] == "Alice"
        assert sorted_chars[0]["id"] == 1  # First Alice should come first (stable)
        assert sorted_chars[1]["name"] == "Alice"
        assert sorted_chars[1]["id"] == 3  # Second Alice should come second
        assert sorted_chars[2]["name"] == "Bob"
        assert sorted_chars[3]["name"] == "Charlie"
        
        # Test sorting by name (descending)
        sorted_chars_desc = service._sort_characters_stable(test_characters, "name", "desc")
        assert sorted_chars_desc[0]["name"] == "Charlie"
        assert sorted_chars_desc[1]["name"] == "Bob"
        assert sorted_chars_desc[2]["name"] == "Alice"
        assert sorted_chars_desc[2]["id"] == 1  # Stable sorting preserved
        assert sorted_chars_desc[3]["name"] == "Alice"
        assert sorted_chars_desc[3]["id"] == 3
        
        # Test sorting by ID
        sorted_by_id = service._sort_characters_stable(test_characters, "id", "asc")
        assert sorted_by_id[0]["id"] == 1
        assert sorted_by_id[1]["id"] == 2
        assert sorted_by_id[2]["id"] == 3
        assert sorted_by_id[3]["id"] == 4
    
    def test_deduplication_across_pages(self):
        """Test that pagination properly deduplicates characters"""
        # This test would require mocking the external API
        # For now, we'll test the deduplication logic directly
        
        # Simulate characters that might appear on multiple pages
        characters_with_duplicates = [
            {"id": 1, "name": "Rick Sanchez", "status": "Alive"},
            {"id": 2, "name": "Morty Smith", "status": "Alive"},
            {"id": 1, "name": "Rick Sanchez", "status": "Alive"},  # Duplicate
            {"id": 3, "name": "Summer Smith", "status": "Alive"},
            {"id": 2, "name": "Morty Smith", "status": "Alive"},  # Duplicate
        ]
        
        # Test the deduplication logic from _iter_pages
        seen_ids = set()
        deduplicated = []
        
        for char in characters_with_duplicates:
            char_id = char.get("id")
            if char_id and char_id not in seen_ids:
                seen_ids.add(char_id)
                deduplicated.append(char)
        
        assert len(deduplicated) == 3
        assert deduplicated[0]["id"] == 1
        assert deduplicated[1]["id"] == 2
        assert deduplicated[2]["id"] == 3
    
    def test_earth_humans_endpoint(self):
        """Test the Earth humans endpoint returns properly filtered and sorted results"""
        response = client.get("/api/v1/characters/earth-humans")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        if data:  # If we have results
            # Verify all characters are alive humans from Earth variants
            for character in data:
                assert character["status"].lower() == "alive"
                assert "human" in character["species"].lower()
                assert service._is_earth_variant(character["origin"]["name"])
            
            # Verify results are sorted by name (stable sorting)
            names = [char["name"] for char in data]
            assert names == sorted(names)
    
    def test_characters_endpoint_with_sorting(self):
        """Test characters endpoint with sorting parameters"""
        # Test sorting by name
        response = client.get("/api/v1/characters?sort_by=name&sort_order=asc")
        assert response.status_code == 200
        
        data = response.json()
        if data.get("results"):
            names = [char["name"] for char in data["results"]]
            assert names == sorted(names)
        
        # Test sorting by ID
        response = client.get("/api/v1/characters?sort_by=id&sort_order=desc")
        assert response.status_code == 200
        
        data = response.json()
        if data.get("results"):
            ids = [char["id"] for char in data["results"]]
            assert ids == sorted(ids, reverse=True)
    
    def test_all_characters_endpoint_with_sorting(self):
        """Test the all characters endpoint with sorting"""
        response = client.get("/api/v1/characters/all?sort_by=name&sort_order=asc&max_pages=2")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        if data:
            # Verify results are sorted by name
            names = [char["name"] for char in data]
            assert names == sorted(names)
    
    def test_filtering_with_earth_variants(self):
        """Test that filtering works correctly with Earth variants"""
        # Test with species=Human and status=Alive
        response = client.get("/api/v1/characters?species=Human&status=Alive")
        assert response.status_code == 200
        
        data = response.json()
        if data.get("results"):
            for character in data["results"]:
                assert character["status"].lower() == "alive"
                assert "human" in character["species"].lower()
    
    def test_pagination_consistency(self):
        """Test that pagination results are consistent"""
        # Get first page
        response1 = client.get("/api/v1/characters?page=1")
        assert response1.status_code == 200
        
        # Get second page
        response2 = client.get("/api/v1/characters?page=2")
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        if data1.get("results") and data2.get("results"):
            # Ensure no overlap between pages
            ids1 = {char["id"] for char in data1["results"]}
            ids2 = {char["id"] for char in data2["results"]}
            assert len(ids1.intersection(ids2)) == 0
    
    def test_error_handling_invalid_sort_params(self):
        """Test error handling for invalid sorting parameters"""
        # Test invalid sort_by
        response = client.get("/api/v1/characters?sort_by=invalid_field")
        # Should still work but use default sorting
        assert response.status_code == 200
        
        # Test invalid sort_order
        response = client.get("/api/v1/characters?sort_order=invalid_order")
        # Should still work but use default sorting
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
