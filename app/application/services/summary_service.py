"""Caso de uso: resumir un texto con el proveedor de IA."""

import re
from dataclasses import dataclass, replace
from enum import Enum

from app.application.errors import InvalidAPIKeyError, TokensOverLimitError
from app.application.interfaces.ai_provider import (
    AIAuthenticationError,
    AIProvider,
    AIProviderError,
)
from app.application.interfaces.parameters_source import ParametersSource
from app.application.parameters import SummaryParameters, apply_overrides
from app.application.prompts import SYSTEM_PROMPT, build_user_prompt

# Algunos modelos devuelven su razonamiento delimitado; no forma parte del resumen
REASONING_BLOCK = re.compile(r"<(think|reasoning)>.*?</\1>", re.DOTALL | re.IGNORECASE)

DEFAULT_MAX_TOKENS_LIMIT = 8000


@dataclass
class SummaryResult:
    summary: str
    model: str
    tokens_used: int | None
    truncated: bool


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
        max_tokens_limit: int = DEFAULT_MAX_TOKENS_LIMIT,
    ):
        self._provider = provider
        self._defaults = defaults
        self._source = source
        self.max_tokens_limit = max_tokens_limit

    async def summarize(
        self,
        text: str,
        model: str | None = None,
        api_key: str | None = None,
        max_tokens: int | None = None,
    ) -> SummaryResult:
        """`model`, `api_key` y `max_tokens` son los ajustes del usuario: ganan a Consul y
        al .env solo para esta petición."""
        # El tope protege la cuota de la clave del servidor de lo que pida cualquiera.
        # No se aplica a Consul ni al .env: esos los pone el administrador.
        if max_tokens is not None and max_tokens > self.max_tokens_limit:
            raise TokensOverLimitError(self.max_tokens_limit)

        # Se leen en cada resumen: un cambio en la configuración vale sin reiniciar
        params = (await self.current_parameters()).parameters
        params = replace(
            params,
            model=model or params.model,
            max_tokens=max_tokens or params.max_tokens,
        )
        user_prompt = build_user_prompt(text[: params.max_prompt_chars])
        try:
            response = await self._provider.complete(
                SYSTEM_PROMPT,
                user_prompt,
                model=params.model,
                max_tokens=params.max_tokens,
                temperature=params.temperature,
                api_key=api_key,
            )
        except AIAuthenticationError as error:
            # Si la clave era del usuario, es su error; si era la del servidor, de configuración
            if api_key:
                raise InvalidAPIKeyError("La API key no es válida.") from error
            raise AIProviderError(
                "OpenRouter rechazó la API key del servidor (OPENROUTER_API_KEY)."
            ) from error

        return SummaryResult(
            summary=REASONING_BLOCK.sub("", response.content).strip(),
            model=response.model,
            tokens_used=response.tokens_used,
            truncated=response.truncated,
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
