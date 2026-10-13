"""Сборка ответов API из ORM-объектов.

Роуты отдают Pydantic-схемы, а не словари, собранные руками: так работают
валидация ответа, автодокументация и единый контракт для админки и публичной части.
"""
from .models import (
    Article,
    Course,
    CourseEnrollment,
    CourseSection,
    Event,
    EventRegistration,
)
from .schemas import (
    ArticleList,
    CourseEnrollmentRead,
    CourseRead,
    DogReadSimple,
    EventRead,
    ExerciseRead,
    ParticipantRead,
    SectionRead,
)

EXCERPT_LIMIT = 200


def make_excerpt(excerpt: str | None, content: str, limit: int = EXCERPT_LIMIT) -> str:
    """Авторский excerpt имеет приоритет; если он пуст — обрезаем контент.

    (Раньше из-за приоритета операторов for короткой статьи возвращался весь
    content, а заданный автором excerpt игнорировался.)
    """
    if excerpt:
        return excerpt
    if len(content) <= limit:
        return content
    return content[:limit].rstrip() + "..."


def article_list_item(article: Article) -> ArticleList:
    """Карточка статьи для списка: без полного контента."""
    return ArticleList(
        id=article.id,
        title=article.title,
        excerpt=make_excerpt(article.excerpt, article.content),
        author_id=article.author_id,
        created_at=article.created_at,
    )


def participant_read(registration: EventRegistration) -> ParticipantRead:
    """Участник события вместе со своими собаками.

    Требует, чтобы registration.user и user.dogs были подгружены заранее
    (selectinload/joinedload) — иначе получим N+1 запросов.
    """
    user = registration.user
    return ParticipantRead(
        user_id=user.id,
        email=user.email,
        avatar=user.avatar,
        dogs=[DogReadSimple.model_validate(dog) for dog in user.dogs],
        registered_at=registration.registered_at,
    )


def participants_of(event: Event) -> list[ParticipantRead]:
    """Все участники события. Требует заранее подгруженных связей."""
    return [participant_read(registration) for registration in event.registrations]


def event_read(
    event: Event,
    *,
    registered_count: int,
    is_registered: bool,
    participants: list[ParticipantRead] | None = None,
) -> EventRead:
    """Единая форма события для публичной части и админки."""
    return EventRead(
        id=event.id,
        title=event.title,
        description=event.description,
        date=event.date,
        location=event.location,
        max_participants=event.max_participants,
        created_at=event.created_at,
        registered_count=registered_count,
        is_registered=is_registered,
        participants=participants or [],
    )


def section_read(section: CourseSection, *, completed: bool = False) -> SectionRead:
    """Секция (прогулка) вместе с её комплексом упражнений.

    Требует заранее подгруженной section.exercises (COURSE_DETAIL_LOADS) —
    иначе получим запрос на каждую секцию.
    """
    return SectionRead(
        id=section.id,
        course_id=section.course_id,
        order_index=section.order_index,
        title=section.title,
        description=section.description,
        exercises=[ExerciseRead.model_validate(exercise) for exercise in section.exercises],
        completed=completed,
    )


def course_detail_read(course: Course, completed_section_ids: set[int]) -> CourseRead:
    """Курс с секциями и упражнениями; completed — для конкретного пользователя."""
    return CourseRead(
        id=course.id,
        title=course.title,
        description=course.description,
        sections=[
            section_read(section, completed=section.id in completed_section_ids)
            for section in course.sections
        ],
    )


def enrollment_read(enrollment: CourseEnrollment) -> CourseEnrollmentRead:
    """Зачисление вместе с данными пользователя.

    Требует подгруженного enrollment.user — иначе получим лишний запрос.
    """
    user = enrollment.user
    return CourseEnrollmentRead(
        user_id=user.id,
        email=user.email,
        avatar=user.avatar,
        enrolled_at=enrollment.created_at,
    )
