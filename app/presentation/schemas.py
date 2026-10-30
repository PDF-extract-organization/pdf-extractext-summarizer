from typing import Annotated

from pydantic import BaseModel, StringConstraints

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class SummarizeRequest(BaseModel):
    text: NonBlankText


class SummarizeResponse(BaseModel):
    summary: str
    model: str
    tokens_used: int | None


class HealthResponse(BaseModel):
    status: str
    service: str


class ParametersResponse(BaseModel):
    model: str
    max_tokens: int
    temperature: float
    max_prompt_chars: int
    # ok | unavailable (config no respondió: valores del .env) | not_configured (sin CONFIG_URL)
    config_status: str
