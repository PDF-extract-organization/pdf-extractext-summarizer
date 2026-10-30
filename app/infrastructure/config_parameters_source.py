"""Adaptador del puerto ParametersSource que lee del servicio config (Consul por detrás).

No usa py-consul: config es el único servicio que habla con Consul.
"""

import logging

import httpx

from app.application.interfaces.parameters_source import ParametersSource

PREFIX = "summarizer/"

logger = logging.getLogger(__name__)


class ConfigServiceParametersSource(ParametersSource):
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def get_overrides(self) -> dict[str, str] | None:
        try:
            async with httpx.AsyncClient(
                transport=self._transport, timeout=self._timeout_seconds
            ) as client:
                response = await client.get(f"{self._base_url}/", params={"prefix": PREFIX})
            response.raise_for_status()
            entries = response.json()["entries"]
            return {e["key"].removeprefix(PREFIX): e["value"] for e in entries}
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            # Un fallo de config nunca rompe el resumen: se sigue con el .env
            logger.warning("El servicio config no respondió bien; se usa el .env: %r", error)
            return None
