"""Общие помощники загрузки и хранения файлов.

Здесь собраны правила, единые для всех загрузок приложения: аватары
пользователей, фотографии собак и медиа к упражнениям курса. Раньше они жили
приватно в routers/users.py — при добавлении медиа к упражнениям вынести их
сюда дешевле, чем дублировать, а заодно правила безопасности (имя файла,
проверка формата) применяются ко всем загрузкам одинаково.

Ключевые правила:
* Расширение НЕ берётся из имени файла клиента. Там может быть «.html»/«.svg»
  (исполняемый в браузере код) или «../» с обходом каталога. Формат определяем
  по содержимому («магические» байты), имя файла целиком генерирует сервер.
* Размер проверяем чтением max_bytes + 1 байт: многогигабайтный файл не осядет
  в оперативной памяти целиком.
* При замене/удалении файла чистим старый, не выходя за пределы каталога.
"""
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

# (расширение, вид медиа, проверка сигнатуры по содержимому)
_JPEG = ("jpg", "image", lambda data: data.startswith(b"\xff\xd8\xff"))
_PNG = ("png", "image", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"))
_WEBP = (
    "webp",
    "image",
    lambda data: data.startswith(b"RIFF") and data[8:12] == b"WEBP",
)
_GIF = (
    "gif",
    "image",
    lambda data: data.startswith(b"GIF87a") or data.startswith(b"GIF89a"),
)
# MP4 определяем по «ftyp» на смещении 4; WebM (в т.ч. с кодеком VP8/VP9) —
# по сигнатуре EBML-заголовка.
_MP4 = ("mp4", "video", lambda data: len(data) >= 12 and data[4:8] == b"ftyp")
_WEBM = ("webm", "video", lambda data: data.startswith(b"\x1a\x45\xdf\xa3"))

# Аватары и фото собак — только статичные картинки (без GIF и видео).
STATIC_IMAGE_SIGNATURES = (_JPEG, _PNG, _WEBP)
# Медиа упражнения — картинки (включая анимированный GIF) и видео.
EXERCISE_MEDIA_SIGNATURES = (_JPEG, _PNG, _WEBP, _GIF, _MP4, _WEBM)

CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
    "mp4": "video/mp4",
    "webm": "video/webm",
}


def detect_media(data: bytes, signatures=STATIC_IMAGE_SIGNATURES) -> tuple[str, str] | None:
    """Определяет формат файла по содержимому: (расширение, вид) или None."""
    for extension, kind, matches in signatures:
        if matches(data):
            return extension, kind
    return None


async def read_upload(
    file: UploadFile,
    max_bytes: int,
    signatures=STATIC_IMAGE_SIGNATURES,
) -> tuple[bytes, str, str]:
    """Читает загруженный файл, проверяя размер и реальный формат.

    Возвращает (содержимое, расширение из белого списка, вид: image/video).
    """
    contents = await file.read(max_bytes + 1)
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Максимальный размер файла: {max_bytes // (1024 * 1024)}MB",
        )

    detected = detect_media(contents, signatures)
    if detected is None:
        allowed = ", ".join(dict.fromkeys(ext.upper() for ext, _, _ in signatures))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недопустимый формат файла. Разрешены: {allowed}",
        )
    extension, kind = detected
    return contents, extension, kind


def write_upload(contents: bytes, extension: str, directory: Path) -> str:
    """Сохраняет файл под сгенерированным именем и возвращает имя файла.

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


def remove_upload(filename: str | None, directory: Path) -> None:
    """Удаляет ранее сохранённый файл, если он есть и лежит внутри каталога.

    basename отсекает выход из папки, а сравнение каталогов — защита от
    случайного удаления файла по абсолютному пути из БД.
    """
    if not filename:
        return
    path = directory / filename.split("/")[-1].split("\\")[-1]
    if path.parent.resolve() == directory.resolve() and path.is_file():
        path.unlink(missing_ok=True)
