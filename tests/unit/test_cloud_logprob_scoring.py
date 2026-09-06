"""Unit tests for cloud-provider tier-1 (logprob) scoring clients.

Covers:
- GroqPackageClient.chat_with_image_logprobs: extraction, None when the
  SDK/model lacks logprob support, RuntimeError on transport failures.
- OpenRouterClient.chat_with_image_logprobs: extraction over the HTTP JSON
  shape, None when no logprob payload, RuntimeError on HTTP failures.
- GroqVisionClientAdapter: forwards to the rotating wrapper (tier 3).
- The pipeline's cloud scoring block: a groq_package engine runs tier 1
  through the real ProcessingManager path and stores the scoring payload.
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

if "src.core" not in sys.modules:
    sys.path.insert(0, str(sys.path[0] or "."))

import pytest

from src.core.keyword_scoring_adapters import (
    _build_classification_prompt,
)
from src.core.session import DatasourceConfig, EngineConfig, Session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _FakeAlt:
    def __init__(self, token, logprob):
        self.token = token
        self.logprob = logprob


class _FakeContentItem:
    def __init__(self, top_logprobs):
        self.top_logprobs = top_logprobs


class _FakeLogprobs:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, logprobs):
        self.logprobs = logprobs


class _FakeCompletion:
    def __init__(self, choices):
        self.choices = choices


def _groq_completion(letters):
    """A Groq-shaped completion: one choice, one content item, top_logprobs."""
    top = [_FakeAlt(token=letter, logprob=lp) for letter, lp in letters.items()]
    return _FakeCompletion(
        choices=[
            _FakeChoice(
                logprobs=_FakeLogprobs(content=[_FakeContentItem(top_logprobs=top)])
            )
        ]
    )


@pytest.fixture
def groq_client():
    from src.integrations.groq_package_client import GroqPackageClient

    client = GroqPackageClient(api_key="test-key")
    # Inject a fake SDK client instead of hitting the network.
    client._client = MagicMock()
    client._cached_key = "test-key"
    return client


# ---------------------------------------------------------------------------
# Groq chat_with_image_logprobs
# ---------------------------------------------------------------------------


def test_groq_logprobs_extracts_first_token_alternatives(groq_client, tmp_path):
    img = tmp_path / "img.jpg"
    img.write_bytes(b"fake")

    groq_client._client.chat.completions.create.return_value = _groq_completion(
        {"A": -0.1, "B": -2.3, "C": -4.0}
    )

    result = groq_client.chat_with_image_logprobs(
        model_name="meta-llama/llama-4-scout-17b-16e-instruct",
        prompt="pick a letter",
        image_path=str(img),
    )

    assert result == {"A": -0.1, "B": -2.3, "C": -4.0}
    call_kwargs = groq_client._client.chat.completions.create.call_args.kwargs
    assert call_kwargs["max_tokens"] == 1
    assert call_kwargs["logprobs"] is True
    assert call_kwargs["top_logprobs"] == 20
    assert call_kwargs["temperature"] == 0.0
    # The prompt and the image both reached the message payload.
    content = call_kwargs["messages"][0]["content"]
    assert {"type": "text", "text": "pick a letter"} in content
    assert any(part["type"] == "image_url" for part in content)


def test_groq_logprobs_none_when_sdk_lacks_support(groq_client, tmp_path):
    """Older SDKs reject the logprobs kwargs with TypeError -> None."""
    img = tmp_path / "img.jpg"
    img.write_bytes(b"fake")

    groq_client._client.chat.completions.create.side_effect = TypeError(
        "unexpected keyword argument 'logprobs'"
    )

    result = groq_client.chat_with_image_logprobs(
        model_name="meta-llama/llama-4-scout-17b-16e-instruct",
        prompt="p",
        image_path=str(img),
    )
    assert result is None


def test_groq_logprobs_none_when_model_returns_no_logprob_data(groq_client, tmp_path):
    img = tmp_path / "img.jpg"
    img.write_bytes(b"fake")

    # SDK accepted params but the model ignored logprobs: empty content list.
    groq_client._client.chat.completions.create.return_value = _FakeCompletion(
        choices=[_FakeChoice(logprobs=_FakeLogprobs(content=[]))]
    )

    result = groq_client.chat_with_image_logprobs(
        model_name="meta-llama/llama-4-scout-17b-16e-instruct",
        prompt="p",
        image_path=str(img),
    )
    assert result is None


def test_groq_logprobs_raises_on_transport_error(groq_client, tmp_path):
    img = tmp_path / "img.jpg"
    img.write_bytes(b"fake")

    groq_client._client.chat.completions.create.side_effect = ConnectionError("down")

    with pytest.raises(RuntimeError, match="Groq logprob scoring call failed"):
        groq_client.chat_with_image_logprobs(
            model_name="meta-llama/llama-4-scout-17b-16e-instruct",
            prompt="p",
            image_path=str(img),
        )


# ---------------------------------------------------------------------------
# OpenRouter chat_with_image_logprobs
# ---------------------------------------------------------------------------


def _or_response(payload, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def test_openrouter_logprobs_extracts_from_http_json(tmp_path):
    from src.core.openrouter_utils import OpenRouterClient

    img = tmp_path / "img.jpg"
    img.write_bytes(b"fake")

    client = OpenRouterClient(token="sk-test")
    payload = {
        "choices": [
            {
                "message": {"content": "A"},
                "logprobs": {
                    "content": [
                        {
                            "top_logprobs": [
                                {"token": "A", "logprob": -0.05},
                                {"token": "B", "logprob": -3.2},
                            ]
                        }
                    ]
                },
            }
        ]
    }

    with patch("src.core.openrouter_utils._HTTP_SESSION") as mock_session:
        mock_session.post.return_value = _or_response(payload)
        result = client.chat_with_image_logprobs(
            model_name="google/gemini-flash", prompt="pick", image_path=str(img)
        )

    assert result == {"A": -0.05, "B": -3.2}
    body = mock_session.post.call_args.kwargs["json"]
    assert body["max_tokens"] == 1
    assert body["logprobs"] is True
    assert body["top_logprobs"] == 20


def test_openrouter_logprobs_none_when_no_logprob_payload(tmp_path):
    from src.core.openrouter_utils import OpenRouterClient

    img = tmp_path / "img.jpg"
    img.write_bytes(b"fake")

    client = OpenRouterClient(token="sk-test")
    payload = {"choices": [{"message": {"content": "A"}}]}  # no logprobs key

    with patch("src.core.openrouter_utils._HTTP_SESSION") as mock_session:
        mock_session.post.return_value = _or_response(payload)
        result = client.chat_with_image_logprobs(
            model_name="m", prompt="p", image_path=str(img)
        )

    assert result is None


def test_openrouter_logprobs_raises_on_http_error(tmp_path):
    from src.core.openrouter_utils import OpenRouterClient

    img = tmp_path / "img.jpg"
    img.write_bytes(b"fake")

    client = OpenRouterClient(token="sk-test")
    resp = _or_response({}, status=500)
    resp.raise_for_status.side_effect = RuntimeError("500 server error")

    with patch("src.core.openrouter_utils._HTTP_SESSION") as mock_session:
        mock_session.post.return_value = resp
        with pytest.raises(RuntimeError, match="OpenRouter logprob call failed"):
            client.chat_with_image_logprobs(
                model_name="m", prompt="p", image_path=str(img)
            )


# ---------------------------------------------------------------------------
# GroqVisionClientAdapter (tier 3 protocol)
# ---------------------------------------------------------------------------


def test_groq_vision_adapter_forwards_to_rotating_wrapper():
    from src.integrations.groq_package_client import GroqVisionClientAdapter

    engine = SimpleNamespace()
    inner = MagicMock()
    inner.chat_with_image_rotating.return_value = "ok"

    adapter = GroqVisionClientAdapter(inner, engine)
    out = adapter.chat_with_image(model_name="m", prompt="p", image_path="i.jpg")

    assert out == "ok"
    inner.chat_with_image_rotating.assert_called_once_with(
        engine_config=engine, model="m", prompt="p", image_path="i.jpg"
    )


# ---------------------------------------------------------------------------
# Tier-1 orchestrator integration with the real adapters
# ---------------------------------------------------------------------------


def test_orchestrator_tier1_with_groq_logprobs(tmp_path):
    """Groq logprob client + adapters produce a calibrated tier-1 result."""
    from src.core.keyword_scoring_adapters import score_keywords

    class GroqStub:
        def chat_with_image_logprobs(self, model_name, prompt, image_path):
            assert "A) forest" in prompt  # lettered prompt reached the client
            return {"A": -0.1, "B": -3.0}

    engine = SimpleNamespace(
        provider="groq_package",
        task="image-to-text",
        probability_mode="probability",
        probability_candidates=["forest", "beach"],
        probability_threshold=0.0,
        probability_enabled=True,
        device="cpu",
    )

    result = score_keywords(
        engine,
        "img.jpg",
        logprob_client_factory=lambda: (GroqStub(), "meta-llama/llama-4-scout"),
    )

    assert result.tier is result.tier.LOGPROB
    assert result.calibrated is True
    assert abs(sum(result.score_map.values()) - 1.0) < 1e-9
    assert result.score_map["forest"] > result.score_map["beach"]


def test_orchestrator_falls_back_to_tier3_when_groq_logprobs_none(tmp_path):
    """A logprobs=None response (unsupported) must fall back to tier 3."""
    from src.core.keyword_scoring_adapters import score_keywords

    class GroqStub:
        def chat_with_image_logprobs(self, model_name, prompt, image_path):
            return None  # SDK/model does not support logprobs

    vision = MagicMock()
    vision.chat_with_image.return_value = '{"forest": 0.8, "beach": 0.2}'

    engine = SimpleNamespace(
        provider="groq_package",
        task="image-to-text",
        probability_mode="probability",
        probability_candidates=["forest", "beach"],
        probability_threshold=0.0,
        probability_enabled=True,
        device="cpu",
    )

    result = score_keywords(
        engine,
        "img.jpg",
        logprob_client_factory=lambda: (GroqStub(), "m"),
        vision_client_factory=lambda: (vision, "m"),
    )

    assert result.tier is result.tier.SEMANTIC_JSON
    assert result.calibrated is False


# ---------------------------------------------------------------------------
# Pipeline wiring: cloud scoring block in ProcessingManager
# ---------------------------------------------------------------------------


def make_cloud_session(provider):
    session = Session()
    session.datasource = DatasourceConfig(type="local", local_path=".")
    session.engine = EngineConfig(
        provider=provider,
        model_id="test-model",
        task="image-to-text",
    )
    session.engine.probability_mode = "probability"
    session.engine.probability_enabled = True
    session.engine.probability_candidates = ["forest", "beach"]
    session.engine.probability_threshold = 0.0
    return session


def test_pipeline_runs_tier1_scoring_for_groq(monkeypatch, tmp_path):
    from PIL import Image
    from src.core.processing import ProcessingManager

    img_path = tmp_path / "img.jpg"
    Image.new("RGB", (1, 1), color="black").save(img_path)

    session = make_cloud_session("groq_package")
    logs = []
    manager = ProcessingManager(session, logs.append, MagicMock())

    # Groq client initialized in _run_job; stub its logprob call.
    manager._api_client = MagicMock()
    manager._api_client.chat_with_image_logprobs.return_value = {
        "A": -0.1,
        "B": -3.0,
    }

    # The real score_keywords runs against the stubbed Groq client; the
    # regular tagging path must NOT run in probability-only mode.
    manager._process_single_item(img_path)

    manager._api_client.chat_with_image_logprobs.assert_called_once()
    assert len(session.results) == 1
    entry = session.results[0]
    assert entry["status"] == "Success"
    assert entry["probabilities"]["forest"] > entry["probabilities"]["beach"]
    assert entry["scoring"]["tier"] == "logprob"
    assert entry["scoring"]["calibrated"] is True
    assert any("forest:" in m for m in logs)


def test_pipeline_tier0_keeps_legacy_fallback_for_groq(monkeypatch, tmp_path):
    """When cloud scoring is unavailable, probability-only mode falls back to
    the LLM tagging path instead of producing empty tags."""
    from PIL import Image
    from src.core.processing import ProcessingManager

    img_path = tmp_path / "img.jpg"
    Image.new("RGB", (1, 1), color="black").save(img_path)

    session = make_cloud_session("groq_package")
    logs = []
    manager = ProcessingManager(session, logs.append, MagicMock())

    # Logprob unsupported AND vision fallback fails -> tier 0.
    manager._api_client = MagicMock()
    manager._api_client.chat_with_image_logprobs.return_value = None
    manager._api_client.chat_with_image_rotating.return_value = (
        "Error: something unrecoverable"
    )

    manager._process_single_item(img_path)

    assert len(session.results) == 1
    entry = session.results[0]
    assert entry["status"] == "Success"
    assert "probabilities" not in entry or entry["probabilities"] == {}
    assert any("falling back to LLM" in m for m in logs)
