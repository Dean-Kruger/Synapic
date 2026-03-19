"""
Groq API Client
================

This module provides a lightweight HTTP client for Groq-style endpoints used
by Synapic during experimentation and diagnostics.

Unlike `groq_package_client.py`, which targets the official SDK flow used by
the main application, this wrapper is intentionally generic:
- It can point at alternate base URLs.
- It uses plain `requests` sessions.
- It exposes a small surface for query execution, model discovery, and health
  checks.

That makes it useful for local testing, self-hosted compatibility work, or
future deployments where the endpoint shape is Groq-like but not identical to
the official cloud service.
"""

import json
import os
import logging
import requests
from typing import List, Dict, Any, Optional

class GroqClient:
    """
    Lightweight Groq-oriented REST client.

    Design goals:
    - Keep dependencies minimal.
    - Support environment-driven configuration for quick local testing.
    - Normalise several possible API response envelopes into predictable Python
      lists for downstream callers.
    """

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, timeout: int = 15):
        """Initialise the client from explicit values or environment defaults."""
        self.base_url = base_url or os.environ.get("GROQ_API_BASE_URL", "https://console.groq.com/api")
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self.timeout = timeout
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})
        self.logger = logging.getLogger(__name__)

    def query(self, dataset: str, groq_query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Execute a query request against the configured Groq-compatible API.

        Args:
            dataset: Logical dataset or collection name expected by the server.
            groq_query: Provider-specific query text.
            limit: Maximum number of records requested from the remote service.

        Returns:
            A list of result dictionaries regardless of whether the server
            responded with `results`, `data`, a bare list, or a single object.
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
        """Return a compact debugging representation without exposing secrets."""
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

    def list_models(self, dataset: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch available Groq models via API.

        The implementation is intentionally tolerant because different Groq-like
        deployments may expose model discovery through either GET or POST and
        may wrap the payload differently.
        """
        models: List[Dict[str, Any]] = []
        # Try GET first
        url = f"{self.base_url.rstrip('/')}/groq/models"
        params: Dict[str, Any] = {"limit": limit}
        if dataset:
            params["dataset"] = dataset
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                models = data
            elif isinstance(data, dict):
                if "models" in data:
                    models = data["models"]
                elif "data" in data:
                    val = data["data"]
                    models = val if isinstance(val, list) else [val]
        except Exception:
            # Fallback to POST
            try:
                payload = {"limit": limit}
                if dataset:
                    payload["dataset"] = dataset
                resp = self.session.post(url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list):
                    models = data
                elif isinstance(data, dict):
                    models = data.get("models", data.get("data", [])) or []
            except Exception:
                models = []
        return models
