"""
Tests for Session.validate_engine
=================================

These tests verify the engine-configuration validation that gates the start of
a processing job: a model must be selected, local models must be downloaded,
and cloud providers must supply their credential.
"""

from unittest.mock import patch


from src.core.session import Session


def _session_with(**engine_overrides):
    s = Session()
    for key, value in engine_overrides.items():
        setattr(s.engine, key, value)
    return s


def test_missing_model_id_fails():
    s = _session_with(provider="huggingface", model_id="", api_key="key")
    assert s.validate_engine() is False


def test_unknown_provider_fails():
    s = _session_with(provider="made_up", model_id="some/model")
    assert s.validate_engine() is False


def test_cloud_provider_requires_api_key():
    s = _session_with(provider="huggingface", model_id="some/model", api_key="")
    assert s.validate_engine() is False

    s.engine.api_key = "hf_token"
    assert s.validate_engine() is True


def test_cerebras_requires_its_own_key():
    s = _session_with(provider="cerebras", model_id="some/model", cerebras_api_key="")
    assert s.validate_engine() is False

    s.engine.cerebras_api_key = "cb_key"
    assert s.validate_engine() is True


def test_ollama_is_valid_without_api_key_when_host_set():
    s = _session_with(
        provider="ollama",
        model_id="llava",
        ollama_host="http://localhost:11434",
    )
    assert s.validate_engine() is True


def test_ollama_fails_without_host():
    s = _session_with(provider="ollama", model_id="llava", ollama_host="")
    assert s.validate_engine() is False


def test_local_requires_downloaded_model():
    s = _session_with(provider="local", model_id="some/model")

    with patch("src.core.huggingface_utils.is_model_downloaded", return_value=False):
        assert s.validate_engine() is False

    with patch("src.core.huggingface_utils.is_model_downloaded", return_value=True):
        assert s.validate_engine() is True
