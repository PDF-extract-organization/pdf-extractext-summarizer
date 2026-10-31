from fastapi import APIRouter, Depends, HTTPException

from app.application.errors import InvalidAPIKeyError, TokensOverLimitError
from app.application.interfaces.ai_provider import (
    AIProviderError,
    AIRateLimitError,
    AIRequestRejectedError,
    AITimeoutError,
    MissingAPIKeyError,
)
from app.application.services.summary_service import SummaryService
from app.dependencies import get_summary_service
from app.presentation.schemas import (
    HealthResponse,
    ParametersResponse,
    SummarizeRequest,
    SummarizeResponse,
)

# Único sitio donde se explica cómo configurar la clave
MISSING_API_KEY_DETAIL = (
    "Falta la API key de OpenRouter. Añádela en la página Ajustes de la web, o en el .env "
    "del servicio summarizer como OPENROUTER_API_KEY=... Crea una gratis en "
    "https://openrouter.ai/keys"
)

router = APIRouter()


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize(
    request: SummarizeRequest,
    service: SummaryService = Depends(get_summary_service),
):
    try:
        return await service.summarize(
            request.text,
            model=request.model,
            api_key=request.api_key,
            max_tokens=request.max_tokens,
        )
    except TokensOverLimitError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except InvalidAPIKeyError as error:
        raise HTTPException(status_code=401, detail=str(error))
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
    # Antes que AIProviderError, que es su clase base
    except AIRequestRejectedError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except AIProviderError as error:
        raise HTTPException(status_code=502, detail=f"El proveedor de IA falló: {error}")


@router.get("/health", response_model=HealthResponse)
async def health(service: SummaryService = Depends(get_summary_service)):
    status = "healthy" if await service.check_health() else "degraded"
    return HealthResponse(status=status, service="summarizer")


@router.get("/parameters", response_model=ParametersResponse)
async def parameters(service: SummaryService = Depends(get_summary_service)):
    """Los parámetros que usaría ahora un resumen sin ajustes del usuario. Sin la API key."""
    current = await service.current_parameters()
    params = current.parameters
    return ParametersResponse(
        model=params.model,
        max_tokens=params.max_tokens,
        max_tokens_limit=service.max_tokens_limit,
        temperature=params.temperature,
        max_prompt_chars=params.max_prompt_chars,
        config_status=current.config_status.value,
    )
