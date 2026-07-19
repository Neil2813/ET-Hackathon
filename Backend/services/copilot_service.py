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
            "Content-Type": "application/json"
        }

        # Build full messages including the system prompt
        full_messages = [{"role": "system", "content": system_prompt}] + messages_payload

        payload = {
            "model": model,
            "messages": full_messages,
            "temperature": 0.2,
            "max_tokens": 1200,
            "stream": True
        }

        accumulated_response = []
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        logger.error("Groq API returned error status %d: %s", response.status_code, error_body)
                        yield f"data: {json.dumps({'token': f'Error calling Groq API: status code {response.status_code}'})}\n\n"
                        yield "data: [DONE]\n\n"
                        return

                    async for line in response.aiter_lines():
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
            # Still persist whatever we have generated so far
            if accumulated_response:
                partial_text = "".join(accumulated_response)
                ConversationService.add_message(conversation_id, "assistant", partial_text + " [Generation Stopped]")
            raise
        except Exception as exc:
            logger.exception("CopilotService: Exception occurred during Groq stream processing: %s", exc)
            yield f"data: {json.dumps({'token': f'Internal Server Error: {str(exc)}'})}\n\n"
        finally:
            # 6. Save full generated assistant response
            if accumulated_response:
                full_text = "".join(accumulated_response)
                ConversationService.add_message(conversation_id, "assistant", full_text)
            
            # Send standard SSE DONE termination signal
            yield "data: [DONE]\n\n"
