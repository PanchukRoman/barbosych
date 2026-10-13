from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Корень проекта (папка, где лежат app/, frontend/, .env)
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Все настройки в одном объекте. Порядок приоритета при чтении:
    переменные окружения → файл .env → значения по умолчанию здесь.

    Если обязательного поля нет нигде — приложение упадёт ПРИ СТАРТЕ
    с понятной ошибкой, а не в случайном месте через час работы.
    """

    # Путь к .env — абсолютный (рядом с пакетом app/), иначе при запуске
    # не из корня проекта (например `cd app && uvicorn main:app`) файл
    # не находился и обязательные DATABASE_URL/SECRET_KEY «терялись».
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), extra="ignore")

    DATABASE_URL: str                    # обязательное — без него не запустится
    SECRET_KEY: str                      # обязательное
    ALGORITHM: str = "HS256"             # алгоритм подписи JWT
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # --- Сессия в cookie ---
    # JWT кладётся в HttpOnly-cookie: страницы и запросы авторизуются
    # автоматически, а токен не светится в URL, логах и истории браузера.
    COOKIE_NAME: str = "access_token"
    COOKIE_SECURE: bool = False          # на проде за HTTPS поставить True
    COOKIE_SAMESITE: str = "lax"

    # --- Загрузки пользователей ---
    # По умолчанию — папка вне frontend/, чтобы пользовательские файлы
    # не попадали в статику фронтенда и в git.
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    MAX_AVATAR_BYTES: int = 5 * 1024 * 1024   # 5 МБ

    @property
    def avatar_dir(self) -> Path:
        return Path(self.UPLOAD_DIR) / "avatars"


settings = Settings()  # единственный экземпляр, его импортируют все модули
