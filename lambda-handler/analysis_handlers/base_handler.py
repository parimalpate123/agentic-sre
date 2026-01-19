"""
Base Analysis Handler - Abstract base class for all analysis handlers

This provides a common interface for analysis handlers, allowing
chat_handler.py to use a registry pattern without knowing about
specific handler implementations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional


class BaseAnalysisHandler(ABC):
    """
    Abstract base class for analysis handlers
    
    Each handler implements:
    - detect_intent(): Check if this handler should handle the question
    - analyze(): Perform the analysis and return results
    - get_name(): Return handler name for logging
    - get_search_mode(): Return search mode identifier for UI
    """
    
    @abstractmethod
    def detect_intent(self, question: str) -> Tuple[bool, Optional[Any]]:
        """
        Detect if this handler should process the question
        
        Args:
            question: User's question text
        
        Returns:
            Tuple of (should_handle, extracted_data)
            - should_handle: True if this handler should process the question
            - extracted_data: Any data extracted from the question (e.g., correlation_id, service_name)
        """
        raise NotImplementedError
    
    @abstractmethod
    async def analyze(
        self,
        question: str,
        extracted_data: Any,
        service: Optional[str] = None,
        time_range: str = '1h',
        hours: int = 1,
        use_mcp: bool = True,
        search_mode: str = 'quick',
        **kwargs
    ) -> Dict[str, Any]:
        """
        Perform analysis and return results
        
        Args:
            question: User's question
            extracted_data: Data extracted by detect_intent()
            service: Optional service name
            time_range: Time range string (1h, 6h, etc.)
            hours: Parsed hours as integer
            use_mcp: Whether to use MCP client
            search_mode: Search mode ('quick' or 'deep')
            **kwargs: Additional context
        
        Returns:
            Dictionary with analysis results, including:
            - answer: Text response
            - pattern_data/correlation_data/etc: Handler-specific data
            - insights: List of insights
            - recommendations: List of recommendations
            - search_mode: Handler's search mode identifier
        """
        raise NotImplementedError
    
    @abstractmethod
    def get_name(self) -> str:
        """Return handler name for logging"""
        raise NotImplementedError
    
    @abstractmethod
    def get_search_mode(self) -> str:
        """Return search mode identifier for UI (e.g., 'patterns', 'correlation')"""
        raise NotImplementedError
