import pytest

from src.core.session import DatasourceConfig, EngineConfig, Session


def test_default_datasource_and_engine_configs():
    ds = DatasourceConfig()
    eng = EngineConfig()

    # Defaults as defined in the dataclasses
    assert ds.type == "local"
    assert isinstance(ds.local_path, str)
    assert eng.provider in ("local", "huggingface", "openrouter")


def test_session_initializes_defaults():
    s = Session()
    assert isinstance(s.datasource, DatasourceConfig)
    assert isinstance(s.engine, EngineConfig)
    # Daminion client starts as None
    assert s.daminion_client is None
    # Basic processing state defaults
    assert s.total_items == 0
    assert s.processed_items == 0
    assert s.failed_items == 0
    assert isinstance(s.results, list)
