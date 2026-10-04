from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import RoleUpdate, UserCreate, UserRead, Token
from ..security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Auth"])


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
    db.commit()       # выполняем INSERT и фиксируем транзакцию
    db.refresh(user)  # подтягиваем поля, сгенерированные БД: id и created_at
    return user       # FastAPI отдаст ответ по схеме UserRead — без пароля


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Логин по стандарту OAuth2: тело — form-urlencoded (не JSON!),
    поле называется username — в него пользователь пишет свой email."""
    user = db.query(User).filter(User.email == form_data.username).first()

    # Одна ошибка и на неверный email, и на неверный пароль — иначе злоумышленник
    # мог бы по разным ответам вычислять, какие email зарегистрированы
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Token(access_token=create_access_token(user.id))


@router.post("/make-admin")
def make_admin(email: str, db: Session = Depends(get_db)):
    """Делает пользователя администратором. Использовать один раз для первого админа."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.role = "admin"
    db.commit()
    return {"message": f"Пользователь {email} теперь администратор"}


@router.post("/users/{user_id}/role", response_model=UserRead)
def update_user_role(
    user_id: int,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Назначение/смена роли пользователю. Только админ."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администратор может менять роли",
        )
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.role = data.role
    db.commit()
    db.refresh(user)
    return user