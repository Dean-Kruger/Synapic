"""
UI Logic Tests for Provider Tab Local
=====================================

These tests isolate the provider tab local UI behavior from the real CustomTkinter
stack by replacing windowing modules with mocks.
"""

import sys
from unittest.mock import MagicMock, patch

from src.core.session import Session
from src.utils import config_manager

# -------------------------------------------------------------------------
# MOCKING UI LIBRARIES
# -------------------------------------------------------------------------
module_mock = MagicMock()


class MockWidget:
    """Minimal stand-in widget that tracks grid visibility for the tests."""

    def __init__(self, *args, **kwargs):
        self._visible = True

    def grid(self, *args, **kwargs):
        self._visible = True

    def grid_remove(self, *args, **kwargs):
        self._visible = False

    def grid_forget(self, *args, **kwargs):
        self._visible = False

    def pack(self, *args, **kwargs):
        pass

    def place(self, *args, **kwargs):
        pass

    def configure(self, **kwargs):
        pass

    def cget(self, *args, **kwargs):
        return ""

    def winfo_children(self):
        return []

    def winfo_viewable(self):
        return 1 if self._visible else 0

    def grid_columnconfigure(self, *args, **kwargs):
        pass

    def grid_rowconfigure(self, *args, **kwargs):
        pass


class MockCheckBox(MockWidget):
    """Checkbox stand-in: select()/deselect()/get() -> 0 or 1."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._selected = False

    def select(self):
        self._selected = True

    def deselect(self):
        self._selected = False

    def get(self):
        return 1 if self._selected else 0


class MockEntry(MockWidget):
    """Entry stand-in: insert()/delete()/get() -> str."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._text = ""

    def insert(self, index, text):
        self._text = str(text)

    def delete(self, first, last=None):
        self._text = ""

    def get(self):
        return self._text


class MockTextbox(MockEntry):
    """Textbox stand-in: same as entry but get() takes index args."""

    def get(self, *args):
        return self._text


class MockStringVar:
    """StringVar stand-in that stores its value like the real Tk variable."""

    def __init__(self, *args, value=None, **kwargs):
        self._value = value

    def set(self, value):
        self._value = value

    def get(self):
        return self._value


# Patch before importing the module
sys.modules["customtkinter"] = module_mock
module_mock.CTkFrame = MockWidget
module_mock.CTkLabel = MockWidget
module_mock.CTkButton = MockWidget
module_mock.CTkCheckBox = MockCheckBox
module_mock.CTkEntry = MockEntry
module_mock.CTkTextbox = MockTextbox
module_mock.CTkSwitch = MockWidget
module_mock.CTkComboBox = MockWidget
module_mock.CTkScrollbar = MockWidget
module_mock.CTkProgressBar = MockWidget
module_mock.CTkSlider = MockWidget
module_mock.CTkTabview = MockWidget
module_mock.CTkFont = MagicMock()
module_mock.StringVar = MockStringVar

# Now we can import the module
from src.ui.steps.provider_tab_local import LocalProviderTab


class MockEngine:
    provider = "local"
    model_id = ""
    task = "image-classification"
    probability_enabled = False
    probability_threshold = 0.0


class MockSession:
    def __init__(self, enabled=False, candidates=None, threshold=0.0):
        self.engine = MockEngine()
        self.engine.probability_enabled = enabled
        self.engine.probability_candidates = list(candidates or [])
        self.engine.probability_threshold = threshold


def make_tab(session):
    return LocalProviderTab(
        parent=None,
        session=session,
        worker=None,
        persist_preference_callback=None,
        filter_image_models_func=None,
    )


def test_local_ui_populates_engine():
    """Test that save_to_session() populates engine from UI controls."""
    session = MockSession()
    tab = make_tab(session)

    # Set UI values
    tab.probability_enabled.select()  # simulate checkbox checked
    tab.candidate_box.delete("1.0", "end")
    tab.candidate_box.insert("1.0", "A,B,C,D")
    tab.threshold_entry.insert(0, "0.05")

    # Call save_to_session
    tab.save_to_session()

    # Verify engine was updated
    assert session.engine.probability_enabled == True
    assert session.engine.probability_candidates == ["A", "B", "C", "D"]
    assert session.engine.probability_threshold == 0.05


def test_local_ui_parses_candidates_one_per_line():
    """Candidates may be newline-separated as well as comma-separated."""
    session = MockSession()
    tab = make_tab(session)

    tab.probability_enabled.select()
    tab.candidate_box.delete("1.0", "end")
    tab.candidate_box.insert("1.0", "cat\ndog\nbird")
    tab.threshold_entry.insert(0, "0.5")

    tab.save_to_session()

    assert session.engine.probability_candidates == ["cat", "dog", "bird"]
    assert session.engine.probability_threshold == 0.5


def test_local_ui_threshold_is_clamped():
    """Thresholds outside 0.0-1.0 are clamped into range."""
    session = MockSession()
    tab = make_tab(session)

    tab.probability_enabled.select()
    tab.threshold_entry.insert(0, "5")
    tab.save_to_session()
    assert session.engine.probability_threshold == 1.0

    tab.threshold_entry.insert(0, "-2")
    tab.save_to_session()
    assert session.engine.probability_threshold == 0.0


def test_local_ui_refresh():
    """Test that refresh() reads session values into UI controls."""
    session = MockSession(enabled=True, candidates=["X", "Y", "Z"], threshold=0.1)
    tab = make_tab(session)

    # Call refresh
    tab.refresh()

    # Verify UI reflects session
    assert tab.probability_enabled.get() == 1  # selected
    assert tab.candidate_box.get("1.0", "end-1c") == "X,Y,Z"
    assert tab.threshold_entry.get() == "0.1"


def test_save_local_persists_probability_settings(tmp_path):
    """save_local() must write the probability settings into the engine and
    the config file so they survive an application restart."""
    session = Session()
    tab = make_tab(session)

    tab.probability_enabled.select()
    tab.candidate_box.delete("1.0", "end")
    tab.candidate_box.insert("1.0", "cat,dog")
    tab.threshold_entry.insert(0, "0.25")

    cfg_path = tmp_path / "synapic_config.json"
    with patch.object(config_manager, "CONFIG_PATH", cfg_path):
        tab.save_local()

    # Engine reflects the UI immediately
    assert session.engine.probability_enabled is True
    assert session.engine.probability_candidates == ["cat", "dog"]
    assert session.engine.probability_threshold == 0.25

    # A brand-new session (simulating a restart) restores the same values
    fresh = Session()
    with patch.object(config_manager, "CONFIG_PATH", cfg_path):
        config_manager.load_config(fresh)
    assert fresh.engine.probability_enabled is True
    assert fresh.engine.probability_candidates == ["cat", "dog"]
    assert fresh.engine.probability_threshold == 0.25


def test_probability_section_toggle():
    """Test that the probability section shows/hides based on checkbox state."""
    session = MockSession(enabled=False)
    tab = make_tab(session)

    # Disabled session: the section starts collapsed after setup sync
    assert tab.probability_content.winfo_viewable() == 0  # hidden

    # Enable -> expands
    tab.probability_enabled.select()
    tab._toggle_probability_section()
    assert tab.probability_content.winfo_viewable() == 1  # visible

    # Disable -> collapses
    tab.probability_enabled.deselect()
    tab._toggle_probability_section()
    assert tab.probability_content.winfo_viewable() == 0  # hidden
