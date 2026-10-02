import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User

# OAuth2PasswordBearer: (1) рисует кнопку Authorize в /docs,
# (2) вытаскивает из заголовка "Authorization: Bearer <токен>" сам токен.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),  # FastAPI сначала получит токен
    db: Session = Depends(get_db),        # ...и сессию БД
) -> User:
    """Сердце авторизации. Любой эндпоинт с параметром
    current_user: User = Depends(get_current_user) становится защищённым:
    без валидного токена выполнение до него не дойдёт (будет 401).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учётные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # decode проверяет и подпись, и срок годности — любая проблема = исключение
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload.get("sub"))
    except (jwt.PyJWTError, TypeError, ValueError):
        raise credentials_exception

    user = db.get(User, user_id)  # быстрый поиск по первичному ключу
    if user is None:
        # Токен валиден, но пользователя удалили из БД — пускать нельзя
        raise credentials_exception
    return user