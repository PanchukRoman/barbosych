from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

from .security import MAX_PASSWORD_BYTES


def _to_aware_datetime(value):
    """Приводит входное значение к datetime с таймзоной.

    Принимает строку ISO-8601 (в том числе с суффиксом Z, который присылает
    браузер через new Date(...).toISOString()) либо datetime.
    Наивное время трактуем как UTC, чтобы результат не зависел от TZ сервера.
    Кривой формат остаётся ValueError → FastAPI вернёт понятный 422,
    а не 500 из середины хендлера.
    """
    if isinstance(value, str):
        text = value.strip()
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        value = datetime.fromisoformat(text)
    if isinstance(value, datetime) and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


IsoDateTime = Annotated[datetime, BeforeValidator(_to_aware_datetime)]
Role = Literal["reader", "admin"]


class UserCreate(BaseModel):
    """Тело POST /auth/register. Pydantic проверит данные ДО вызова эндпоинта:
    кривой email или короткий пароль → FastAPI сам вернёт 422 с описанием."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=MAX_PASSWORD_BYTES)

    @field_validator("password")
    @classmethod
    def _fit_bcrypt_limit(cls, value: str) -> str:
        # Лимит bcrypt — 72 БАЙТА, а не символа: кириллица в UTF-8 весит 2 байта.
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(
                f"Пароль слишком длинный: максимум {MAX_PASSWORD_BYTES} байт в UTF-8"
            )
        return value


class UserRead(BaseModel):
    """Схема ОТВЕТА — белый список полей, разрешённых наружу.
    hashed_password здесь НЕТ — он физически не сможет утечь в JSON."""

    model_config = ConfigDict(from_attributes=True)  # разрешает собирать схему из ORM-объекта

    id: int
    email: EmailStr
    role: str
    avatar: str | None
    created_at: datetime


class UserUpdate(BaseModel):
    """Обновление профиля пользователя."""

    email: EmailStr | None = None


class Token(BaseModel):
    """Ответ на логин. Токен также кладётся в HttpOnly-cookie."""

    access_token: str
    token_type: str = "bearer"


class RoleUpdate(BaseModel):
    """Назначение роли пользователю (только админ). Сам пользователь
    берётся из пути запроса, чтобы не было двух источников истины."""

    role: Role


# ========================
# Статьи
# ========================

class ArticleCreate(BaseModel):
    """Создание статьи (только админ)."""

    title: str = Field(min_length=3, max_length=255)
    content: str = Field(min_length=10)
    excerpt: str = Field(default="", max_length=500)


class ArticleUpdate(BaseModel):
    """Обновление статьи (только админ)."""

    title: str | None = Field(default=None, min_length=3, max_length=255)
    content: str | None = Field(default=None, min_length=10)
    excerpt: str | None = Field(default=None, max_length=500)


class ArticleRead(BaseModel):
    """Публичное чтение статьи."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    excerpt: str
    author_id: int
    created_at: datetime
    updated_at: datetime | None


class ArticleList(BaseModel):
    """Список статей (без полного контента)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    excerpt: str
    author_id: int
    created_at: datetime


# ========================
# События
# ========================

class EventCreate(BaseModel):
    """Создание события (только админ)."""

    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10)
    date: IsoDateTime
    location: str = Field(default="", max_length=255)
    max_participants: int = Field(default=50, ge=1)


class EventUpdate(BaseModel):
    """Обновление события (только админ)."""

    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, min_length=10)
    date: IsoDateTime | None = None
    location: str | None = Field(default=None, max_length=255)
    max_participants: int | None = Field(default=None, ge=1)


class EventRead(BaseModel):
    """Публичное чтение события. registered_count / is_registered считает
    сервер: клиент не должен догадываться о них по списку участников."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    date: datetime
    location: str
    max_participants: int
    created_at: datetime

    registered_count: int = 0
    is_registered: bool = False
    participants: list["ParticipantRead"] = Field(default_factory=list)


