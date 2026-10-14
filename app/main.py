"""Точка входа FastAPI-приложения.

Поддерживаются оба способа запуска:
    uvicorn app.main:app --reload          # из корня проекта (рекомендуется)
    cd app && uvicorn main:app --reload    # из папки app
"""
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# --- Совместимость с запуском из папки app/ --------------------------------
# Команда `cd app && uvicorn main:app` импортирует main как модуль ВЕРХНЕГО
# уровня (__package__ пустое), и относительные импорты ниже падают с ошибкой
# "attempted relative import with no known parent package".
# Представляемся как app.main: кладём корень проекта в sys.path и задаём
# пакет — дальше всё работает так же, как при запуске из корня проекта.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "app"

from fastapi import Depends, FastAPI  # noqa: E402  (импорт после настройки пакета)
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from .config import settings  # noqa: E402
from .database import Base, engine  # noqa: E402
from .deps import require_admin_page_user, require_page_user  # noqa: E402
from .models import User  # noqa: E402
from .routers import admin, auth, course, public, users  # noqa: E402

logger = logging.getLogger("barbosych")
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Код до yield — один раз при старте, после yield — при остановке."""
    # Папка для загрузок должна существовать и быть доступной на запись.
    # Недоступный каталог НЕ роняет всё приложение: сайт, статьи, события и
    # личный кабинет работают, а загрузка аватара вернёт понятную 503
    # (см. routers/users.py). Так заведомо рабочая часть не блокируется
    # из-за прав на одну папку.
    for upload_dir in (
        settings.avatar_dir,
        settings.dog_photo_dir,
        settings.exercise_media_dir,
    ):
        try:
            upload_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning(
                "Каталог загрузок недоступен: %s (%s). Загрузка файлов будет "
                "отклоняться с HTTP 503 — укажите доступный на запись путь "
                "в переменной UPLOAD_DIR.",
                upload_dir,
                exc,
            )

    # Создаёт таблицы, которых ещё нет (существующие не трогает).
    # Для изменения уже существующих таблиц — migrate.py / Alembic.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Barbosych API", lifespan=lifespan)

# Раздаём статические файлы (frontend/) и пользовательские загрузки.
# Загрузки лежат ВНЕ frontend/ — так пользовательские файлы не смешиваются
# со статикой приложения и не попадают в git.
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
# check_dir=False: каталог создаётся в lifespan, чтобы приложение падало
# с понятным сообщением, а не на импорте модуля.
app.mount(
    "/uploads",
    StaticFiles(directory=settings.UPLOAD_DIR, check_dir=False),
    name="uploads",
)


@app.get("/", include_in_schema=False)
async def root():
    """Страница входа."""
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/dashboard", include_in_schema=False)
async def dashboard_page(current_user: User = Depends(require_page_user)):
    """Личный кабинет: HTML отдаётся только при валидной сессии.
    Неавторизованного браузер уводит на страницу входа (303)."""
    return FileResponse(FRONTEND_DIR / "dashboard.html")


@app.get("/admin", include_in_schema=False)
async def admin_page(current_user: User = Depends(require_admin_page_user)):
    """Админ-панель: только для администраторов."""
    return FileResponse(FRONTEND_DIR / "admin.html")


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(admin.router)
app.include_router(public.router)
app.include_router(course.router)
