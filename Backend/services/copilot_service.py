from __future__ import annotations

import os
import json
import logging
import httpx
import asyncio
from typing import Any, AsyncGenerator

from services.context_builder import ContextBuilder
from services.prompt_builder import PromptBuilder
from services.conversation_service import ConversationService

logger = logging.getLogger("services.copilot_service")

# Retry configuration for transient Groq API failures
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0  # seconds
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


async def _call_groq_with_retry(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> AsyncGenerator[str, None]:
    """
    Makes a streaming POST request to the Groq API with exponential backoff
    retries on transient errors (429, 5xx). Yields raw SSE lines.
    """
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code in _RETRYABLE_STATUS_CODES:
                        error_body = await response.aread()
                        raise httpx.HTTPStatusError(
                            f"Groq API transient error {response.status_code}: {error_body}",
                            request=response.request,
                            response=response,
                        )
                    if response.status_code != 200:
                        error_body = await response.aread()
                        # Non-retryable error — raise immediately
                        raise ValueError(
                            f"Groq API error {response.status_code}: {error_body}"
                        )
                    async for line in response.aiter_lines():
                        yield line
                    return  # Success — exit retry loop
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Groq API transient failure on attempt %d/%d, retrying in %.1fs: %s",
                    attempt + 1,
                    _MAX_RETRIES,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
            else:
                raise
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Groq API network error on attempt %d/%d, retrying in %.1fs: %s",
                    attempt + 1,
                    _MAX_RETRIES,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
            else:
                raise


class CopilotService:
    @staticmethod
    async def stream_chat(
        user_id: str,
        tenant_id: str,
        message: str,
        page: str,
        incident_id: str | None = None,
        supplier_id: str | None = None,
        route_id: str | None = None,
        workflow_id: str | None = None,
        filters: dict | None = None,
        selected_objects: list | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Gathers context, builds system prompts, writes user query to history,
        streams response from Groq, and records the assistant's final response.
        """
        # 1. Resolve or create active conversation
        conversation_id = ConversationService.get_or_create_active_conversation(user_id)

        # 2. Persist user message to DB immediately
        ConversationService.add_message(conversation_id, "user", message)

        # 3. Compile context and history
        context_data = await ContextBuilder.build_context(
            user_id=user_id,
            tenant_id=tenant_id,
            page=page,
            incident_id=incident_id,
            supplier_id=supplier_id,
            route_id=route_id,
            workflow_id=workflow_id,
            filters=filters,
            selected_objects=selected_objects,
        )

        history = ConversationService.get_conversation_messages(conversation_id)
        # Exclude the very last message we just saved to prevent duplication in build_prompt_payload
        history_for_prompt = history[:-1] if len(history) > 0 else []

        # 4. Construct prompts
        system_prompt, _, messages_payload = PromptBuilder.build_prompt_payload(
            context_data=context_data,
            history=history_for_prompt,
            user_message=message
        )

        # 5. Connect to Groq Chat Completion with stream: True
        api_key = (os.getenv("GROQ_API_KEY") or "").strip()
        if not api_key:
            error_msg = "Error: GROQ_API_KEY is not configured on the backend."
            yield f"data: {json.dumps({'token': error_msg})}\n\n"
            yield "data: [DONE]\n\n"
            return

        model = (os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile").strip()
        url = "https://api.groq.com/openai/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Build full messages including the system prompt
        full_messages = [{"role": "system", "content": system_prompt}] + messages_payload

        payload = {
            "model": model,
            "messages": full_messages,
            "temperature": 0.2,
            "max_tokens": 1200,
            "stream": True,
        }

        accumulated_response: list[str] = []
        done_sent = False

        try:
            async for line in _call_groq_with_retry(url, headers, payload):
                line = line.strip()
                if not line:
                    continue
                if line == "data: [DONE]":
                    break
                if line.startswith("data: "):
                    data_str = line[6:]
                    try:
                        chunk = json.loads(data_str)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                accumulated_response.append(content)
                                yield f"data: {json.dumps({'token': content})}\n\n"
                    except Exception:
                        pass

        except asyncio.CancelledError:
            logger.info("CopilotService: Chat stream was cancelled by client connection drop.")
            # Persist whatever was generated before the cancel
            if accumulated_response:
                partial_text = "".join(accumulated_response)
                ConversationService.add_message(
                    conversation_id, "assistant", partial_text + " [Generation Stopped]"
                )
            # Emit DONE before re-raising so any remaining client connection is cleanly closed
            done_sent = True
            yield "data: [DONE]\n\n"
            raise

        except Exception as exc:
            logger.exception("CopilotService: Exception during Groq stream: %s", exc)
            yield f"data: {json.dumps({'token': f'Internal Server Error: {str(exc)}'})}\n\n"

        finally:
            # 6. Persist full generated assistant response
            if accumulated_response:
                full_text = "".join(accumulated_response)
                ConversationService.add_message(conversation_id, "assistant", full_text)

            # Guard against double-emitting [DONE] (e.g. after CancelledError path above)
            if not done_sent:
                yield "data: [DONE]\n\n"