class EventRegistrationRead(BaseModel):
    """Чтение записи на событие."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    event_id: int
    registered_at: datetime


class MyEventRead(BaseModel):
    """Событие из списка «мои записи»."""

    registration_id: int
    event_id: int
    event_title: str
    event_date: datetime
    event_location: str
    registered_at: datetime


class DogReadSimple(BaseModel):
    """Минимальная информация о собаке (для карточки участника)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    breed: str
    age: int


class ParticipantRead(BaseModel):
    """Информация об участнике события."""

    user_id: int
    email: EmailStr
    avatar: str | None
    dogs: list[DogReadSimple] = Field(default_factory=list)
    registered_at: datetime


# ========================
# Собаки
# ========================

class DogCreate(BaseModel):
    """Добавление собаки в профиль."""

    name: str = Field(..., min_length=1, max_length=100)
    breed: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=0, le=30)


class DogUpdate(BaseModel):
    """Обновление информации о собаке."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    breed: str | None = Field(default=None, min_length=1, max_length=100)
    age: int | None = Field(default=None, ge=0, le=30)


class DogRead(BaseModel):
    """Чтение информации о собаке."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    breed: str
    age: int
    owner_id: int
    created_at: datetime


# ========================
# Курс дрессировки
# ========================
# Курс → секции (1 секция = 1 прогулка) → упражнения (комплекс на прогулку).
# Контент наполняет админ; пользователь отмечает пройденные секции.


class ExerciseCreate(BaseModel):
    """Создание упражнения в секции (только админ)."""

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    repetitions: str = Field(default="", max_length=100)
    duration_minutes: int = Field(default=0, ge=0, le=600)
    # Не задан — сервер поставит упражнение в конец секции.
    order_index: int | None = Field(default=None, ge=0)


class ExerciseUpdate(BaseModel):
    """Обновление упражнения (только админ)."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    repetitions: str | None = Field(default=None, max_length=100)
    duration_minutes: int | None = Field(default=None, ge=0, le=600)
    order_index: int | None = Field(default=None, ge=0)


class ExerciseRead(BaseModel):
    """Чтение упражнения."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    section_id: int
    order_index: int
    title: str
    description: str
    repetitions: str
    duration_minutes: int


class SectionCreate(BaseModel):
    """Создание секции курса = прогулки (только админ)."""

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    order_index: int | None = Field(default=None, ge=0)


class SectionUpdate(BaseModel):
    """Обновление секции (только админ)."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    order_index: int | None = Field(default=None, ge=0)


class SectionRead(BaseModel):
    """Чтение секции вместе с комплексом упражнений.

    completed проставляет сервер для конкретного пользователя (в админке
    остаётся False) — клиент не должен угадывать это по своим данным.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    order_index: int
    title: str
    description: str
    exercises: list[ExerciseRead] = Field(default_factory=list)
    completed: bool = False


class CourseCreate(BaseModel):
    """Создание курса (только админ)."""

    title: str = Field(min_length=3, max_length=255)
    description: str = Field(default="", max_length=2000)


class CourseUpdate(BaseModel):
    """Обновление курса (только админ)."""

    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class CourseList(BaseModel):
    """Карточка курса для списка: прогресс считает сервер."""

    id: int
    title: str
    description: str
    sections_count: int
    completed_count: int


class AdminCourseList(CourseList):
    """Карточка курса для админки: плюс число зачисленных пользователей."""

    enrolled_count: int = 0


class CourseRead(BaseModel):
    """Курс с секциями и упражнениями (детальный просмотр)."""

    id: int
    title: str
    description: str
    sections: list[SectionRead] = Field(default_factory=list)


class SectionProgressRead(BaseModel):
    """Отметка о пройденной секции."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    section_id: int
    completed_at: datetime


class CourseEnrollmentRead(BaseModel):
    """Зачисленный на курс пользователь (ответ админки)."""

    user_id: int
    email: EmailStr
    avatar: str | None = None
    enrolled_at: datetime


class CourseStudentRead(BaseModel):
    """Строка списка «кого пригласить»: все пользователи + признак зачисления."""

    user_id: int
    email: EmailStr
    avatar: str | None = None
    role: str
    enrolled: bool = False


class CourseEnrollmentCreate(BaseModel):
    """Тело POST /admin/courses/{id}/enrollments — кого зачислить на курс."""

    user_id: int = Field(ge=1)
