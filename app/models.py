from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# Про lazy-стратегии: раньше у всех связей стоял lazy="selectin" — это значило,
# что КАЖДАЯ загрузка пользователя (в т.ч. в get_current_user на каждый запрос)
# тянула его статьи, события, записи и собак четырьмя лишними запросами.
# Теперь по умолчанию ленивая загрузка, а нужные связи подгружаются явно
# (selectinload/joinedload) там, где они реально нужны — см. app/routers/public.py.


class User(Base):
    """Таблица users. Каждый атрибут = колонка."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="reader")
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Связи
    articles: Mapped[list["Article"]] = relationship(back_populates="author")
    events: Mapped[list["Event"]] = relationship(back_populates="author")
    event_registrations: Mapped[list["EventRegistration"]] = relationship(
        back_populates="user"
    )
    dogs: Mapped[list["Dog"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    # Курсы, которые создал пользователь (на практике — админ), и его отметки
    # о пройденных прогулках.
    courses: Mapped[list["Course"]] = relationship(back_populates="author")
    section_progress: Mapped[list["SectionProgress"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    # Зачисления на курсы: доступ пользователя к прохождению. Пока строки нет —
    # курса пользователь не видит, доступ открывает админ («пригласить»).
    course_enrollments: Mapped[list["CourseEnrollment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Article(Base):
    """Таблица статей. Пишет админ, видят все пользователи."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    excerpt: Mapped[str] = mapped_column(String(500), default="")
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    author: Mapped["User"] = relationship(back_populates="articles")


class Event(Base):
    """Таблица событий. Создаёт админ, пользователи записываются."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[str] = mapped_column(String(255), default="")
    max_participants: Mapped[int] = mapped_column(Integer, default=50)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    author: Mapped["User"] = relationship(back_populates="events")
    registrations: Mapped[list["EventRegistration"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventRegistration(Base):
    """Таблица записей на события."""

    __tablename__ = "event_registrations"
    __table_args__ = (
        # Один пользователь — одна запись на событие. Без этого ограничения
        # проверка «уже записан?» + INSERT не атомарны и два параллельных
        # запроса создавали дубли.
        UniqueConstraint("user_id", "event_id", name="uq_event_registration_user_event"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="event_registrations")
    event: Mapped["Event"] = relationship(back_populates="registrations")


class Dog(Base):
    """Таблица собак. У пользователя может быть много собак."""

    __tablename__ = "dogs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    breed: Mapped[str] = mapped_column(String(100))
    age: Mapped[int] = mapped_column(Integer)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    owner: Mapped["User"] = relationship(back_populates="dogs")


# ========================
# Курс дрессировки
# ========================
# Курс — контейнер верхнего уровня («некий курс дрессировки собаки»).
# Курс делится на секции; 1 секция = 1 прогулка с собакой. Внутри секции
# задан комплекс упражнений, которые пользователь отрабатывает на прогулке.
# Контентом (курс/секции/упражнения) наполняет админ, а пользователь отмечает
# пройденные прогулки — таблица SectionProgress.


class Course(Base):
    """Таблица курсов дрессировки."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    author: Mapped["User"] = relationship(back_populates="courses")
    # Порядок задаёт админ (order_index); id — стабильный второй ключ, иначе
    # при одинаковом order_index порядок секций в списке «плавал» бы.
    sections: Mapped[list["CourseSection"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="[CourseSection.order_index, CourseSection.id]",
    )
    # Кому открыт доступ к курсу. Пусто — курс не виден ни одному пользователю.
    enrollments: Mapped[list["CourseEnrollment"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )


class CourseSection(Base):
    """Секция курса = одна прогулка. Задаёт комплекс упражнений."""

    __tablename__ = "course_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    course: Mapped["Course"] = relationship(back_populates="sections")
    exercises: Mapped[list["Exercise"]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="[Exercise.order_index, Exercise.id]",
    )
    progress: Mapped[list["SectionProgress"]] = relationship(
        back_populates="section", cascade="all, delete-orphan"
    )


class Exercise(Base):
    """Упражнение внутри секции — элемент комплекса на прогулку."""

    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(
        ForeignKey("course_sections.id", ondelete="CASCADE")
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    # repetitions — текстом («3 подхода по 5 раз»): упражнения бывают разной
    # природы (повторы, выдержка, расстояние), одним числом не описать.
    repetitions: Mapped[str] = mapped_column(String(100), default="")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    section: Mapped["CourseSection"] = relationship(back_populates="exercises")


class SectionProgress(Base):
    """Отметка «пользователь прошёл секцию (прогулку)»."""

    __tablename__ = "section_progress"
    __table_args__ = (
        # Одну прогулку нельзя «пройти» дважды: без ограничения двойной клик
        # или два параллельных запроса создали бы дубли (как у записей на события).
        UniqueConstraint("user_id", "section_id", name="uq_section_progress_user_section"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    section_id: Mapped[int] = mapped_column(
        ForeignKey("course_sections.id", ondelete="CASCADE")
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="section_progress")
    section: Mapped["CourseSection"] = relationship(back_populates="progress")


class CourseEnrollment(Base):
    """Зачисление пользователя на курс — «пропуск» к прохождению.

    По умолчанию курсы пользователю недоступны: доступ открывает админ,
    приглашая пользователя на курс. Наличие строки здесь = доступ есть.
    """

    __tablename__ = "course_enrollments"
    __table_args__ = (
        # Одного пользователя нельзя зачислить на курс дважды.
        UniqueConstraint("user_id", "course_id", name="uq_course_enrollment_user_course"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="course_enrollments")
    course: Mapped["Course"] = relationship(back_populates="enrollments")
