from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .error import ClientError, ServerError
from .utils.jwt import verify_jwt
import logging

logger = logging.getLogger(__name__)


async def handle_client_error(request: Request, exc: ClientError):
    error_dict = {"code": exc.base_error.code, "message": exc.base_error.message}
    logger.warning(f"Client error: {error_dict}")
    return JSONResponse(status_code=exc.status_code, content={"error": error_dict})


async def handle_server_error(request: Request, exc: ServerError):
    error_dict = {"code": exc.base_error.code, "message": "Internal server error"}
    logger.error(f"Server error: {exc.base_error.code}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"error": error_dict}
    )


def create_app(ApplicationConfig) -> FastAPI:
    app = FastAPI(title="API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ApplicationConfig.CORS_ORIGINS,
        allow_credentials=ApplicationConfig.CORS_ALLOW_CREDENTIALS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Import WebSocket manager
    from src.api.routes.websocket import manager

    # Register WebSocket endpoint directly on app (must be before HTTP routes)
    @app.websocket("/")
    async def websocket_endpoint(websocket: WebSocket, token: str = None):
        """WebSocket endpoint for real-time communication"""
        logger.info(f"[APP] WebSocket endpoint called - token provided: {token is not None}")

        if not token:
            logger.warning("[APP] WebSocket connection rejected - No token provided")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="No token")
            return

        user_context = verify_jwt(token)
        if not user_context:
            logger.warning("[APP] WebSocket connection rejected - Invalid token")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            return

        await manager.connect(websocket, user_context)

        try:
            await manager.send_personal_message(
                {
                    "event": "connection:established",
                    "data": {
                        "user_id": user_context.get("user_id"),
                        "tenant_id": user_context.get("tenant_id"),
                        "role": user_context.get("role"),
                    },
                },
                websocket,
            )

            while True:
                data = await websocket.receive_json()
                event = data.get("event")
                payload = data.get("data", {})

                logger.info(
                    f"WebSocket message - Event: {event}, User: {user_context.get('user_id')}"
                )

                if event == "ping":
                    await manager.send_personal_message(
                        {"event": "pong", "data": payload}, websocket
                    )
                else:
                    await manager.send_personal_message(
                        {
                            "event": f"{event}:response",
                            "data": {"status": "received", "original": payload},
                        },
                        websocket,
                    )

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected - User: {user_context.get('user_id')}")
            manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"WebSocket error: {type(e).__name__} - {str(e)}")
            manager.disconnect(websocket)

    from src.api.routes import (
        health_check,
        projects,
        tasks,
        pipeline,
        artifacts,
        exports,
        git_sync,
        observability,
    )

    app.include_router(health_check.router, tags=["Health"])
    app.include_router(projects.router, tags=["Projects"])
    app.include_router(tasks.router, tags=["Tasks"])
    app.include_router(pipeline.router, tags=["Pipeline"])
    app.include_router(artifacts.router, tags=["Artifacts"])
    app.include_router(exports.router, tags=["Exports"])
    app.include_router(git_sync.router, tags=["Git Sync"])
    app.include_router(observability.router, tags=["Observability"])

    app.add_exception_handler(ClientError, handle_client_error)
    app.add_exception_handler(ServerError, handle_server_error)

    return app
