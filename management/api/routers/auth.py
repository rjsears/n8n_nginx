"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/routers/auth.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from api.database import get_db
from api.dependencies import (
    get_current_user,
    get_current_session,
    get_client_ip,
    rate_limit_login,
    verify_session_for_proxy,
)
from api.services.auth_service import AuthService
from api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    SessionInfo,
    SubnetCreate,
    SubnetResponse,
    UserInfo,
)
from api.schemas.common import SuccessResponse

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    response: Response,
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_login),
):
    """
    Authenticate user and create session.
    Returns session token for subsequent requests.
    Also sets a session cookie for nginx auth_request (used by iframes).
    """
    client_ip = await get_client_ip(request)
    user_agent = request.headers.get("User-Agent")

    auth_service = AuthService(db)

    # Check subnet restriction first
    if not await auth_service.is_ip_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied from this network",
        )

    user, session, error = await auth_service.authenticate(
        username=credentials.username,
        password=credentials.password,
        client_ip=client_ip,
        user_agent=user_agent,
    )

    if error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Set session cookie for nginx auth_request (used by iframes like File Browser)
    # httponly=False allows JavaScript to read it if needed, but it's also sent with requests
    # secure=True ensures it's only sent over HTTPS
    # samesite="lax" allows the cookie to be sent with same-site requests and top-level navigations
    response.set_cookie(
        key="session",
        value=session.token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=int((session.expires_at - session.created_at).total_seconds()),
        path="/",
    )

    return LoginResponse(
        token=session.token,
        expires_at=session.expires_at,
        user=UserInfo.model_validate(user),
    )


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    response: Response,
    session=Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    """Invalidate current session and clear session cookie."""
    auth_service = AuthService(db)
    await auth_service.logout(session.token)

    # Clear the session cookie
    response.delete_cookie(key="session", path="/")

    return SuccessResponse(message="Logged out successfully")


@router.get("/verify", status_code=status.HTTP_200_OK)
async def verify_session(
    _: bool = Depends(verify_session_for_proxy),
):
    """
    Verify session for nginx auth_request.
    Used for SSO proxy to Adminer and Dozzle.
    Returns 200 if valid, 401 if not.
    """
    return Response(status_code=status.HTTP_200_OK)


@router.get("/session", response_model=SessionInfo)
async def get_session_info(
    session=Depends(get_current_session),
):
    """Get current session information."""
    return SessionInfo.model_validate(session)


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(
    user=Depends(get_current_user),
):
    """Get current authenticated user."""
    return UserInfo.model_validate(user)


@router.put("/password", response_model=SuccessResponse)
async def change_password(
    password_change: PasswordChangeRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change current user's password."""
    auth_service = AuthService(db)

    success, error = await auth_service.change_password(
        user_id=user.id,
        current_password=password_change.current_password,
        new_password=password_change.new_password,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )

    return SuccessResponse(message="Password changed successfully")


@router.get("/sessions", response_model=List[SessionInfo])
async def list_sessions(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active sessions for current user."""
    auth_service = AuthService(db)
    sessions = await auth_service.get_user_sessions(user.id)
    return [SessionInfo.model_validate(s) for s in sessions]


@router.delete("/sessions", response_model=SuccessResponse)
async def logout_all_sessions(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout all sessions for current user."""
    auth_service = AuthService(db)
    count = await auth_service.logout_all(user.id)
    return SuccessResponse(message=f"Logged out {count} session(s)")


# Subnet management

@router.get("/subnets", response_model=List[SubnetResponse])
async def list_subnets(
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List allowed subnets."""
    auth_service = AuthService(db)
    subnets = await auth_service.get_allowed_subnets()
    return [SubnetResponse.model_validate(s) for s in subnets]


@router.post("/subnets", response_model=SubnetResponse, status_code=status.HTTP_201_CREATED)
async def add_subnet(
    subnet: SubnetCreate,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add an allowed subnet."""
    auth_service = AuthService(db)
    created = await auth_service.add_allowed_subnet(
        cidr=subnet.cidr,
        description=subnet.description,
        enabled=subnet.enabled,
    )
    return SubnetResponse.model_validate(created)


@router.delete("/subnets/{subnet_id}", response_model=SuccessResponse)
async def delete_subnet(
    subnet_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an allowed subnet."""
    auth_service = AuthService(db)
    deleted = await auth_service.delete_allowed_subnet(subnet_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subnet not found",
        )

    return SuccessResponse(message="Subnet deleted")
