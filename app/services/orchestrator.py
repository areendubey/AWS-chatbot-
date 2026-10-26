"""
Central chat orchestration service owned by Member 1 (Project Lead).
Coordinates:
Relevance Gate -> Registration Auth Check -> Structured Event Facts ->
Semantic Vector Retrieval -> Gemini Provider (with Fallback) -> Guardrail & Citation Validation.
"""
import uuid
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.schemas.chat import ChatRequest, ChatResponse, ChatStatus, SourceItem
from app.services.guardrails import guardrail_service
from app.services.event_service import EventService
from app.services.retrieval import retrieval_service
from app.providers.gemini import gemini_provider

logger = get_logger("services.orchestrator")


class OrchestratorService:
    @staticmethod
    def process_chat_message(
        request: ChatRequest,
        db: Session,
        request_id: str,
        user_identity: Optional[Dict[str, Any]] = None,
    ) -> ChatResponse:
        """
        Executes end-to-end RAG and factual lookup workflow.
        """
        conversation_id = request.conversation_id or str(uuid.uuid4())
        question = request.question.strip()

        # 1. Relevance / Safety Gate
        is_allowed, redirect_msg = guardrail_service.check_relevance(question)
        if not is_allowed:
            return ChatResponse(
                answer=redirect_msg,
                sources=[],
                conversation_id=conversation_id,
                request_id=request_id,
                status=ChatStatus.OUT_OF_SCOPE,
            )

        # 2. Registration Status Authorization Gate
        q_lower = question.lower()
        if "my registration" in q_lower or "registered" in q_lower or "ticket" in q_lower:
            if not user_identity:
                return ChatResponse(
                    answer="To view your registration status and ticket, please sign in with your verified Google account.",
                    sources=[],
                    conversation_id=conversation_id,
                    request_id=request_id,
                    status=ChatStatus.NEEDS_CLARIFICATION,
                )

            # Query authoritative DB for user's registration
            user_sub = user_identity.get("sub")
            # Try to find matched event
            matched_event = EventService.find_event_by_query(db, question)
            if matched_event:
                reg = EventService.get_user_registration(db, user_sub=user_sub, event_id=matched_event.event_id)
                if reg:
                    return ChatResponse(
                        answer=f"You are confirmed for '{matched_event.title}'! Your ticket code is {reg.ticket_code}. Venue: {matched_event.venue}, Starts at: {matched_event.start_at.strftime('%d %b %Y, %I:%M %p')}.",
                        sources=[SourceItem(title=matched_event.title, url=matched_event.source_url, event_id=matched_event.event_id)],
                        conversation_id=conversation_id,
                        request_id=request_id,
                        status=ChatStatus.ANSWERED,
                    )
                else:
                    return ChatResponse(
                        answer=f"You do not have an active registration for '{matched_event.title}'. Registration link: {matched_event.registration_url or 'Registration is currently closed.'}",
                        sources=[SourceItem(title=matched_event.title, url=matched_event.source_url, event_id=matched_event.event_id)],
                        conversation_id=conversation_id,
                        request_id=request_id,
                        status=ChatStatus.ANSWERED,
                    )

        # 3. Structured Event Lookup (Authoritative DB)
        structured_event = EventService.find_event_by_query(db, question)
        structured_facts_str = None
        if structured_event:
            structured_facts_str = (
                f"Event: {structured_event.title}\n"
                f"Status: {structured_event.status}\n"
                f"Starts: {structured_event.start_at.isoformat()}\n"
                f"Ends: {structured_event.end_at.isoformat()}\n"
                f"Venue: {structured_event.venue}\n"
                f"Registration URL: {structured_event.registration_url or 'None'}\n"
                f"Deadline: {structured_event.registration_deadline or 'None'}\n"
                f"Summary: {structured_event.summary}"
            )

        # 4. Semantic Vector Retrieval (Qdrant)
        retrieved_chunks = retrieval_service.search(question, top_k=3)

        # 5. LLM Answer Generation (Gemini with Fallback)
        llm_response = gemini_provider.generate_answer(
            question=question,
            context_chunks=retrieved_chunks,
            structured_event_facts=structured_facts_str,
        )

        # 6. Citation Validation
        allowed_urls = [c.source_url for c in retrieved_chunks if c.source_url]
        if structured_event and structured_event.source_url:
            allowed_urls.append(structured_event.source_url)
        validated_sources = guardrail_service.validate_citations(llm_response.sources, allowed_urls)

        # Map status string to ChatStatus enum safely
        final_status = ChatStatus.ANSWERED
        for s in ChatStatus:
            if s.value == llm_response.status:
                final_status = s
                break

        return ChatResponse(
            answer=llm_response.answer,
            sources=validated_sources,
            conversation_id=conversation_id,
            request_id=request_id,
            status=final_status,
        )


orchestrator_service = OrchestratorService()
