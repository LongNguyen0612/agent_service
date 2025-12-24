"""
WebSocket Route

Handles real-time bidirectional communication with clients.
"""

import logging
from typing import Dict, Set
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from src.api.utils.jwt import verify_jwt

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections grouped by tenant"""

    def __init__(self):
        # tenant_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # websocket -> user_context mapping
        self.connection_contexts: Dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket, user_context: dict):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()

        tenant_id = user_context.get("tenant_id")
        if tenant_id:
            if tenant_id not in self.active_connections:
                self.active_connections[tenant_id] = set()
            self.active_connections[tenant_id].add(websocket)
            self.connection_contexts[websocket] = user_context

            logger.info(
                f"WebSocket connected - User: {user_context.get('user_id')}, "
                f"Tenant: {tenant_id}, "
                f"Total connections for tenant: {len(self.active_connections[tenant_id])}"
            )

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        context = self.connection_contexts.get(websocket)
        if context:
            tenant_id = context.get("tenant_id")
            if tenant_id and tenant_id in self.active_connections:
                self.active_connections[tenant_id].discard(websocket)
                if not self.active_connections[tenant_id]:
                    del self.active_connections[tenant_id]

            del self.connection_contexts[websocket]

            logger.info(
                f"WebSocket disconnected - User: {context.get('user_id')}, "
                f"Tenant: {tenant_id}"
            )

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to a specific WebSocket connection"""
        await websocket.send_json(message)

    async def broadcast_to_tenant(self, message: dict, tenant_id: str):
        """Broadcast message to all connections in a tenant"""
        if tenant_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[tenant_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending to connection: {e}")
                    disconnected.add(connection)

            # Clean up disconnected connections
            for connection in disconnected:
                self.disconnect(connection)


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/")
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    """
    WebSocket endpoint for real-time communication

    Query Parameters:
        token: JWT authentication token

    Message Format:
        {
            "event": "event_name",
            "data": { ... }
        }
    """
    logger.info(f"WebSocket endpoint called - token provided: {token is not None}")
    logger.info(f"Token value (first 50 chars): {token[:50] if token else 'None'}...")

    # Verify JWT token
    if not token:
        logger.warning("WebSocket connection rejected - No token provided")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="No token provided")
        return

    user_context = verify_jwt(token)
    if not user_context:
        logger.warning("WebSocket connection rejected - Invalid token")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return

    # Accept connection
    await manager.connect(websocket, user_context)

    try:
        # Send connection confirmation
        await manager.send_personal_message(
            {
                "event": "connection:established",
                "data": {
                    "user_id": user_context.get("user_id"),
                    "tenant_id": user_context.get("tenant_id"),
                    "role": user_context.get("role")
                }
            },
            websocket
        )

        # Listen for messages
        while True:
            data = await websocket.receive_json()

            event = data.get("event")
            payload = data.get("data", {})

            logger.info(f"WebSocket message received - Event: {event}, User: {user_context.get('user_id')}")

            # Handle different event types
            if event == "ping":
                await manager.send_personal_message(
                    {"event": "pong", "data": payload},
                    websocket
                )
            else:
                # Echo back for now (can be extended with specific handlers)
                await manager.send_personal_message(
                    {
                        "event": f"{event}:response",
                        "data": {"status": "received", "original": payload}
                    },
                    websocket
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected - User: {user_context.get('user_id')}")
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {type(e).__name__} - {str(e)}")
        manager.disconnect(websocket)


# Export manager for use in other parts of the application
__all__ = ["router", "manager"]
