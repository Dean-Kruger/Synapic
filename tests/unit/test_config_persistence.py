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
    session.engine.probability_candidates = ["A", "B", "C", "D"]
    session.engine.probability_threshold = 0.35

    cfg_path = tmp_path / "synapic_config.json"
    with patch.object(config_manager, "CONFIG_PATH", cfg_path):
        config_manager.save_config(session)

        loaded = Session()
        config_manager.load_config(loaded)

    assert loaded.engine.probability_enabled is True
    assert loaded.engine.probability_candidates == ["A", "B", "C", "D"]
    assert loaded.engine.probability_threshold == 0.35


def test_probability_settings_default_when_no_config(tmp_path):
    """Without a config file the engine keeps its safe defaults."""
    session = Session()
    cfg_path = tmp_path / "missing.json"
    with patch.object(config_manager, "CONFIG_PATH", cfg_path):
        config_manager.load_config(session)

    assert session.engine.probability_enabled is False
    assert session.engine.probability_candidates == []
    assert session.engine.probability_threshold == 0.0
