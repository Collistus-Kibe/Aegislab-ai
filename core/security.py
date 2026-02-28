"""
AegisLab AI — Firebase Authentication & Security
Initializes Firebase Admin SDK and provides a FastAPI dependency
for verifying Bearer tokens on protected endpoints.
"""

import logging

import firebase_admin
from firebase_admin import auth, credentials
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shared.config import settings

logger = logging.getLogger(__name__)

# ── Firebase Initialization ─────────────────────────────────────────────────
# Guard against duplicate initialization during hot-reloads in development.

if not firebase_admin._apps:
    cred = credentials.Certificate(settings.FIREBASE_CRED_PATH)
    firebase_admin.initialize_app(cred)
    logger.info("Firebase Admin SDK initialized from: %s", settings.FIREBASE_CRED_PATH)
else:
    logger.info("Firebase Admin SDK already initialized — skipping.")

# ── Auth Dependency ─────────────────────────────────────────────────────────

security = HTTPBearer()


async def verify_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    FastAPI dependency that extracts and verifies a Firebase ID token
    from the ``Authorization: Bearer <token>`` header.

    Returns
    -------
    str
        The Firebase ``uid`` of the authenticated user.

    Raises
    ------
    HTTPException (401)
        If the token is invalid, expired, or missing.
    """
    token = credentials.credentials

    try:
        decoded_token = auth.verify_id_token(token, check_revoked=False, clock_skew_seconds=5)
        uid: str = decoded_token["uid"]
        logger.debug("Authenticated user: %s", uid)
        return uid

    except auth.InvalidIdTokenError as exc:
        logger.warning("Invalid Firebase ID token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except auth.ExpiredIdTokenError as exc:
        logger.warning("Expired Firebase ID token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired. Please sign out and sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except ValueError as exc:
        logger.warning("Malformed token value: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Malformed authentication token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except Exception as exc:
        logger.error("Token verification failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )
