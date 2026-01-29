"""
Synapic Wizard Steps
====================

This package contains the individual frames representing the four steps of 
the tagging wizard.

Classes:
--------
- Step1Datasource: Initial image selection and DAM configuration.
- Step2Tagging: AI model selection and engine configuration.
- Step3Process: Execution monitoring and progress tracking.
- Step4Results: Final session summary and review dashboard.
"""

from .step1_datasource import Step1Datasource
from .step2_tagging import Step2Tagging
from .step3_process import Step3Process
from .step4_results import Step4Results
