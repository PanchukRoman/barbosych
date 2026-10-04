from fastapi import APIRouter, Depends

from ..deps import get_current_user
from ..models import User
from ..schemas import UserRead

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)):
    """Защищённый эндпоинт: вся защита — в одной строке Depends.
    Если функция вызвалась — current_user уже готовый объект из БД."""
    return current_user