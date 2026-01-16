import unittest
from unittest.mock import patch, MagicMock
from src.utils.daminion_api import DaminionAPI, DaminionAuthenticationError

class TestDaminionAPI(unittest.TestCase):
    def setUp(self):
        self.base_url = "http://fake-daminion.com"
        self.api = DaminionAPI(self.base_url, "user", "pass")

    @patch('requests.Session.post')
    def test_authenticate_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = self.api.authenticate()
        
        self.assertTrue(result)
        self.assertTrue(self.api.authenticated)
        mock_post.assert_called_with(
            f"{self.base_url}/api/UserManager/Login",
            params={'userName': 'user', 'password': 'pass'},
            timeout=30
        )

    @patch('requests.Session.request')
    def test_get_media_item(self, mock_request):
        self.api.authenticated = True
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 123, "name": "test.jpg"}
        mock_request.return_value = mock_response

        item = self.api.get_media_item(123)
        
        self.assertEqual(item["id"], 123)
        mock_request.assert_called_with(
            "GET",
            f"{self.base_url}/api/MediaItems?id=123",
            timeout=30
        )

    @patch('requests.Session.request')
    def test_search_media_items(self, mock_request):
        self.api.authenticated = True
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"total": 1, "items": []}
        mock_request.return_value = mock_response

        self.api.search_media_items(query="vacation", page_size=50)
        
        mock_request.assert_called_with(
            "GET",
            f"{self.base_url}/api/MediaItems/Get",
            params={'query': 'vacation', 'index': 0, 'size': 50},
            timeout=30
        )

    @patch('requests.Session.request')
    def test_approve_items(self, mock_request):
        self.api.authenticated = True
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = True
        mock_request.return_value = mock_response

        self.api.approve_items([1, 2, 3])
        
        mock_request.assert_called_with(
            "POST",
            f"{self.base_url}/api/MediaItems/ApproveItems",
            json=[1, 2, 3],
            timeout=30
        )

if __name__ == '__main__':
    unittest.main()
