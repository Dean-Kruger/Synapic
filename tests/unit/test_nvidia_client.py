import unittest
from unittest.mock import patch, MagicMock
from src.integrations.nvidia_client import NvidiaClient

class TestNvidiaClient(unittest.TestCase):
    def setUp(self):
        self.api_key = "test_key"
        self.client = NvidiaClient(api_key=self.api_key)

    @patch('src.integrations.nvidia_client.requests.Session.get')
    def test_list_models(self, mock_get):
        # Mock response for listing models
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"id": "mistralai/mistral-large-3-675b-instruct-2512"},
                {"id": "nvidia/llama-3.1-405b-instruct"}
            ]
        }
        mock_get.return_value = mock_resp

        models = self.client.list_models()
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0]['id'], "mistralai/mistral-large-3-675b-instruct-2512")
        self.assertEqual(models[0]['provider'], "Nvidia")

    @patch('src.integrations.nvidia_client.requests.Session.post')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data=b"fake_image_data")
    def test_chat_with_image(self, mock_file, mock_exists, mock_post):
        mock_exists.return_value = True
        
        # Mock response for chat completion
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '{"description": "A beautiful landscape", "category": "Nature", "keywords": ["mountains", "lake"]}'
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        response = self.client.chat_with_image(
            model_name="mistralai/mistral-large-3-675b-instruct-2512",
            prompt="Analyze this image",
            image_path="test.png"
        )

        self.assertIn("description", response)
        self.assertIn("A beautiful landscape", response)
        mock_post.assert_called_once()
        
        # Check payload
        args, kwargs = mock_post.call_args
        payload = kwargs['json']
        self.assertEqual(payload['model'], "mistralai/mistral-large-3-675b-instruct-2512")
        self.assertTrue(payload['messages'][0]['content'].startswith("Analyze this image"))
        self.assertIn("data:image/png;base64,", payload['messages'][0]['content'])

if __name__ == '__main__':
    unittest.main()
