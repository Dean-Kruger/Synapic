"""Config persistence tests for the probability scoring engine fields."""
from unittest.mock import patch

from src.core.session import Session
from src.utils import config_manager


def test_probability_settings_survive_config_round_trip(tmp_path):
    """probability_enabled/candidates/threshold must persist through
    save_config -> load_config so settings survive an application restart."""
    session = Session()
    session.engine.provider = "local"
    session.engine.probability_enabled = True
    session.engine.probability_mode = "both"
    session.engine.probability_candidates = ["A", "B", "C", "D"]
    session.engine.probability_threshold = 0.35

    cfg_path = tmp_path / "synapic_config.json"
    with patch.object(config_manager, "CONFIG_PATH", cfg_path):
        config_manager.save_config(session)

        loaded = Session()
        config_manager.load_config(loaded)

    assert loaded.engine.probability_enabled is True
    assert loaded.engine.probability_mode == "both"
    assert loaded.engine.probability_candidates == ["A", "B", "C", "D"]
    assert loaded.engine.probability_threshold == 0.35


def test_probability_mode_survives_config_round_trip(tmp_path):
    """The tagging mode (llm/probability/both) persists through save/load."""
    session = Session()
    session.engine.provider = "local"
    session.engine.probability_mode = "probability"
    session.engine.probability_enabled = True

    cfg_path = tmp_path / "synapic_config.json"
    with patch.object(config_manager, "CONFIG_PATH", cfg_path):
        config_manager.save_config(session)

        loaded = Session()
        config_manager.load_config(loaded)

    assert loaded.engine.probability_mode == "probability"
    assert loaded.engine.probability_enabled is True


def test_legacy_enabled_only_config_migrates_to_both(tmp_path):
    """A config written before probability_mode existed (only
    probability_enabled=True) loads as the 'both' mode."""
    import json

    cfg_path = tmp_path / "legacy.json"
    cfg_path.write_text(
        json.dumps({"engine": {"provider": "local", "probability_enabled": True}}),
        encoding="utf-8",
    )

    loaded = Session()
    with patch.object(config_manager, "CONFIG_PATH", cfg_path):
        config_manager.load_config(loaded)

    assert loaded.engine.probability_mode == "both"
    assert loaded.engine.probability_enabled is True


def test_probability_settings_default_when_no_config(tmp_path):
    """Without a config file the engine keeps its safe defaults."""
    session = Session()
    cfg_path = tmp_path / "missing.json"
    with patch.object(config_manager, "CONFIG_PATH", cfg_path):
        config_manager.load_config(session)

    assert session.engine.probability_enabled is False
    assert session.engine.probability_mode == "llm"
    assert session.engine.probability_candidates == []
    assert session.engine.probability_threshold == 0.0
