from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User
from .security import decode_access_token

# OAuth2PasswordBearer делает две вещи:
#   1) рисует кнопку Authorize в /docs и описывает security-схему в OpenAPI;
#   2) вытаскивает токен из заголовка "Authorization: Bearer <токен>".
# auto_error=False — не падать сразу, а дать нам решить, что вернуть клиенту.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def extract_token(request: Request, bearer_token: str | None = Depends(oauth2_scheme)) -> str | None:
    """Ищет токен в двух источниках (в порядке приоритета):
    1. HttpOnly-cookie — так работают страницы и браузерный UI;
    2. заголовок "Authorization: Bearer ..." — для API-клиентов и /docs.

    ВАЖНО: вариант "?token=..." больше НЕ поддерживается. Он был удобен для
    навигации, но токен утекал в логи сервера, историю браузера и Referer.
    Теперь cookie браузер отправляет сам, и токен в URL не нужен.
    """
    return request.cookies.get(settings.COOKIE_NAME) or bearer_token


def get_current_user(
    db: Session = Depends(get_db),
    token: str | None = Depends(extract_token),
) -> User:
    """Сердце авторизации. Любой эндпоинт с параметром
    current_user: User = Depends(get_current_user) становится защищённым:
    без валидного токена выполнение до него не дойдёт (будет 401)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учётные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    # decode проверяет и подпись, и срок годности — любая проблема даёт None
    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_exception

    user = db.get(User, user_id)  # быстрый поиск по первичному ключу
    if user is None:
        # Токен валиден, но пользователя удалили из БД — пускать нельзя
        raise credentials_exception
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Зависимость для админских эндпоинтов: пускает только role == 'admin'."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ только для администраторов",
        )
    return current_user


def _page_redirect(location: str) -> HTTPException:
    """303 See Other — браузер уйдёт на location методом GET."""
    return HTTPException(
        status_code=status.HTTP_303_SEE_OTHER,
        detail="Требуется вход",
        headers={"Location": location},
    )


def require_page_user(
    db: Session = Depends(get_db),
    token: str | None = Depends(extract_token),
) -> User:
    """Для HTML-страниц: вместо JSON-401 отправляем браузер на страницу входа.
    Так закрыты /dashboard и /admin: HTML не отдаётся «просто так»."""
    if not token:
        raise _page_redirect("/")
    user_id = decode_access_token(token)
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise _page_redirect("/")
    return user


def require_admin_page_user(user: User = Depends(require_page_user)) -> User:
    """Для HTML-страницы админки: обычного пользователя уводим в личный кабинет."""
    if user.role != "admin":
        raise _page_redirect("/dashboard")
    return user
