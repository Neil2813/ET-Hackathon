from __future__ import annotations

import json
from pathlib import Path
from typing import Any

class PromptBuilder:
    @staticmethod
    def load_system_prompt() -> str:
        prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "system_prompt.md"
        try:
            return prompt_path.read_text(encoding="utf-8")
        except Exception:
            # Fallback if file is missing
            return (
                "You are the Praecantator AI Operations Copilot, an enterprise Energy Supply Chain Resilience analyst. "
                "You assist ONLY with energy security, supply chain resilience, logistics, geopolitical intelligence, "
                "routing, governance, operational analysis, supplier intelligence, and platform workflows. "
                "Reject unrelated questions. Refuse general knowledge queries."
            )

    @staticmethod
    def build_prompt_payload(
        context_data: dict[str, Any],
        history: list[dict[str, str]],
        user_message: str
    ) -> tuple[str, str, list[dict[str, str]]]:
        """
        Builds the system prompt (including context) and the messages list for the model.
        Returns:
            system_prompt_with_context: str
            user_message: str
            messages: list[dict[str, str]]
        """
        system_base = PromptBuilder.load_system_prompt()

        # Format context data cleanly as formatted JSON block
        context_formatted = json.dumps(context_data, indent=2)
        system_with_context = (
            f"{system_base}\n\n"
            f"=== ACTIVE APPLICATION CONTEXT ===\n"
            f"```json\n"
            f"{context_formatted}\n"
            f"```\n"
            f"==================================\n"
        )

        messages = []
        for msg in history:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })

        # The user's query is passed as the last message
        messages.append({
            "role": "user",
            "content": user_message
        })

        return system_with_context, user_message, messages
