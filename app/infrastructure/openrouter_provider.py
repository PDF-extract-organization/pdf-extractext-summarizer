"""Adaptador del puerto AIProvider para OpenRouter (API compatible con la de OpenAI)."""

import httpx

from app.application.interfaces.ai_provider import (
    AIAuthenticationError,
    AIOutOfTokensError,
    AIProvider,
    AIProviderError,
    AIRateLimitError,
    AIRequestRejectedError,
    AIResponse,
    AITimeoutError,
    MissingAPIKeyError,
)

HEALTH_TIMEOUT_SECONDS = 3.0


class OpenRouterAIProvider(AIProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._api_key = api_key
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        api_key: str | None = None,
    ) -> AIResponse:
        # La del usuario si llega; si no, la del servidor
        key = (api_key or "").strip() or self._api_key.strip()
        if not key:
            raise MissingAPIKeyError("No hay API key de OpenRouter.")

        try:
            async with self._client(self._timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=self._headers(key),
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                )
        except httpx.TimeoutException as error:
            raise AITimeoutError("OpenRouter tardó demasiado en responder.") from error
        except httpx.RequestError as error:
            raise AIProviderError(f"No se pudo contactar con OpenRouter: {error}") from error

        if response.status_code == 429:
            raise AIRateLimitError(response.headers.get("Retry-After"))
        # Nunca se incluye la clave en el mensaje: puede ser la del usuario
        if response.status_code == 401:
            raise AIAuthenticationError("OpenRouter rechazó la API key.")
        if response.status_code in (400, 404):
            raise AIRequestRejectedError(
                f"OpenRouter rechazó la petición: {self._error_message(response)}"
            )
        if response.is_error:
            raise AIProviderError(f"OpenRouter respondió {response.status_code}.")

        data = self._parse_json(response)
        choice = self._first_choice(data)
        truncated = choice.get("finish_reason") == "length"
        return AIResponse(
            content=self._extract_content(choice, truncated, max_tokens),
            model=model,
            tokens_used=(data.get("usage") or {}).get("total_tokens"),
            truncated=truncated,
        )

    async def health_check(self) -> bool:
        if not self._api_key.strip():
            return False
        try:
            async with self._client(HEALTH_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    f"{self._base_url}/models", headers=self._headers(self._api_key)
                )
        except httpx.HTTPError:
            return False
        return response.status_code == 200

    def _client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self._transport, timeout=timeout)

    @staticmethod
    def _headers(key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {key}"}

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            error = response.json()["error"]
            return str(error["message"] if isinstance(error, dict) else error)
        except (ValueError, KeyError, TypeError):
            return f"código {response.status_code}"

    @staticmethod
    def _parse_json(response: httpx.Response) -> dict:
        try:
            data = response.json()
        except ValueError as error:
            raise AIProviderError("OpenRouter devolvió una respuesta que no es JSON.") from error

        if not isinstance(data, dict):
            raise AIProviderError("Formato de respuesta inesperado de OpenRouter.")
        if "error" in data:
            error = data["error"]
            message = error.get("message", str(error)) if isinstance(error, dict) else str(error)
            raise AIProviderError(f"Error de OpenRouter: {message}")
        return data

    @staticmethod
    def _first_choice(data: dict) -> dict:
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError, TypeError) as error:
            raise AIProviderError("Formato de respuesta inesperado de OpenRouter.") from error
        if not isinstance(choice, dict):
            raise AIProviderError("Formato de respuesta inesperado de OpenRouter.")
        return choice

    @staticmethod
    def _extract_content(choice: dict, truncated: bool, max_tokens: int) -> str:
        try:
            content = choice["message"]["content"]
        except (KeyError, TypeError) as error:
            raise AIProviderError("Formato de respuesta inesperado de OpenRouter.") from error

        if isinstance(content, str):
            return content
        # Los modelos de razonamiento gastan del mismo límite pensando (#2)
        if truncated:
            raise AIOutOfTokensError(
                f"El modelo agotó los {max_tokens} tokens antes de escribir el resumen "
                "(suele gastarlos razonando). Sube el máximo de tokens o elige otro modelo."
            )
        raise AIProviderError("OpenRouter no devolvió texto en la respuesta.")
