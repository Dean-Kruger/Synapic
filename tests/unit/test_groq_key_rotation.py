"""
Tests for Groq API Key Rotation Helpers
=======================================

Covers ``EngineConfig._next_available_key_index`` and the rotation helpers
built on top of it (``groq_api_key`` property, ``rotate_groq_key``, and
``mark_groq_key_exhausted``). These were extracted in WR-01 to remove the
duplicated exhausted-key scanning loops, so the tests pin down the exact
semantics the refactor must preserve:

- The active key is the first non-exhausted key at/after the rotation index
  (wrapping around).
- When every key is exhausted, the property falls back to the current
  rotation index instead of crashing or returning an exhausted key silently.
- rotate_groq_key advances to the *next* non-exhausted key and never returns
  the current one unless no other key is available.
"""


from src.core.session import EngineConfig


class TestNextAvailableKeyIndex:
    """Tests for the low-level _next_available_key_index helper."""

    def test_no_keys_returns_none(self):
        cfg = EngineConfig()
        assert cfg._next_available_key_index(0) is None

    def test_returns_start_index_when_available(self):
        cfg = EngineConfig()
        cfg.groq_api_keys = "key1\nkey2\nkey3"
        assert cfg._next_available_key_index(0) == 0
        assert cfg._next_available_key_index(1) == 1
        assert cfg._next_available_key_index(2) == 2

    def test_skips_exhausted_keys_forward(self):
        cfg = EngineConfig()
        cfg.groq_api_keys = "key1\nkey2\nkey3"
        cfg.mark_groq_key_exhausted("key1")
        assert cfg._next_available_key_index(0) == 1

    def test_wraps_around_when_start_is_exhausted(self):
        cfg = EngineConfig()
        cfg.groq_api_keys = "key1\nkey2\nkey3"
        cfg.mark_groq_key_exhausted("key3")
        # Starting at the last (exhausted) key must wrap to the first.
        assert cfg._next_available_key_index(2) == 0

    def test_wraps_around_for_start_beyond_end(self):
        cfg = EngineConfig()
        cfg.groq_api_keys = "key1\nkey2\nkey3"
        assert cfg._next_available_key_index(3) == 0
        assert cfg._next_available_key_index(7) == 1

    def test_returns_none_when_all_exhausted(self):
        cfg = EngineConfig()
        cfg.groq_api_keys = "key1\nkey2"
        cfg.mark_groq_key_exhausted("key1")
        cfg.mark_groq_key_exhausted("key2")
        assert cfg._next_available_key_index(0) is None
        assert cfg._next_available_key_index(1) is None

    def test_blank_lines_and_whitespace_are_ignored(self):
        cfg = EngineConfig()
        cfg.groq_api_keys = "  key1  \n\n   \nkey2"
        keys = cfg.get_groq_key_list()
        assert keys == ["key1", "key2"]


class TestGroqApiKeyProperty:
    """Tests for the backward-compatible groq_api_key property."""

    def test_no_keys_returns_empty_string(self):
        cfg = EngineConfig()
        assert cfg.groq_api_key == ""

    def test_returns_active_key_from_rotation_index(self):
        cfg = EngineConfig()
        cfg.groq_api_keys = "key1\nkey2\nkey3"
        assert cfg.groq_api_key == "key1"

    def test_skips_exhausted_keys(self):
        cfg = EngineConfig()
        cfg.groq_api_keys = "key1\nkey2\nkey3"
        cfg.mark_groq_key_exhausted("key1")
        assert cfg.groq_api_key == "key2"

    def test_falls_back_to_current_index_when_all_exhausted(self):
        cfg = EngineConfig()
        cfg.groq_api_keys = "key1\nkey2"
        cfg.groq_current_key_index = 1
        cfg.mark_groq_key_exhausted("key1")
        cfg.mark_groq_key_exhausted("key2")
        # All exhausted: property must not crash and returns the key at the
        # current rotation index so callers can surface the exhaustion error.
        assert cfg.groq_api_key == "key2"

    def test_setter_replaces_single_key(self):
        cfg = EngineConfig()
        cfg.groq_api_key = "new-key"
        assert cfg.groq_api_keys == "new-key"
        assert cfg.groq_api_key == "new-key"


