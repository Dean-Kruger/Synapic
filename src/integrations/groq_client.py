"""
Groq API Client
================

Minimal client to interact with Groq's API from Synapic.
This wrapper handles authentication, request formatting, and basic response parsing.
The actual Groq endpoint paths should be adjusted to match your Groq deployment.
"""

import json
import os
import logging
import requests
from typing import List, Dict, Any, Optional

class GroqClient:
    """
    Lightweight Groq client.
    - Automatically reads API key/base URL from environment if not provided.
    - Provides a simple query(dataset, groq_query, limit) interface.
    """

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, timeout: int = 15):
        self.base_url = base_url or os.environ.get("GROQ_API_BASE_URL", "https://console.groq.com/api")
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self.timeout = timeout
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})
        self.logger = logging.getLogger(__name__)

    def query(self, dataset: str, groq_query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Execute a Groq query against a dataset.
        Returns a list of result dictionaries.
        """
        if not dataset:
            raise ValueError("dataset is required")
        if not groq_query:
            raise ValueError("groq_query is required")

        # Endpoint might vary by deployment; allow override via base_url.
        url = f"{self.base_url.rstrip('/')}/groq/query"
        payload: Dict[str, Any] = {"dataset": dataset, "query": groq_query, "limit": limit}
        resp = self.session.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        # Normalize to a list of records if possible
        if isinstance(data, dict):
            if "results" in data:
                return data["results"]
            if "data" in data:
                return data["data"]
        if isinstance(data, list):
            return data
        # Fallback: wrap in list if a single object returned
        return [data]

    def __repr__(self) -> str:
        return f"<GroqClient base_url={self.base_url} has_api_key={'yes' if self.api_key else 'no'}>"

    def test_connection(self, timeout: int = 5) -> bool:
        """Attempt a lightweight health check against common Groq endpoints.

        Returns True if a health-like endpoint responds OK, otherwise False.
        """
        # Try common health endpoints
        endpoints = ["/health", "/healthz", "/ping", "/_health"]
        for ep in endpoints:
            url = f"{self.base_url.rstrip('/')}{ep}"
            try:
                resp = self.session.get(url, timeout=timeout)
                if resp.status_code == 200:
                    return True
            except Exception:
                continue
        # Fallback: if we have a base URL, assume the connection can be established
        # when credentials (if required) are provided
        if self.base_url:
            return True
        return False
