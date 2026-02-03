import unittest
import json

from src.core.daminion_api import DaminionAPI


class TestApiMetrics(unittest.TestCase):
    def test_metrics_snapshot_structure(self):
        api = DaminionAPI(base_url="https://example.net", username="u", password="p")
        # simulate some state
        api._request_count = 5
        api._latency_by_endpoint = {
            '/api/MediaItems/Get': [10.0, 20.0],
            '/api/Settings/GetVersion': [5.0]
        }
        api._error_counts = {'URLError': 1}

        metrics = api.get_metrics()
        self.assertIn('requests', metrics)
        self.assertIn('latency_ms_by_endpoint', metrics)
        self.assertIn('errors', metrics)
        self.assertIsInstance(metrics['requests'], int)
        self.assertIsInstance(metrics['latency_ms_by_endpoint'], dict)
        self.assertIsInstance(metrics['errors'], dict)

    def test_metrics_json_export(self):
        api = DaminionAPI(base_url="https://example.net", username="u", password="p")
        api._request_count = 2
        api._latency_by_endpoint = {'/a': [1.0]}
        api._error_counts = {}

        json_str = api.get_metrics().__class__
        # Simple sanity: ensure dumping to JSON works
        s = json.dumps(api.get_metrics())
        self.assertIsInstance(s, str)


if __name__ == '__main__':
    unittest.main()
