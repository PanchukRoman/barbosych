from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Все настройки в одном объекте. Порядок приоритета при чтении:
    переменные окружения → файл .env → значения по умолчанию здесь.

    Если обязательного поля нет нигде — приложение упадёт ПРИ СТАРТЕ
    с понятной ошибкой, а не в случайном месте через час работы.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str                    # обязательное — без него не запустится
    SECRET_KEY: str                      # обязательное
    ALGORITHM: str = "HS256"             # алгоритм подписи JWT
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30


settings = Settings()  # единственный экземпляр, его импортируют все модули