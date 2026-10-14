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
    Exercise,
    ExerciseProgress,
    SectionProgress,
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


def exercise_read(exercise: Exercise, *, done_seconds: int | None = None) -> ExerciseRead:
    """Упражнение с медиа и отметкой «отработано» для конкретного пользователя.

    done_seconds=None — упражнение не отмечено; число (в т.ч. 0) — отмечено,
    а значение хранит фактическое время по таймеру.
    """
    return ExerciseRead(
        id=exercise.id,
        section_id=exercise.section_id,
        order_index=exercise.order_index,
        title=exercise.title,
        description=exercise.description,
        repetitions=exercise.repetitions,
        duration_minutes=exercise.duration_minutes,
        media=exercise.media,
        media_type=exercise.media_type or "image",
        completed=done_seconds is not None,
        actual_seconds=done_seconds or 0,
    )


def section_read(
    section: CourseSection,
    *,
    progress: SectionProgress | None = None,
    exercise_progress: dict[int, ExerciseProgress] | None = None,
    dog_name: str | None = None,
) -> SectionRead:
    """Секция (прогулка) вместе с упражнениями, дневником и прогрессом.

    Требует заранее подгруженной section.exercises (COURSE_DETAIL_LOADS) —
    иначе получим запрос на каждую секцию. exercise_progress — карта
    «id упражнения → отметка пользователя».
    """
    done = {
        exercise_id: item.actual_seconds
        for exercise_id, item in (exercise_progress or {}).items()
    }
    exercises = [
        exercise_read(exercise, done_seconds=done.get(exercise.id))
        for exercise in section.exercises
    ]
    total = len(exercises)
    completed_exercises = sum(1 for exercise in exercises if exercise.completed)
    completed = bool(progress and progress.completed_at)
    if total:
        percent = round(completed_exercises / total * 100)
    else:
        # Прогулка без упражнений: считаем выполненной, если её отметили.
        percent = 100 if completed else 0

    return SectionRead(
        id=section.id,
        course_id=section.course_id,
        order_index=section.order_index,
        title=section.title,
        description=section.description,
        exercises=exercises,
        completed=completed,
        completed_exercises=completed_exercises,
        total_exercises=total,
        percent=percent,
        dog_id=progress.dog_id if progress else None,
        dog_name=dog_name,
        started_at=progress.started_at if progress else None,
        completed_at=progress.completed_at if progress else None,
        note=progress.note if progress else "",
        rating=progress.rating if progress else None,
        weather=progress.weather if progress else "",
        actual_minutes=progress.actual_minutes if progress else 0,
    )


def course_detail_read(
    course: Course,
    *,
    section_progress: dict[int, SectionProgress] | None = None,
    exercise_progress: dict[int, ExerciseProgress] | None = None,
    dog_names: dict[int, str] | None = None,
) -> CourseRead:
    """Курс с секциями и упражнениями; прогресс — для конкретного пользователя."""
    progress_by_section = section_progress or {}
    dog_names = dog_names or {}
    return CourseRead(
        id=course.id,
        title=course.title,
        description=course.description,
        sections=[
            section_read(
                section,
                progress=progress_by_section.get(section.id),
                exercise_progress=exercise_progress,
                dog_name=(
                    dog_names.get(progress_by_section[section.id].dog_id)
                    if section.id in progress_by_section
                    and progress_by_section[section.id].dog_id is not None
                    else None
                ),
            )
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
