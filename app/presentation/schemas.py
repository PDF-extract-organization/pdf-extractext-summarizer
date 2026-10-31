from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class SummarizeRequest(BaseModel):
    text: NonBlankText
    # Ajustes del usuario (página Ajustes). Si no llegan: Consul y luego el .env
    model: NonBlankText | None = None
    # repr=False: que la clave no salga si el objeto acaba en un log
    api_key: NonBlankText | None = Field(default=None, repr=False)
    # El tope (max_tokens_limit) lo aplica el caso de uso, con un 400 que lo explica
    max_tokens: int | None = Field(default=None, ge=1)


class SummarizeResponse(BaseModel):
    summary: str
    model: str
    tokens_used: int | None
    # El modelo paró por max_tokens: el resumen está incompleto
    truncated: bool


class HealthResponse(BaseModel):
    status: str
    service: str


class ParametersResponse(BaseModel):
    model: str
    max_tokens: int
    # Máximo que acepta max_tokens en la petición; la página Ajustes valida con él
    max_tokens_limit: int
    temperature: float
    max_prompt_chars: int
    # ok | unavailable (config no respondió: valores del .env) | not_configured (sin CONFIG_URL)
    config_status: str
