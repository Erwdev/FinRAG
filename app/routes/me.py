from fastapi import APIRouter, Depends

from app.auth.deps import CurrentUser, get_current_owner
from app.domain.portfolio.schemas import MeOut

router = APIRouter()


@router.get("/me", response_model=MeOut)
async def me(user: CurrentUser = Depends(get_current_owner)) -> MeOut:
    # Tidak membuat pengguna. Pengguna hanya ada jika seed_user sudah dijalankan.
    return MeOut(id=user.id, email=user.email, role=user.role)
