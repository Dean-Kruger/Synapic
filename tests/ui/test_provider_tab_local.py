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

    def winfo_rootx(self):
        return 0

    def winfo_rooty(self):
        return 0

    def winfo_height(self):
        return 20

    def winfo_width(self):
        return 200

    def grid_columnconfigure(self, *args, **kwargs):
        pass

    def grid_rowconfigure(self, *args, **kwargs):
        pass

    def bind(self, *args, **kwargs):
        pass

    def focus_set(self):
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


class MockLabel(MockWidget):
    """Label stand-in that records the last configured text."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._text = kwargs.get("text", "")

    def configure(self, **kwargs):
        if "text" in kwargs:
            self._text = kwargs["text"]


class MockSlider(MockWidget):
    """Slider stand-in: set()/get() track a float value."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._value = kwargs.get("from_", 0.0)

    def set(self, value):
        self._value = value

    def get(self):
        return self._value


class MockRadioButton(MockWidget):
    """Radio button stand-in: select() sets the shared variable to this value."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._variable = kwargs.get("variable")
        self._value = kwargs.get("value")

    def select(self):
        if self._variable is not None:
            self._variable.set(self._value)

    def get(self):
        if self._variable is None:
            return 0
        return 1 if self._variable.get() == self._value else 0


# Patch before importing the module
sys.modules["customtkinter"] = module_mock
module_mock.CTkFrame = MockWidget
module_mock.CTkLabel = MockLabel
module_mock.CTkButton = MockWidget
module_mock.CTkCheckBox = MockCheckBox
module_mock.CTkEntry = MockEntry
module_mock.CTkTextbox = MockTextbox
module_mock.CTkSwitch = MockWidget
module_mock.CTkComboBox = MockWidget
module_mock.CTkScrollbar = MockWidget
module_mock.CTkProgressBar = MockWidget
module_mock.CTkSlider = MockSlider
module_mock.CTkRadioButton = MockRadioButton
module_mock.CTkTabview = MockWidget
module_mock.CTkFont = MagicMock()
module_mock.CTkToplevel = MockWidget
module_mock.StringVar = MockStringVar

# Another test module (tests/test_ui_dedup.py) may already have imported the
# provider tab classes with a *different* customtkinter stand-in (one whose
# CTkFrame lacks grid_columnconfigure). Drop the cached copies so this file's
# mock is used and ProviderTabBase inheritance resolves correctly.
for _name in ("src.ui.steps.provider_tab_base", "src.ui.steps.provider_tab_local"):
    sys.modules.pop(_name, None)

# Now we can import the module
from src.ui.steps.provider_tab_local import LocalProviderTab


class MockEngine:
    provider = "local"
    model_id = ""
    task = "image-classification"
    probability_enabled = False
    probability_mode = "llm"
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
    tab.mode_both.select()  # simulate selecting "Both" mode
    tab.candidate_entry.delete(0, "end")
    tab.candidate_entry.insert(0, "A,B,C,D")
    tab.threshold_slider.set(0.05)

    # Call save_to_session
    tab.save_to_session()

    # Verify engine was updated
    assert session.engine.probability_mode == "both"
    assert session.engine.probability_enabled == True
    assert session.engine.probability_candidates == ["A", "B", "C", "D"]
    assert session.engine.probability_threshold == 0.05


def test_local_ui_parses_candidates_one_per_line():
    """Candidates may be newline-separated as well as comma-separated."""
    session = MockSession()
    tab = make_tab(session)

    tab.mode_probability.select()
    tab.candidate_entry.delete(0, "end")
    tab.candidate_entry.insert(0, "cat\ndog\nbird")
    tab.threshold_slider.set(0.5)

    tab.save_to_session()

    assert session.engine.probability_mode == "probability"
    assert session.engine.probability_candidates == ["cat", "dog", "bird"]
    assert session.engine.probability_threshold == 0.5


def test_local_ui_threshold_reads_from_slider():
    """The threshold comes from the slider and lands in the engine."""
    session = MockSession()
    tab = make_tab(session)

    tab.mode_both.select()
    tab.threshold_slider.set(0.6)
    tab.save_to_session()
    assert session.engine.probability_threshold == 0.6

    tab.threshold_slider.set(0.0)
    tab.save_to_session()
    assert session.engine.probability_threshold == 0.0


def test_local_ui_refresh_clamps_out_of_range_threshold():
    """Refresh clamps out-of-range session thresholds into 0.0-1.0 and shows
    the percentage in the value label."""
    session = MockSession(enabled=True, candidates=["X"], threshold=5.0)
    tab = make_tab(session)

    tab.refresh()

    assert tab.threshold_slider.get() == 1.0
    assert tab.threshold_value_label._text == "100%"


def test_local_ui_refresh():
    """Test that refresh() reads session values into UI controls."""
    session = MockSession(enabled=True, candidates=["X", "Y", "Z"], threshold=0.1)
    tab = make_tab(session)

    # Call refresh
    tab.refresh()

    # Verify UI reflects session
    assert tab.probability_mode_var.get() == "both"  # enabled session -> both
    assert tab.candidate_entry.get() == "X,Y,Z"
    assert tab.threshold_slider.get() == 0.1
    assert tab.threshold_value_label._text == "10%"


def test_save_local_persists_probability_settings(tmp_path):
    """save_local() must write the probability settings into the engine and
    the config file so they survive an application restart."""
    session = Session()
    tab = make_tab(session)

    tab.mode_both.select()
    tab.candidate_entry.delete(0, "end")
    tab.candidate_entry.insert(0, "cat,dog")
    tab.threshold_slider.set(0.25)

    cfg_path = tmp_path / "synapic_config.json"
    with patch.object(config_manager, "CONFIG_PATH", cfg_path):
        tab.save_local()

    # Engine reflects the UI immediately
    assert session.engine.probability_mode == "both"
    assert session.engine.probability_enabled is True
    assert session.engine.probability_candidates == ["cat", "dog"]
    assert session.engine.probability_threshold == 0.25

    # A brand-new session (simulating a restart) restores the same values
    fresh = Session()
    with patch.object(config_manager, "CONFIG_PATH", cfg_path):
        config_manager.load_config(fresh)
    assert fresh.engine.probability_mode == "both"
    assert fresh.engine.probability_enabled is True
    assert fresh.engine.probability_candidates == ["cat", "dog"]
    assert fresh.engine.probability_threshold == 0.25


def test_probability_section_toggle():
    """The probability controls show only when the mode is not LLM-only."""
    session = MockSession(enabled=False)
    tab = make_tab(session)

    # LLM-only session: the section starts collapsed after setup sync
    assert tab.probability_mode_var.get() == "llm"
    assert tab.probability_content.winfo_viewable() == 0  # hidden

    # Probability only -> expands
    tab.mode_probability.select()
    tab._toggle_probability_section()
    assert tab.probability_content.winfo_viewable() == 1  # visible

    # Back to LLM only -> collapses
    tab.mode_llm.select()
    tab._toggle_probability_section()
    assert tab.probability_content.winfo_viewable() == 0  # hidden

    # Both -> expands
    tab.mode_both.select()
    tab._toggle_probability_section()
    assert tab.probability_content.winfo_viewable() == 1  # visible


def test_local_ui_llm_only_mode_disables_probability():
    """LLM-only mode maps to probability_enabled=False in the engine."""
    session = MockSession()
    tab = make_tab(session)

    tab.mode_llm.select()
    tab.save_to_session()

    assert session.engine.probability_mode == "llm"
    assert session.engine.probability_enabled is False


def test_select_local_model_preloads_candidate_tokens():
    """Selecting a model fills the candidate box with its label set."""
    session = MockSession()
    tab = make_tab(session)

    from src.core import huggingface_utils

    with patch.object(
        huggingface_utils,
        "get_model_label_tokens",
        return_value=["cat", "dog", "bird"],
    ):
        tab.select_local_model("org/model")

    assert tab.local_model_var.get() == "org/model"
    assert tab.candidate_entry.get() == "cat,dog,bird"


def test_select_local_model_without_labels_keeps_candidates():
    """Models without a label set (e.g. captioning VLMs) leave the candidate
    box unchanged."""
    session = MockSession()
    tab = make_tab(session)

    tab.candidate_entry.delete(0, "end")
    tab.candidate_entry.insert(0, "A,B,C,D")

    from src.core import huggingface_utils

    with patch.object(huggingface_utils, "get_model_label_tokens", return_value=[]):
        tab.select_local_model("org/model")

    assert tab.candidate_entry.get() == "A,B,C,D"
