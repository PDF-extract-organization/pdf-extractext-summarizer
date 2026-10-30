"""Adaptador del puerto AIProvider para OpenRouter (API compatible con la de OpenAI)."""

import httpx

from app.application.interfaces.ai_provider import (
    AIProvider,
    AIProviderError,
    AIRateLimitError,
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
    ) -> AIResponse:
        if not self._api_key.strip():
            raise MissingAPIKeyError("OPENROUTER_API_KEY no está configurada.")

        try:
            async with self._client(self._timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=self._headers(),
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
        if response.is_error:
            raise AIProviderError(f"OpenRouter respondió {response.status_code}.")

        data = self._parse_json(response)
        return AIResponse(
            content=self._extract_content(data),
            model=model,
            tokens_used=(data.get("usage") or {}).get("total_tokens"),
        )

    async def health_check(self) -> bool:
        if not self._api_key.strip():
            return False
        try:
            async with self._client(HEALTH_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    f"{self._base_url}/models", headers=self._headers()
                )
        except httpx.HTTPError:
            return False
        return response.status_code == 200

    def _client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self._transport, timeout=timeout)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

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
    def _extract_content(data: dict) -> str:
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise AIProviderError("Formato de respuesta inesperado de OpenRouter.") from error

        if not isinstance(content, str):
            raise AIProviderError("OpenRouter no devolvió texto en la respuesta.")
        return content
