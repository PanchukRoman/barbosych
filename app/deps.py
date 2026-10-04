import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User

# OAuth2PasswordBearer: (1) рисует кнопку Authorize в /docs,
# (2) вытаскивает из заголовка "Authorization: Bearer <токен>" сам токен.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Сердце авторизации. Любой эндпоинт с параметром
    current_user: User = Depends(get_current_user) становится защищённым:
    без валидного токена выполнение до него не дойдёт (будет 401).

    Токен читается из двух источников (в порядке приоритета):
    1. Заголовок "Authorization: Bearer <token>" — стандартный способ
    2. Query parameter "?token=<token>" — для навигации по страницам,
       когда токен хранится в localStorage и не передаётся автоматически

    ВАЖНО: Query parameter менее безопасен — токен виден в URL и логах.
    Для продакшена используй только Authorization header или cookies.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учётные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1. Пытаемся получить токен из Authorization header (стандартный способ)
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]  # убираем префикс "Bearer "

    # 2. Если в заголовке нет — пробуем query parameter ?token=...
    #    Это нужно для навигации по страницам (dashboard, admin),
    #    когда токен хранится в localStorage и не передаётся автоматически
    if not token:
        token = request.query_params.get("token")

    # 3. Если токен всё ещё нет — возвращаем 401
    if not token:
        raise credentials_exception

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