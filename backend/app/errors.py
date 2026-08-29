from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message


def error_body(
    request: Request, code: str, message: str, details: object = None
) -> dict[str, object]:
    error = {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", "unknown"),
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if details is not None:
        error["details"] = details
    return {"error": error}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            content=error_body(request, exc.code, exc.message), status_code=exc.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            content=error_body(
                request, "DADOS_INVALIDOS", "Dados de entrada inválidos", exc.errors()
            ),
            status_code=422,
        )
