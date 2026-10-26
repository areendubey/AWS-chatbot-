"""
Base abstract interface for LLM providers.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.schemas.chat import SourceItem


class LLMResponse:
    def __init__(
        self,
        answer: str,
        sources: List[SourceItem],
        status: str = "answered",
        raw_output: Optional[str] = None
    ):
        self.answer = answer
        self.sources = sources
        self.status = status
        self.raw_output = raw_output


class BaseLLMProvider(ABC):
    @abstractmethod
    def generate_answer(
        self,
        question: str,
        context_chunks: List[Any],
        structured_event_facts: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> LLMResponse:
        """Generates evidence-grounded response using strict system constraints."""
        pass
