import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import Dog, User
from ..schemas import DogCreate, DogRead, DogUpdate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])

# Разрешаем только эти форматы. Расширение НЕ берём из имени файла, которое
# присылает клиент: там может быть .html/.svg (исполняемый в браузере код)
# или "..." с обходом каталога. Формат определяем по содержимому файла.
_AVATAR_SIGNATURES = (
    ("jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ("png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    ("webp", lambda data: data.startswith(b"RIFF") and data[8:12] == b"WEBP"),
)
AVATAR_CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}


def _detect_avatar_extension(data: bytes) -> str | None:
    """Определяет формат картинки по «магическим» байтам содержимого."""
    for extension, matches in _AVATAR_SIGNATURES:
        if matches(data):
            return extension
    return None


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
    """Загрузка аватара пользователя.

    Что проверяем:
      * реальный формат по содержимому (не по доверчивому content_type);
      * размер — читаем не больше лимита + 1 байт, чтобы 5 ГБ не осели в RAM;
      * имя файла генерируем сами, поэтому обход каталога невозможен.
    """
    max_bytes = settings.MAX_AVATAR_BYTES
    contents = await file.read(max_bytes + 1)
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Максимальный размер файла: {max_bytes // (1024 * 1024)}MB",
        )

    extension = _detect_avatar_extension(contents)
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Допустимые форматы: JPEG, PNG, WebP",
        )

    # Имя целиком наше: uuid4 + безопасное расширение из белого списка.
    filename = f"{uuid.uuid4().hex}.{extension}"
    avatar_dir = settings.avatar_dir
    try:
        avatar_dir.mkdir(parents=True, exist_ok=True)
        (avatar_dir / filename).write_bytes(contents)
    except OSError:
        # Диск переполнен / нет прав на каталог / путь недоступен — отдаём
        # понятный 503, а не невнятный 500 из середины хендлера.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Хранилище для загрузок недоступно — проверьте путь UPLOAD_DIR",
        )

    # Удаляем предыдущий аватар (basename отсекает любые попытки выйти из папки)
    previous = current_user.avatar
    if previous:
        old_path = avatar_dir / previous.split("/")[-1].split("\\")[-1]
        if old_path.parent.resolve() == avatar_dir.resolve() and old_path.is_file():
            old_path.unlink(missing_ok=True)

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
    return (
        db.query(Dog)
        .filter(Dog.owner_id == current_user.id)
        .order_by(Dog.created_at.desc())
        .all()
    )


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
