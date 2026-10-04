import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User, Dog
from ..schemas import UserRead, UserUpdate, DogCreate, DogUpdate, DogRead

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)):
    """Защищённый эндпоинт: вся защита — в одной строке Depends.
    Если функция вызвалась — current_user уже готовый объект из БД."""
    return current_user


@router.put("/me", response_model=UserRead)
def update_profile(
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновление данных профиля (email)."""
    if user_update.email is not None:
        existing = db.query(User).filter(User.email == user_update.email).first()
        if existing and existing.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email уже существует",
            )
        current_user.email = user_update.email
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/avatar", response_model=UserRead)
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Загрузка аватара пользователя."""
    # Проверка типа файла
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Допустимые форматы: JPEG, PNG, WebP",
        )

    # Проверка размера (5MB)
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Максимальный размер файла: 5MB",
        )

    # Генерация уникального имени файла
    ext = file.filename.split(".")[-1] if file.filename else "jpg"
    filename = f"{uuid.uuid4()}.{ext}"
    avatar_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "avatars")
    os.makedirs(avatar_path, exist_ok=True)

    # Сохранение файла
    with open(os.path.join(avatar_path, filename), "wb") as f:
        f.write(contents)

    # Удаление старого аватара
    if current_user.avatar:
        old_path = os.path.join(avatar_path, current_user.avatar)
        if os.path.exists(old_path):
            os.remove(old_path)

    current_user.avatar = filename
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/me/dogs", response_model=list[DogRead])
def get_my_dogs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить список собак текущего пользователя."""
    return db.query(Dog).filter(Dog.owner_id == current_user.id).order_by(Dog.created_at.desc()).all()


@router.post("/me/dogs", response_model=DogRead, status_code=status.HTTP_201_CREATED)
def add_dog(
    dog_data: DogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Добавить собаку в профиль."""
    dog = Dog(
        name=dog_data.name,
        breed=dog_data.breed,
        age=dog_data.age,
        owner_id=current_user.id,
    )
    db.add(dog)
    db.commit()
    db.refresh(dog)
    return dog


@router.put("/me/dogs/{dog_id}", response_model=DogRead)
def update_dog(
    dog_id: int,
    dog_data: DogUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить информацию о собаке."""
    dog = db.query(Dog).filter(Dog.id == dog_id, Dog.owner_id == current_user.id).first()
    if not dog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Собака не найдена или не принадлежит вам",
        )

    if dog_data.name is not None:
        dog.name = dog_data.name
    if dog_data.breed is not None:
        dog.breed = dog_data.breed
    if dog_data.age is not None:
        dog.age = dog_data.age

    db.commit()
    db.refresh(dog)
    return dog


@router.delete("/me/dogs/{dog_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dog(
    dog_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удалить собаку из профиля."""
    dog = db.query(Dog).filter(Dog.id == dog_id, Dog.owner_id == current_user.id).first()
    if not dog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Собака не найдена или не принадлежит вам",
        )
    db.delete(dog)
    db.commit()
