import uuid
from pathlib import Path

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
_IMAGE_SIGNATURES = (
    ("jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ("png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    ("webp", lambda data: data.startswith(b"RIFF") and data[8:12] == b"WEBP"),
)
IMAGE_CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}


def _detect_image_extension(data: bytes) -> str | None:
    """Определяет формат картинки по «магическим» байтам содержимого."""
    for extension, matches in _IMAGE_SIGNATURES:
        if matches(data):
            return extension
    return None


async def _read_image(file: UploadFile, max_bytes: int) -> tuple[bytes, str]:
    """Читает загруженную картинку, проверяя размер и реальный формат.

    Размер проверяем чтением max_bytes + 1 байт: файл в 5 ГБ не осядет в RAM.
    """
    contents = await file.read(max_bytes + 1)
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Максимальный размер файла: {max_bytes // (1024 * 1024)}MB",
        )

    extension = _detect_image_extension(contents)
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Допустимые форматы: JPEG, PNG, WebP",
        )
    return contents, extension


def _write_image(contents: bytes, extension: str, directory: Path) -> str:
    """Сохраняет картинку под сгенерированным именем и возвращает имя файла.

    Имя целиком наше (uuid4 + безопасное расширение из белого списка), поэтому
    обход каталога через имя файла клиента невозможен.
    """
    filename = f"{uuid.uuid4().hex}.{extension}"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / filename).write_bytes(contents)
    except OSError:
        # Диск переполнен / нет прав на каталог / путь недоступен — отдаём
        # понятный 503, а не невнятный 500 из середины хендлера.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Хранилище для загрузок недоступно — проверьте путь UPLOAD_DIR",
        )
    return filename


def _remove_image(filename: str | None, directory: Path) -> None:
    """Удаляет ранее сохранённый файл, если он есть и лежит внутри каталога.

    basename отсекает выход из папки, а сравнение каталогов — защита от
    случайного удаления файла по абсолютному пути из БД.
    """
    if not filename:
        return
    path = directory / filename.split("/")[-1].split("\\")[-1]
    if path.parent.resolve() == directory.resolve() and path.is_file():
        path.unlink(missing_ok=True)


def _get_own_dog(db: Session, current_user: User, dog_id: int) -> Dog:
    """Собака текущего пользователя или 404 — чужая собака «не существует»."""
    dog = (
        db.query(Dog)
        .filter(Dog.id == dog_id, Dog.owner_id == current_user.id)
        .first()
    )
    if not dog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Собака не найдена или не принадлежит вам",
        )
    return dog


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
    contents, extension = await _read_image(file, settings.MAX_AVATAR_BYTES)
    filename = _write_image(contents, extension, settings.avatar_dir)

    # Удаляем предыдущий аватар после успешной записи нового: если запись
    # упала, старый файл остаётся на месте и профиль не «ломается».
    _remove_image(current_user.avatar, settings.avatar_dir)

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
    dog = _get_own_dog(db, current_user, dog_id)

    if dog_data.name is not None:
        dog.name = dog_data.name
    if dog_data.breed is not None:
        dog.breed = dog_data.breed
    if dog_data.age is not None:
        dog.age = dog_data.age

    db.commit()
    db.refresh(dog)
    return dog


@router.post("/me/dogs/{dog_id}/photo", response_model=DogRead)
async def upload_dog_photo(
    dog_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Загрузить (или заменить) фотографию собаки.

    Проверки те же, что и для аватара: реальный формат по содержимому файла и
    лимит размера. Собака обязана принадлежать текущему пользователю, иначе 404.
    """
    dog = _get_own_dog(db, current_user, dog_id)

    contents, extension = await _read_image(file, settings.MAX_DOG_PHOTO_BYTES)
    filename = _write_image(contents, extension, settings.dog_photo_dir)

    # Старое фото удаляем только после успешной записи нового.
    _remove_image(dog.photo, settings.dog_photo_dir)

    dog.photo = filename
    db.commit()
    db.refresh(dog)
    return dog


@router.delete("/me/dogs/{dog_id}/photo", response_model=DogRead)
def delete_dog_photo(
    dog_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Убрать фотографию собаки: файл удаляется, поле photo обнуляется.

    Идемпотентно — повторный вызов на собаке без фото не ошибка.
    """
    dog = _get_own_dog(db, current_user, dog_id)

    _remove_image(dog.photo, settings.dog_photo_dir)
    dog.photo = None
    db.commit()
    db.refresh(dog)
    return dog


@router.delete("/me/dogs/{dog_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dog(
    dog_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удалить собаку из профиля вместе с её фотографией."""
    dog = _get_own_dog(db, current_user, dog_id)

    _remove_image(dog.photo, settings.dog_photo_dir)
    db.delete(dog)
    db.commit()
