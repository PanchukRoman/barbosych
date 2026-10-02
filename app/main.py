from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles

from .database import Base, engine
from .deps import get_current_user
from .models import User
from .routers import admin, auth, public, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Код до yield — один раз при старте, после yield — при остановке."""
    # Создаёт таблицы, которых ещё нет (существующие не трогает).
    # В продакшене вместо этого — миграции Alembic, до них дойдём.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="FastAPI Auth", lifespan=lifespan)

# Раздаём статические файлы (frontend/)
import os
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/static", StaticFiles(directory=frontend_path), name="static")


@app.get("/", include_in_schema=False)
async def root():
    """Перенаправляем корень на страницу входа."""
    from fastapi.responses import FileResponse
    return FileResponse(os.path.join(frontend_path, "index.html"))


@app.get("/dashboard", include_in_schema=False)
async def dashboard_page():
    """Личный кабинет — доступна только авторизованным."""
    from fastapi.responses import FileResponse
    return FileResponse(os.path.join(frontend_path, "dashboard.html"))


@app.get("/admin", include_in_schema=False)
async def admin_page(current_user: User = Depends(get_current_user)):
    """Админ-панель — доступна только администраторам."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ только для администраторов",
        )
    from fastapi.responses import FileResponse
    return FileResponse(os.path.join(frontend_path, "admin.html"))


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(admin.router)
app.include_router(public.router)