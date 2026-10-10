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
