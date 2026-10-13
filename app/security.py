from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings

# bcrypt физически не умеет работать с паролем длиннее 72 байт:
# старые версии молча обрезали, bcrypt>=5 бросает ValueError.
# Поэтому ограничение проверяется на входе (см. schemas.UserCreate),
# а здесь оно же используется как страховка.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    """Пароль → необратимый хеш для БД.

    bcrypt сам добавляет случайную соль: одинаковые пароли дают РАЗНЫЕ хеши.
    Хеш медленный (~100–300 мс) — для одного логина незаметно,
    а перебор паролей злоумышленником становится непосильным.
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Хеш нельзя расшифровать. Проверка = хешируем введённый пароль
    с солью из сохранённого хеша (bcrypt сам её достанет) и сравниваем."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        # Пароль длиннее 72 байт или битый хеш в БД — это не «свой» пароль,
        # а не повод отдавать 500 вместо 401.
        return False


def create_access_token(user_id: int) -> str:
    """Создаёт JWT: заголовок.полезная_нагрузка.подпись.

    Payload ПОДПИСАН, но НЕ зашифрован — любой может прочитать его на jwt.io.
    Подделать без SECRET_KEY — нельзя. Поэтому кладём только id пользователя.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),  # "subject" — чей токен (JWT требует строку)
        "exp": expire,        # момент протухания; jwt.decode сам отклонит просроченный
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Проверяет подпись и срок годности токена.

    Возвращает id пользователя или None, если токен невалиден/просрочен/битый.
    Единая точка расшифровки: и HTTP-запросы, и страницы используют её.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        return None
