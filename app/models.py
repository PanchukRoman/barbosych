from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
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
    # о пройденных прогулках и отдельных упражнениях.
    courses: Mapped[list["Course"]] = relationship(back_populates="author")
    section_progress: Mapped[list["SectionProgress"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    exercise_progress: Mapped[list["ExerciseProgress"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    # Зачисления на курсы: доступ пользователя к прохождению. Пока строки нет —
    # курса пользователь не видит, доступ открывает админ («пригласить»).
    course_enrollments: Mapped[list["CourseEnrollment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    # Уведомления о новом контенте (см. Notification). Удаляются вместе с
    # пользователем: чужая лента никому не нужна.
    notifications: Mapped[list["Notification"]] = relationship(
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
    # Имя файла фотографии собаки в каталоге settings.dog_photo_dir (uploads/dogs).
    # NULL — фото не загружено. URL собирает фронтенд: /uploads/dogs/<photo>.
    photo: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
    # Медиа-подсказка к упражнению (фото/GIF/видео). Хранится имя файла в
    # каталоге settings.exercise_media_dir (uploads/exercises); URL собирает
    # фронтенд: /uploads/exercises/<media>. media_type — «image» или «video»,
    # чтобы клиент знал, что рисовать: <img> или <video>.
    media: Mapped[str | None] = mapped_column(String(255), nullable=True)
    media_type: Mapped[str] = mapped_column(String(20), default="image")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    section: Mapped["CourseSection"] = relationship(back_populates="exercises")
    progress: Mapped[list["ExerciseProgress"]] = relationship(
        back_populates="exercise", cascade="all, delete-orphan"
    )


class SectionProgress(Base):
    """Запись о прогулке пользователя: с какой собакой, когда и с каким итогом.

    Строка появляется, когда пользователь начинает прогулку (выбрав собаку) или
    сразу отмечает её пройденной. completed_at заполнен — прогулка зачтена.
    Здесь же хранится дневник прогулки: заметка, оценка, погода и фактическое
    время (упражнения отмечаются отдельно, в ExerciseProgress).
    """

    __tablename__ = "section_progress"
    __table_args__ = (
        # Одну прогулку нельзя «пройти» дважды: без ограничения двойной клик
        # или два параллельных запроса создали бы дубли (как у записей на события).
        UniqueConstraint("user_id", "section_id", name="uq_section_progress_user_section"),
        # Оценка — целое от 1 до 5; ограничение на уровне БД не даёт записать
        # мусор в обход API.
        CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)",
            name="ck_section_progress_rating",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    section_id: Mapped[int] = mapped_column(
        ForeignKey("course_sections.id", ondelete="CASCADE")
    )
    # Какую собаку тренировали на прогулке. NULL — собаку не выбрали или удалили
    # (при удалении собаки внешний ключ обнуляется: ON DELETE SET NULL).
    dog_id: Mapped[int | None] = mapped_column(
        ForeignKey("dogs.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # NULL — прогулка начата, но не завершена (в зачёт курса не идёт).
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # --- Дневник прогулки ---
    note: Mapped[str] = mapped_column(Text, default="")
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weather: Mapped[str] = mapped_column(String(50), default="")
    actual_minutes: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="section_progress")
    section: Mapped["CourseSection"] = relationship(back_populates="progress")
    dog: Mapped["Dog | None"] = relationship()


class ExerciseProgress(Base):
    """Отметка «упражнение отработано».

    Прогресс курса считаем по упражнениям, а не только по прогулкам целиком:
    тогда видно, что пользователь выполнил 3 из 5 упражнений прогулки, а не
    «0 из 1 прогулки». actual_seconds хранит время работы по таймеру.
    """

    __tablename__ = "exercise_progress"
    __table_args__ = (
        # Одно упражнение отмечается один раз на пользователя.
        UniqueConstraint(
            "user_id", "exercise_id", name="uq_exercise_progress_user_exercise"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE")
    )
    # Фактически затраченное время (секунды), если упражнение запускали по
    # таймеру. 0 — таймер не использовали.
    actual_seconds: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="exercise_progress")
    exercise: Mapped["Exercise"] = relationship(back_populates="progress")


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


class Notification(Base):
    """Уведомление пользователю о новом контенте.

    Запись создаётся в момент публикации: админ добавил статью или событие,
    пользователя пригласили на курс, в курсе появилась новая прогулка или
    упражнение. Живёт до тех пор, пока пользователь не отметит ленту
    прочитанной или не очистит её.

    Почему на сервере, а не в localStorage, как было раньше: клиентская лента
    строилась сравнением текущих списков контента с прошлым визитом, поэтому
    результат зависел от браузера и от того, заходил ли человек в кабинет до
    публикации. Из-за этого у одного пользователя уведомление появлялось, а у
    другого его не было вовсе. Серверная лента одинакова для всех и переживает
    очистку хранилища браузера.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        # Лента всегда читается как «мои записи, новые сверху» — под это индекс.
        Index("ix_notifications_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # Вид записи задаёт иконку на клиенте: article, event, course, section,
    # exercise. Отдельный ENUM не нужен — набор видов расширяемый.
    type: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # NULL — ещё не прочитано. Отметка ставится, когда пользователь открыл ленту.
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="notifications")
