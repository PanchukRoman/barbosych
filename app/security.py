from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings


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
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


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