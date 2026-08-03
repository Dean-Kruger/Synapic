"""
Synapic Wizard Steps
====================

This package contains the individual frames representing the steps of
the tagging wizard.

Classes:
--------
- Step1Datasource: Initial image selection and DAM configuration.
- Step2Tagging: AI model selection and engine configuration.
- Step3Process: Execution monitoring and progress tracking.
- Step4Results: Final session summary and review dashboard.
- StepDedup: Deduplication detection and management.
"""

from .step1_datasource import Step1Datasource  # noqa: F401
from .step2_tagging import Step2Tagging  # noqa: F401
from .step3_process import Step3Process  # noqa: F401
from .step4_results import Step4Results  # noqa: F401

from .step_dedup import StepDedup  # noqa: F401
from .step_upscale import StepUpscale  # noqa: F401
