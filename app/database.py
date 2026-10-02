from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import settings

# Engine — держит ПУЛ соединений с Postgres и переиспользует их,
# чтобы не открывать новое соединение на каждый запрос.
engine = create_engine(
    settings.DATABASE_URL,
    # Перед выдачей соединения из пула — контрольный "SELECT 1".
    # Мёртвое соединение молча заменяется живым.
    pool_pre_ping=True,
)

# Фабрика сессий. Сессия — «рабочий блокнот» одной транзакции.
# Не потокобезопасна, поэтому на каждый HTTP-запрос создаётся своя.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,         # изменения летят в БД только по явному commit()
    expire_on_commit=False,  # после commit() объекты остаются читаемыми
)


class Base(DeclarativeBase):
    """Родитель всех моделей. По реестру наследников SQLAlchemy
    строит CREATE TABLE при старте приложения."""
    pass


def get_db():
    """Зависимость: сессия БД на время одного HTTP-запроса.
    Код до yield — до эндпоинта, после yield — после него (даже при ошибке)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()