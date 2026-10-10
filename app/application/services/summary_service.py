"""Caso de uso: resumir un texto con el proveedor de IA."""

import re
from dataclasses import dataclass

from app.application.interfaces.ai_provider import AIProvider
from app.application.prompts import SYSTEM_PROMPT, build_user_prompt

# Algunos modelos devuelven su razonamiento delimitado; no forma parte del resumen
REASONING_BLOCK = re.compile(r"<(think|reasoning)>.*?</\1>", re.DOTALL | re.IGNORECASE)


@dataclass
class SummaryResult:
    summary: str
    model: str
    tokens_used: int | None


class SummaryService:
    def __init__(self, provider: AIProvider, max_prompt_chars: int):
        self._provider = provider
        self._max_prompt_chars = max_prompt_chars

    async def summarize(self, text: str) -> SummaryResult:
        user_prompt = build_user_prompt(text[: self._max_prompt_chars])
        response = await self._provider.complete(SYSTEM_PROMPT, user_prompt)

        return SummaryResult(
            summary=REASONING_BLOCK.sub("", response.content).strip(),
            model=response.model,
            tokens_used=response.tokens_used,
        )

    async def check_health(self) -> bool:
        return await self._provider.health_check()
