"""
UI Logic Tests for Provider Tab Local
=====================================

These tests isolate the provider tab local UI behavior from the real CustomTkinter
stack by replacing windowing modules with mocks.
"""

import pytest
from unittest.mock import MagicMock, patch
import sys

# -------------------------------------------------------------------------
# MOCKING UI LIBRARIES
# -------------------------------------------------------------------------
module_mock = MagicMock()

# Define a real class for CTkFrame so inheritance works normally
class MockCTkFrame:
    """Tiny stand-in base class that satisfies the widget API used by the tests."""
    def __init__(self, *args, **kwargs): pass
    def grid(self, *args, **kwargs): pass
    def pack(self, *args, **kwargs): pass
    def place(self, *args, **kwargs): pass
    def configure(self, **kwargs): pass
    def cget(self, *args, **kwargs): return ""
    def winfo_children(self): return []
    def grid_columnconfigure(self, *args, **kwargs): pass
    def grid_rowconfigure(self, *args, **kwargs): pass

# Patch before importing the module
sys.modules['customtkinter'] = module_mock
module_mock.CTkFrame = MockCTkFrame
module_mock.CTkLabel = MockCTkFrame
module_mock.CTkButton = MockCTkFrame
module_mock.CTkCheckBox = MockCTkFrame
module_mock.CTkEntry = MockCTkFrame
module_mock.CTkTextbox = MockCTkFrame
module_mock.CTkSwitch = MockCTkFrame
module_mock.CTkComboBox = MockCTkFrame
module_mock.CTkScrollbar = MockCTkFrame
module_mock.CTkProgressBar = MockCTkFrame
module_mock.CTkSlider = MockCTkFrame
module_mock.CTkSwitch = MockCTkFrame
module_mock.CTkTabview = MockCTkFrame
module_mock.CTkFont = MagicMock()

# Now we can import the module
from src.ui.steps.provider_tab_local import LocalProviderTab

def test_local_ui_populates_engine():
    """Test that save_to_session() populates engine from UI controls."""
    # Create a mock session
    class MockSession:
        def __init__(self):
            self.engine = MagicMock()

    session = MockSession()

    # Create the tab
    tab = LocalProviderTab(parent=None, session=session, worker=None, persist_preference_callback=None, filter_image_models_func=None)

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

def test_local_ui_refresh():
    """Test that refresh() reads session values into UI controls."""
    # Create a mock session with engine
    class MockSession:
        def __init__(self):
            self.engine = MagicMock()
            self.engine.probability_enabled = True
            self.engine.probability_candidates = ["X", "Y", "Z"]
            self.engine.probability_threshold = 0.1

    session = MockSession()

    # Create the tab
    tab = LocalProviderTab(parent=None, session=session, worker=None, persist_preference_callback=None, filter_image_models_func=None)

    # Call refresh
    tab.refresh()

    # Verify UI reflects session
    assert tab.probability_enabled.get() == 1  # selected
    assert tab.candidate_box.get("1.0", "end-1c") == "X,Y,Z"
    assert tab.threshold_entry.get() == "0.1"