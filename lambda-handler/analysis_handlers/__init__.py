"""
Analysis Handlers Registry

This module provides a registry of analysis handlers.
Each handler is a standalone module that implements BaseAnalysisHandler.

To add a new handler:
1. Create handler file (e.g., diagnosis_handler.py)
2. Import it here
3. Add to REGISTERED_HANDLERS list
"""

from typing import List
from .base_handler import BaseAnalysisHandler
from .pattern_handler import PatternAnalysisHandler

# Registry of all analysis handlers
# Order matters: handlers are checked in this order
REGISTERED_HANDLERS: List[BaseAnalysisHandler] = [
    PatternAnalysisHandler(),
    # Future handlers will be added here:
    # CorrelationHandler(),  # When refactored
    # DiagnosisHandler(),     # Feature 3
    # RemediationHandler(),   # Feature 4
]


def get_registered_handlers() -> List[BaseAnalysisHandler]:
    """
    Get list of registered analysis handlers
    
    Returns:
        List of handler instances in priority order
    """
    return REGISTERED_HANDLERS
