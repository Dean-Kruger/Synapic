"""
Unit tests for application configuration.
"""

import unittest
from src.core import config

class TestConfig(unittest.TestCase):
    """Test cases for global configuration constants."""
    
    def test_task_mappings(self):
        """Verify that task mappings are consistent."""
        for task_id, display_name in config.TASK_DISPLAY_MAP.items():
            # Check reverse mapping
            self.assertEqual(config.DISPLAY_TASK_MAP[display_name], task_id)
            
    def test_capability_coverage(self):
        """Ensure all standard tasks have mapped capabilities."""
        standard_tasks = [
            config.MODEL_TASK_IMAGE_CLASSIFICATION,
            config.MODEL_TASK_ZERO_SHOT,
            config.MODEL_TASK_IMAGE_TO_TEXT
        ]
        for task in standard_tasks:
            self.assertIn(task, config.CAPABILITY_MAP)
            
    def test_supported_extensions(self):
        """Verify supported image extensions list."""
        self.assertIn("*.jpg", config.SUPPORTED_IMAGE_EXTENSIONS)
        self.assertIn("*.png", config.SUPPORTED_IMAGE_EXTENSIONS)

if __name__ == "__main__":
    unittest.main()
