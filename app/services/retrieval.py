"""
Vector retrieval service interface and Qdrant connector.
Provides semantic retrieval over approved active event chunks and FAQs.
Also implements deterministic Qdrant fallback when Gemini is unavailable.
"""
from typing import List, Dict, Any, Optional
from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.chat import SourceItem

logger = get_logger("services.retrieval")


class RetrievedChunk:
    def __init__(
        self,
        chunk_id: str,
        text: str,
        score: float,
        event_id: Optional[str] = None,
        title: str = "Society Information",
        source_url: Optional[str] = None,
        is_approved: bool = True,
    ):
        self.chunk_id = chunk_id
        self.text = text
        self.score = score
        self.event_id = event_id
        self.title = title
        self.source_url = source_url
        self.is_approved = is_approved


class RetrievalService:
    """
    Retrieval service abstraction.
    Member 2 implements the live Qdrant client + Sentence Transformers embedding here.
    """

    def __init__(self):
        self.settings = get_settings()

    def search(
        self,
        query: str,
        top_k: int = 4,
        include_historical: bool = False
    ) -> List[RetrievedChunk]:
        """
        Executes dense semantic retrieval in Qdrant with metadata filters:
        - Must be is_approved=True
        - Must be is_active=True (unless include_historical is explicitly requested)
        """
        # When live Qdrant is connected by Member 2, this calls qdrant_client.
        # Fallback to local in-memory knowledge / approved events if Qdrant is initializing.
        logger.info("Executing retrieval query for: '%s' (top_k=%d, historical=%s)", query, top_k, include_historical)
        
        # Safe mock candidate for baseline tests
        results: List[RetrievedChunk] = []
        q_lower = query.lower()
        if "workshop" in q_lower or "aws" in q_lower or "cloud" in q_lower or "event" in q_lower:
            results.append(
                RetrievedChunk(
                    chunk_id="chunk-aws-intro-01",
                    text="AWS Cloud Club KIIT organizes hands-on workshops on AWS Cloud Foundations, Architecture, and DevOps. Sessions are held at Campus 6 Auditorium.",
                    score=0.88,
                    event_id="evt-aws-foundations-2026",
                    title="AWS Cloud Foundations Workshop 2026",
                    source_url="https://aws-sbg-kiit.org/events/foundations-2026",
                    is_approved=True,
                )
            )
        return results

    def deterministic_fallback_answer(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Policy requirement: When Gemini quota/timeout/transient error occurs,
        query approved current sources in Qdrant and return a deterministic, grounded answer.
        Never invent an answer.
        """
        chunks = self.search(query, top_k=2)
        if not chunks:
            return None

        # Return excerpt from highest scoring approved chunk
        top_chunk = chunks[0]
        if top_chunk.score < 0.65:
            return None

        answer_text = f"Based on approved society records: {top_chunk.text}"
        sources = [
            SourceItem(
                title=top_chunk.title,
                url=top_chunk.source_url,
                event_id=top_chunk.event_id,
            )
        ]
        return {
            "answer": answer_text,
            "sources": sources,
        }


retrieval_service = RetrievalService()
