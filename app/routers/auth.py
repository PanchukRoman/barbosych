from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import require_admin
from ..models import User
from ..schemas import RoleUpdate, Token, UserCreate, UserRead
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Auth"])


def _set_auth_cookie(response: Response, token: str) -> None:
    """Кладёт JWT в HttpOnly-cookie.

    HttpOnly — JS не может прочитать токен из cookie;
    SameSite — cookie не уходит на сторонние сайты (защита от CSRF);
    Secure — только по HTTPS (включается через COOKIE_SECURE на проде).
    """
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Регистрация: к моменту вызова Pydantic уже проверил данные,
    get_db уже выдал сессию. Осталась только бизнес-логика."""
    # SELECT ... WHERE email = ... LIMIT 1
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким email уже существует",
        )

    user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),  # сырой пароль в БД не попадёт
    )
    db.add(user)      # объект в очередь на INSERT (запроса пока не было)
    try:
        db.commit()   # выполняем INSERT и фиксируем транзакцию
    except IntegrityError:
        # Между проверкой выше и INSERT другой запрос успел создать такого же
        # пользователя: уникальный индекс в БД — последняя линия обороны.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким email уже существует",
        )
    db.refresh(user)  # подтягиваем поля, сгенерированные БД: id и created_at
    return user       # FastAPI отдаст ответ по схеме UserRead — без пароля


@router.post("/login", response_model=Token)
def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Логин по стандарту OAuth2: тело — form-urlencoded (не JSON!),
    поле называется username — в него пользователь пишет свой email.
    Токен возвращается в теле (для API-клиентов) и в HttpOnly-cookie (для UI)."""
    user = db.query(User).filter(User.email == form_data.username).first()

    # Одна ошибка и на неверный email, и на неверный пароль — иначе злоумышленник
    # мог бы по разным ответам вычислять, какие email зарегистрированы
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user.id)
    _set_auth_cookie(response, token)
    return Token(access_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    """Выход: гасим cookie. Токен в теле клиент хранить не должен."""
    response.delete_cookie(key=settings.COOKIE_NAME, path="/")


@router.post("/users/{user_id}/role", response_model=UserRead)
def update_user_role(
    user_id: int,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Назначение/смена роли пользователю. Только админ.

    Пользователь берётся ТОЛЬКО из пути запроса: раньше в теле был свой user_id,
    который побеждал путь — роль можно было сменить не тому, кого указали в URL.
    """
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Нельзя оставить систему без администраторов
    if user.role == "admin" and data.role != "admin":
        admins_count = db.query(User).filter(User.role == "admin").count()
        if admins_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя снять роль с последнего администратора",
            )

    user.role = data.role
    db.commit()
    db.refresh(user)
    return user
