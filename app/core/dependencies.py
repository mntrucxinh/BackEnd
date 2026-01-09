"""FastAPI dependencies for authentication and authorization."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import JWT_SECRET, JWT_ALGORITHM
from app.models.tables import User
from jose import JWTError, jwt
from app.services import auth_service

security = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency để lấy current user từ JWT token.
    
    Args:
        credentials: HTTP Bearer token từ header
        db: Database session
        
    Returns:
        User object
        
    Raises:
        HTTPException: Nếu token không hợp lệ hoặc user không tồn tại
    """
    token = None
    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    if not token:
        token = request.cookies.get(auth_service.ACCESS_COOKIE_NAME)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "missing_token",
                "message": "Không tìm thấy access token.",
            },
        )
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_token",
                "message": f"Token không hợp lệ: {e}",
            },
        )
    
    # Check token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_token_type",
                "message": "Token không phải access token.",
            },
        )
    
    # Lấy user_id từ payload
    user_id = payload.get("uid")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_token",
                "message": "Thiếu uid trong token.",
            },
        )
    
    # Tìm user trong DB
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "User không tồn tại."},
        )
    
    return user

