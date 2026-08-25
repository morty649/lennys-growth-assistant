from fastapi import APIRouter

from app.client_auth import issue_client_token, login_profile
from app.schemas import ClientTokenView, ProfileLogin

router = APIRouter()


@router.post("/api/client", response_model=ClientTokenView)
def client_create() -> ClientTokenView:
    token, expires_at = issue_client_token()
    return ClientTokenView(token=token, expires_at=expires_at)


@router.post("/api/login", response_model=ClientTokenView)
def profile_login(payload: ProfileLogin) -> ClientTokenView:
    token, expires_at = login_profile(payload.username, payload.password)
    return ClientTokenView(token=token, expires_at=expires_at)
