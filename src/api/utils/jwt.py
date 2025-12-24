from typing import Optional
import logging

from jose import JWTError, jwt

from config import ApplicationConfig

logger = logging.getLogger(__name__)


def verify_jwt(token: str) -> Optional[dict]:
    """
    Verify and decode JWT token from IAM service

    Args:
        token: JWT token string

    Returns:
        Decoded payload dict with user_id, tenant_id, role or None if invalid
    """
    try:
        logger.info(f"Attempting to verify JWT token (first 20 chars): {token[:20]}...")
        payload = jwt.decode(
            token, ApplicationConfig.JWT_SECRET, algorithms=["HS256"]
        )
        logger.info(f"JWT verification successful for user_id: {payload.get('user_id')}")
        return payload
    except JWTError as e:
        logger.error(f"JWT verification failed: {type(e).__name__} - {str(e)}")
        logger.error(f"Token (first 50 chars): {token[:50]}...")
        logger.error(f"JWT_SECRET (first 10 chars): {ApplicationConfig.JWT_SECRET[:10]}...")
        return None
