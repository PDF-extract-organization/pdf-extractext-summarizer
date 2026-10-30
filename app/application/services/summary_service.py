"""Caso de uso: resumir un texto con el proveedor de IA."""

import re
from dataclasses import dataclass
from enum import Enum

from app.application.interfaces.ai_provider import AIProvider
from app.application.interfaces.parameters_source import ParametersSource
from app.application.parameters import SummaryParameters, apply_overrides
from app.application.prompts import SYSTEM_PROMPT, build_user_prompt

# Algunos modelos devuelven su razonamiento delimitado; no forma parte del resumen
REASONING_BLOCK = re.compile(r"<(think|reasoning)>.*?</\1>", re.DOTALL | re.IGNORECASE)


@dataclass
class SummaryResult:
    summary: str
    model: str
    tokens_used: int | None


class ConfigStatus(str, Enum):
    OK = "ok"
    UNAVAILABLE = "unavailable"  # la fuente no respondió: se usa el .env
    NOT_CONFIGURED = "not_configured"  # sin fuente: solo el .env


@dataclass(frozen=True)
class CurrentParameters:
    parameters: SummaryParameters
    config_status: ConfigStatus


class SummaryService:
    def __init__(
        self,
        provider: AIProvider,
        defaults: SummaryParameters,
        source: ParametersSource | None = None,
    ):
        self._provider = provider
        self._defaults = defaults
        self._source = source

    async def summarize(self, text: str) -> SummaryResult:
        # Se leen en cada resumen: un cambio en la configuración vale sin reiniciar
        params = (await self.current_parameters()).parameters
        user_prompt = build_user_prompt(text[: params.max_prompt_chars])
        response = await self._provider.complete(
            SYSTEM_PROMPT,
            user_prompt,
            model=params.model,
            max_tokens=params.max_tokens,
            temperature=params.temperature,
        )

        return SummaryResult(
            summary=REASONING_BLOCK.sub("", response.content).strip(),
            model=response.model,
            tokens_used=response.tokens_used,
        )

    async def current_parameters(self) -> CurrentParameters:
        """Los parámetros que se usarían ahora: la configuración centralizada sobre el .env."""
        if self._source is None:
            return CurrentParameters(self._defaults, ConfigStatus.NOT_CONFIGURED)

        overrides = await self._source.get_overrides()
        if overrides is None:
            return CurrentParameters(self._defaults, ConfigStatus.UNAVAILABLE)
        return CurrentParameters(apply_overrides(self._defaults, overrides), ConfigStatus.OK)

    async def check_health(self) -> bool:
        return await self._provider.health_check()
