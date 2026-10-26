"""
Safety guardrails, relevance gating, prompt injection defense, and citation validation.
"""
import re
from typing import List, Tuple, Optional
from app.schemas.chat import SourceItem

OFF_TOPIC_PATTERNS = [
    re.compile(r"(?i)\b(write\s+(a\s+)?(c\+\+|python|java|javascript|rust|go)\s+program|code|algorithm|leetcode)\b"),
    re.compile(r"(?i)\b(weather\s+in|who\s+won\s+the\s+match|capital\s+of|write\s+an\s+essay|solve\s+math)\b"),
]

PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?i)\b(ignore\s+(all\s+)?(previous|prior)\s+instructions|system\s+prompt|reveal\s+(api\s+)?key)\b"),
    re.compile(r"(?i)\b(you\s+are\s+now\s+in\s+developer\s+mode|jailbreak|disregard\s+rules)\b"),
]


class GuardrailService:
    @staticmethod
    def check_relevance(question: str) -> Tuple[bool, Optional[str]]:
        """
        Classifies clearly out-of-scope or malicious queries before expensive RAG processing.
        Returns (is_allowed, redirect_message).
        """
        # 1. Prompt injection / abuse check
        for pattern in PROMPT_INJECTION_PATTERNS:
            if pattern.search(question):
                return False, "I cannot fulfill this request. I am here to assist with AWS Cloud Club KIIT events and society inquiries."

        # 2. Obvious off-topic check
        for pattern in OFF_TOPIC_PATTERNS:
            if pattern.search(question):
                return False, "I am the AWS Cloud Club KIIT assistant. I can only assist with society events, workshops, registration, and club activities."

        return True, None

    @staticmethod
    def validate_citations(
        sources: List[SourceItem],
        retrieved_chunk_urls: List[str]
    ) -> List[SourceItem]:
        """
        Ensures model never returns fabricated URLs.
        Only URLs present in retrieved approved evidence are permitted.
        """
        valid_sources = []
        for src in sources:
            if not src.url or src.url in retrieved_chunk_urls:
                valid_sources.append(src)
        return valid_sources


guardrail_service = GuardrailService()
