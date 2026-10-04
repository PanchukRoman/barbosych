from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, computed_field


class UserCreate(BaseModel):
    """Тело POST /auth/register. Pydantic проверит данные ДО вызова эндпоинта:
    кривой email или короткий пароль → FastAPI сам вернёт 422 с описанием."""
    email: EmailStr
    password: str = Field(min_length=8)


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
    """Ответ на логин."""
    access_token: str
    token_type: str = "bearer"


class RoleUpdate(BaseModel):
    """Назначение роли пользователю (только админ)."""
    user_id: int
    role: str = Field(..., pattern="^(reader|admin)$")


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
    date: str  # ISO формат строки
    location: str = Field(default="", max_length=255)
    max_participants: int = Field(default=50, ge=1)


class EventUpdate(BaseModel):
    """Обновление события (только админ)."""
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, min_length=10)
    date: str | None = None  # ISO формат строки
    location: str | None = Field(default=None, max_length=255)
    max_participants: int | None = Field(default=None, ge=1)


class EventRead(BaseModel):
    """Публичное чтение события."""
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
    participants: list["ParticipantRead"] = []


class EventRegistrationRequest(BaseModel):
    """Запрос на запись на событие."""
    event_id: int


class EventRegistrationRead(BaseModel):
    """Чтение записи на событие."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    event_id: int
    registered_at: datetime


class DogReadSimple(BaseModel):
    """Минимальная информация о собаке."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    breed: str
    age: int


class ParticipantRead(BaseModel):
    """Информация об участнике события."""
    user_id: int
    email: str
    avatar: str | None
    dogs: list[DogReadSimple] = []
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
