import unittest
from src.core.session import EngineConfig

class TestEngineConfigDefaults(unittest.TestCase):
    def test_defaults(self):
        cfg = EngineConfig()
        # Verify new probability scoring fields have expected defaults
        self.assertFalse(cfg.probability_enabled, "probability_enabled should default to False")
        self.assertIsInstance(cfg.probability_candidates, list, "probability_candidates should be a list")
        self.assertEqual(cfg.probability_candidates, [], "probability_candidates should default to empty list")
        self.assertIsInstance(cfg.probability_threshold, float, "probability_threshold should be a float")
        self.assertEqual(cfg.probability_threshold, 0.0, "probability_threshold should default to 0.0")

if __name__ == "__main__":
    unittest.main()