class TestRotateGroqKey:
    """Tests for rotate_groq_key advancing to the next available key."""

    def test_no_keys_returns_empty_string(self):
        cfg = EngineConfig()
        assert cfg.rotate_groq_key() == ""

    def test_advances_to_next_key(self):
        cfg = EngineConfig()
        cfg.groq_api_keys = "key1\nkey2\nkey3"
        assert cfg.rotate_groq_key() == "key2"
        assert cfg.groq_current_key_index == 1

    def test_wraps_around_to_first_key(self):
        cfg = EngineConfig()
        cfg.groq_api_keys = "key1\nkey2"
        cfg.groq_current_key_index = 1
        assert cfg.rotate_groq_key() == "key1"
        assert cfg.groq_current_key_index == 0

    def test_skips_exhausted_key_while_rotating(self):
        cfg = EngineConfig()
        cfg.groq_api_keys = "key1\nkey2\nkey3"
        cfg.mark_groq_key_exhausted("key2")
        assert cfg.rotate_groq_key() == "key3"
        assert cfg.groq_current_key_index == 2

    def test_wraps_past_exhausted_tail(self):
        cfg = EngineConfig()
        cfg.groq_api_keys = "key1\nkey2\nkey3"
        cfg.groq_current_key_index = 2
        cfg.mark_groq_key_exhausted("key2")
        # From key3, rotation wraps to key1 (key2 is exhausted).
        assert cfg.rotate_groq_key() == "key1"

    def test_keeps_current_index_when_all_exhausted(self):
        cfg = EngineConfig()
        cfg.groq_api_keys = "key1\nkey2"
        cfg.mark_groq_key_exhausted("key1")
        cfg.mark_groq_key_exhausted("key2")
        cfg.groq_current_key_index = 0
        # No available key to rotate to: index stays put, key is still returned.
        assert cfg.rotate_groq_key() == "key1"
        assert cfg.groq_current_key_index == 0


class TestMarkGroqKeyExhausted:
    """Tests for mark_groq_key_exhausted."""

    def test_adds_key_to_exhausted_set(self):
        cfg = EngineConfig()
        cfg.groq_api_keys = "key1\nkey2"
        cfg.mark_groq_key_exhausted("key1")
        assert "key1" in cfg.groq_exhausted_keys
        assert "key2" not in cfg.groq_exhausted_keys

    def test_ignores_empty_key(self):
        cfg = EngineConfig()
        cfg.mark_groq_key_exhausted("")
        cfg.mark_groq_key_exhausted(None)
        assert cfg.groq_exhausted_keys == set()

    def test_exhausted_keys_reset_on_new_session(self):
        cfg = EngineConfig()
        cfg.groq_api_keys = "key1\nkey2"
        cfg.mark_groq_key_exhausted("key1")
        assert "key1" in cfg.groq_exhausted_keys
        # Reset stats (as ProcessingManager does per job) clears the set.
        cfg.groq_exhausted_keys.clear()
        assert cfg.groq_exhausted_keys == set()
        assert cfg.groq_api_key == "key1"


class TestRotationEndToEnd:
    """Full rotation cycle simulating a run with quota exhaustion."""

    def test_cycles_through_all_keys_then_exhausts(self):
        cfg = EngineConfig()
        cfg.groq_api_keys = "key1\nkey2\nkey3"

        used = []
        for _ in range(3):
            used.append(cfg.groq_api_key)
            cfg.mark_groq_key_exhausted(cfg.groq_api_key)
            cfg.rotate_groq_key()

        # Every key was used exactly once before any repeats.
        assert used == ["key1", "key2", "key3"]
        assert cfg.groq_exhausted_keys == {"key1", "key2", "key3"}

        # All exhausted: property falls back gracefully.
        assert cfg.groq_api_key in {"key1", "key2", "key3"}
