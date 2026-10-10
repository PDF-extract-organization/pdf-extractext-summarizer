from fastapi import APIRouter, Depends, HTTPException

from app.application.interfaces.ai_provider import (
    AIProviderError,
    AIRateLimitError,
    AITimeoutError,
    MissingAPIKeyError,
)
from app.application.services.summary_service import SummaryService
from app.dependencies import get_summary_service
from app.presentation.schemas import HealthResponse, SummarizeRequest, SummarizeResponse

# Único sitio donde se explica cómo configurar la clave
MISSING_API_KEY_DETAIL = (
    "Falta la OPENROUTER_API_KEY del servicio summarizer. Crea una gratis en "
    "https://openrouter.ai/keys y añádela al .env como OPENROUTER_API_KEY=..."
)

router = APIRouter()


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize(
    request: SummarizeRequest,
    service: SummaryService = Depends(get_summary_service),
):
    try:
        return await service.summarize(request.text)
    except MissingAPIKeyError:
        raise HTTPException(status_code=503, detail=MISSING_API_KEY_DETAIL)
    except AIRateLimitError as error:
        headers = {"Retry-After": error.retry_after} if error.retry_after else None
        raise HTTPException(
            status_code=429,
            detail="El proveedor de IA ha alcanzado su límite de peticiones. Inténtalo más tarde.",
            headers=headers,
        )
    except AITimeoutError:
        raise HTTPException(status_code=504, detail="El modelo tardó demasiado en responder.")
    except AIProviderError as error:
        raise HTTPException(status_code=502, detail=f"El proveedor de IA falló: {error}")


@router.get("/health", response_model=HealthResponse)
async def health(service: SummaryService = Depends(get_summary_service)):
    status = "healthy" if await service.check_health() else "degraded"
    return HealthResponse(status=status, service="summarizer")
