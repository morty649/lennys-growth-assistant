from fastapi import APIRouter

from app.client_auth import issue_client_token
from app.schemas import ClientTokenView

router = APIRouter()


@router.post("/api/client", response_model=ClientTokenView)
def client_create() -> ClientTokenView:
    token, expires_at = issue_client_token()
    return ClientTokenView(token=token, expires_at=expires_at)
