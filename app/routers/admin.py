from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import require_admin
from ..loaders import COURSE_DETAIL_LOADS, EVENT_DETAIL_LOADS
from ..models import (
    Article,
    Course,
    CourseEnrollment,
    CourseSection,
    Event,
    EventRegistration,
    Exercise,
    User,
)
from ..schemas import (
    AdminCourseList,
    ArticleCreate,
    ArticleList,
    ArticleRead,
    ArticleUpdate,
    CourseCreate,
    CourseEnrollmentCreate,
    CourseEnrollmentRead,
    CourseList,
    CourseRead,
    CourseStudentRead,
    CourseUpdate,
    EventCreate,
    EventRead,
    EventUpdate,
    ExerciseCreate,
    ExerciseRead,
    ExerciseUpdate,
    SectionCreate,
    SectionRead,
    SectionUpdate,
)
from ..serializers import (
    article_list_item,
    course_detail_read,
    enrollment_read,
    event_read,
    participants_of,
    section_read,
)
from ..uploads import (
    EXERCISE_MEDIA_SIGNATURES,
    read_upload,
    remove_upload,
    write_upload,
)

# Общие с публичной частью агрегаты по курсу (число секций/пройденных) —
# считаем их одинаково в админке и в кабинете пользователя.
from .course import course_list_items

router = APIRouter(prefix="/admin", tags=["Admin"])


def _registration_counts(db: Session, event_ids: list[int]) -> dict[int, int]:
    """Сколько человек записалось на каждое событие — одним запросом, без N+1."""
    if not event_ids:
        return {}
    rows = (
        db.query(EventRegistration.event_id, func.count(EventRegistration.id))
        .filter(EventRegistration.event_id.in_(event_ids))
        .group_by(EventRegistration.event_id)
        .all()
    )
    return {event_id: count for event_id, count in rows}


def _registered_event_ids(db: Session, user_id: int, event_ids: list[int]) -> set[int]:
    """На какие из событий записан конкретный пользователь — тоже одним запросом."""
    if not event_ids:
        return set()
    rows = (
        db.query(EventRegistration.event_id)
        .filter(
            EventRegistration.user_id == user_id,
            EventRegistration.event_id.in_(event_ids),
        )
        .all()
    )
    return {event_id for (event_id,) in rows}


# ========================
# Статьи (только админ)
# ========================

@router.post("/articles", response_model=ArticleRead, status_code=status.HTTP_201_CREATED)
def create_article(
    data: ArticleCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Создание новой статьи. Только админ."""
    article = Article(
        title=data.title,
        content=data.content,
        excerpt=data.excerpt,
        author_id=admin.id,
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


@router.get("/articles", response_model=list[ArticleList])
def list_articles(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Список всех статей (без полного контента). Только админ."""
    articles = (
        db.query(Article).order_by(Article.created_at.desc()).offset(skip).limit(limit).all()
    )
    # тот же способ формирования excerpt, что и в публичном списке
    return [article_list_item(article) for article in articles]


@router.get("/articles/{article_id}", response_model=ArticleRead)
def get_article(
    article_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Получение одной статьи по ID. Только админ."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Статья не найдена")
    return article


@router.put("/articles/{article_id}", response_model=ArticleRead)
def update_article(
    article_id: int,
    data: ArticleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Обновление статьи. Только админ."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Статья не найдена")

    if data.title is not None:
        article.title = data.title
    if data.content is not None:
        article.content = data.content
    if data.excerpt is not None:
        article.excerpt = data.excerpt

    db.commit()
    db.refresh(article)
    return article


@router.delete("/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_article(
    article_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Удаление статьи. Только админ."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Статья не найдена")

    db.delete(article)
    db.commit()


# ========================
# События (только админ)
# ========================

@router.post("/events", response_model=EventRead, status_code=status.HTTP_201_CREATED)
def create_event(
    data: EventCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Создание нового события. Только админ.

    Дата приходит уже провалидированным datetime (см. schemas.IsoDateTime):
    кривой формат клиент получит как 422, а не как 500 из середины хендлера.
    """
    event = Event(
        title=data.title,
        description=data.description,
        date=data.date,
        location=data.location,
        max_participants=data.max_participants,
        author_id=admin.id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event_read(event, registered_count=0, is_registered=False)


@router.get("/events", response_model=list[EventRead])
def list_events(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Список всех событий. Только админ."""
    events = db.query(Event).order_by(Event.date.desc()).offset(skip).limit(limit).all()
    event_ids = [event.id for event in events]
    counts = _registration_counts(db, event_ids)
    mine = _registered_event_ids(db, admin.id, event_ids)
    return [
        event_read(
            event,
            registered_count=counts.get(event.id, 0),
            is_registered=event.id in mine,
        )
        for event in events
    ]


@router.get("/events/{event_id}", response_model=EventRead)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Получение одного события по ID (с участниками). Только админ."""
    event = (
        db.query(Event).options(*EVENT_DETAIL_LOADS).filter(Event.id == event_id).first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    return event_read(
        event,
        registered_count=len(event.registrations),
        is_registered=any(reg.user_id == admin.id for reg in event.registrations),
        participants=participants_of(event),
    )


@router.put("/events/{event_id}", response_model=EventRead)
def update_event(
    event_id: int,
    data: EventUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Обновление события. Только админ."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")

    if data.title is not None:
        event.title = data.title
    if data.description is not None:
        event.description = data.description
    if data.date is not None:
        event.date = data.date
    if data.location is not None:
        event.location = data.location
    if data.max_participants is not None:
        event.max_participants = data.max_participants

    db.commit()
    db.refresh(event)

    registered_count = (
        db.query(EventRegistration).filter(EventRegistration.event_id == event.id).count()
    )
    is_registered = bool(
        db.query(EventRegistration)
        .filter(
            EventRegistration.event_id == event.id,
            EventRegistration.user_id == admin.id,
        )
        .first()
    )
    return event_read(
        event, registered_count=registered_count, is_registered=is_registered
    )


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Удаление события. Только админ."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")

    db.delete(event)
    db.commit()


# ========================
# Курс дрессировки (только админ)
# ========================
# Курс → секции (1 секция = 1 прогулка) → упражнения (комплекс на прогулку).
# Порядок задаётся order_index; если админ его не задал — ставим в конец.


def _next_order_index(db: Session, model, parent_column, parent_id: int) -> int:
    """Следующий порядковый номер среди детей родителя (или 0, если детей нет)."""
    current_max = (
        db.query(func.max(model.order_index)).filter(parent_column == parent_id).scalar()
    )
    return 0 if current_max is None else current_max + 1


@router.post("/courses", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
def create_course(
    data: CourseCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Создание курса. Только админ."""
    course = Course(title=data.title, description=data.description, author_id=admin.id)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course_detail_read(course)


@router.get("/courses", response_model=list[AdminCourseList])
def list_courses(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Список курсов с числом секций и зачисленных. Только админ."""
    courses = db.query(Course).order_by(Course.id.desc()).offset(skip).limit(limit).all()
    return course_list_items(db, courses, admin.id, with_enrollment_counts=True)


@router.get("/courses/{course_id}", response_model=CourseRead)
def get_course(
    course_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Курс целиком (секции + упражнения). Только админ."""
    course = (
        db.query(Course).options(*COURSE_DETAIL_LOADS).filter(Course.id == course_id).first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")
    # В админке прогресс конкретного пользователя не нужен — отдаём пустым.
    return course_detail_read(course)


@router.put("/courses/{course_id}", response_model=CourseRead)
def update_course(
    course_id: int,
    data: CourseUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Обновление курса. Только админ."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    if data.title is not None:
        course.title = data.title
    if data.description is not None:
        course.description = data.description

    db.commit()
    db.refresh(course)
    return course_detail_read(course)


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Удаление курса вместе с секциями и упражнениями. Только админ."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    db.delete(course)  # cascade удалит секции, упражнения и отметки прогресса
    db.commit()


@router.post(
    "/courses/{course_id}/sections",
    response_model=SectionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_section(
    course_id: int,
    data: SectionCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Добавление секции (прогулки) в курс. Только админ."""
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    order_index = (
        data.order_index
        if data.order_index is not None
        else _next_order_index(db, CourseSection, CourseSection.course_id, course_id)
    )
    section = CourseSection(
        course_id=course_id,
        title=data.title,
        description=data.description,
        order_index=order_index,
    )
    db.add(section)
    db.commit()
    db.refresh(section)
    return section_read(section)


@router.put("/sections/{section_id}", response_model=SectionRead)
def update_section(
    section_id: int,
    data: SectionUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Обновление секции. Только админ."""
    section = db.query(CourseSection).filter(CourseSection.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Секция не найдена")

    if data.title is not None:
        section.title = data.title
    if data.description is not None:
        section.description = data.description
    if data.order_index is not None:
        section.order_index = data.order_index

    db.commit()
    db.refresh(section)
    return section_read(section)


@router.delete("/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_section(
    section_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Удаление секции вместе с упражнениями. Только админ."""
    section = db.query(CourseSection).filter(CourseSection.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Секция не найдена")

    db.delete(section)
    db.commit()


@router.post(
    "/sections/{section_id}/exercises",
    response_model=ExerciseRead,
    status_code=status.HTTP_201_CREATED,
)
def create_exercise(
    section_id: int,
    data: ExerciseCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Добавление упражнения в секцию. Только админ."""
    section = db.get(CourseSection, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Секция не найдена")

    order_index = (
        data.order_index
        if data.order_index is not None
        else _next_order_index(db, Exercise, Exercise.section_id, section_id)
    )
    exercise = Exercise(
        section_id=section_id,
        title=data.title,
        description=data.description,
        repetitions=data.repetitions,
        duration_minutes=data.duration_minutes,
        order_index=order_index,
    )
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return exercise


@router.put("/exercises/{exercise_id}", response_model=ExerciseRead)
def update_exercise(
    exercise_id: int,
    data: ExerciseUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Обновление упражнения. Только админ."""
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Упражнение не найдено")

    if data.title is not None:
        exercise.title = data.title
    if data.description is not None:
        exercise.description = data.description
    if data.repetitions is not None:
        exercise.repetitions = data.repetitions
    if data.duration_minutes is not None:
        exercise.duration_minutes = data.duration_minutes
    if data.order_index is not None:
        exercise.order_index = data.order_index

    db.commit()
    db.refresh(exercise)
    return exercise


@router.delete("/exercises/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exercise(
    exercise_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Удаление упражнения вместе с его медиа. Только админ."""
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Упражнение не найдено")

    # Сначала убираем файл, потом запись: если удаление файла не удалось,
    # упражнение остаётся с рабочим медиа, а не со ссылкой в никуда.
    remove_upload(exercise.media, settings.exercise_media_dir)
    db.delete(exercise)
    db.commit()


@router.post("/exercises/{exercise_id}/media", response_model=ExerciseRead)
async def upload_exercise_media(
    exercise_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Загрузить (или заменить) медиа упражнения: фото, GIF или видео.

    Правила те же, что у аватара и фото собаки: формат определяем по
    содержимому, имя файла генерирует сервер, старый файл удаляем только после
    успешной записи нового.
    """
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Упражнение не найдено")

    contents, extension, kind = await read_upload(
        file, settings.MAX_EXERCISE_MEDIA_BYTES, EXERCISE_MEDIA_SIGNATURES
    )
    filename = write_upload(contents, extension, settings.exercise_media_dir)

    remove_upload(exercise.media, settings.exercise_media_dir)

    exercise.media = filename
    exercise.media_type = kind
    db.commit()
    db.refresh(exercise)
    return exercise


@router.delete("/exercises/{exercise_id}/media", response_model=ExerciseRead)
def delete_exercise_media(
    exercise_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Убрать медиа упражнения: файл удаляется, поля обнуляются.

    Идемпотентно — повторный вызов у упражнения без медиа не ошибка.
    """
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Упражнение не найдено")

    remove_upload(exercise.media, settings.exercise_media_dir)
    exercise.media = None
    exercise.media_type = "image"
    db.commit()
    db.refresh(exercise)
    return exercise


# ========================
# Зачисление на курс (доступ пользователей)
# ========================
# По умолчанию курс пользователю недоступен. Админ «приглашает» на курс —
# создаётся строка course_enrollments, и только после этого пользователь
# видит курс в кабинете и может отмечать прогулки.


def _enrolled_user_ids(db: Session, course_id: int) -> set[int]:
    """Кто уже зачислен на курс — одним запросом."""
    rows = (
        db.query(CourseEnrollment.user_id)
        .filter(CourseEnrollment.course_id == course_id)
        .all()
    )
    return {user_id for (user_id,) in rows}


@router.get("/courses/{course_id}/enrollments", response_model=list[CourseStudentRead])
def list_course_students(
    course_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Кого можно пригласить: ВСЕ зарегистрированные пользователи, у каждого —
    флаг enrolled (зачислен ли уже на этот курс). Только админ."""
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    users = db.query(User).order_by(User.id.asc()).all()
    enrolled = _enrolled_user_ids(db, course_id)
    return [
        CourseStudentRead(
            user_id=user.id,
            email=user.email,
            avatar=user.avatar,
            role=user.role,
            enrolled=user.id in enrolled,
        )
        for user in users
    ]


@router.post(
    "/courses/{course_id}/enrollments",
    response_model=CourseEnrollmentRead,
    status_code=status.HTTP_201_CREATED,
)
def enroll_user_to_course(
    course_id: int,
    data: CourseEnrollmentCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Пригласить пользователя на курс (открыть доступ). Идемпотентно:
    повторное приглашение не ошибка, а возврат уже существующего зачисления."""
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")
    user = db.get(User, data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    existing = (
        db.query(CourseEnrollment)
        .filter(
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.user_id == user.id,
        )
        .first()
    )
    if existing:
        return enrollment_read(existing)

    enrollment = CourseEnrollment(course_id=course_id, user_id=user.id)
    db.add(enrollment)
    try:
        db.commit()
    except IntegrityError:
        # Уникальный индекс (user_id, course_id) — защита от двух параллельных
        # приглашений. Возвращаем уже созданное зачисление, а не ошибку.
        db.rollback()
        enrollment = (
            db.query(CourseEnrollment)
            .filter(
                CourseEnrollment.course_id == course_id,
                CourseEnrollment.user_id == user.id,
            )
            .first()
        )
        if enrollment:
            return enrollment_read(enrollment)
        raise
    db.refresh(enrollment)
    return enrollment_read(enrollment)


@router.delete(
    "/courses/{course_id}/enrollments/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unenroll_user_from_course(
    course_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Отозвать доступ пользователя к курсу.

    Прогресс пользователя НЕ удаляем: если его пригласят снова, пройденные
    прогулки сохранятся.
    """
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    (
        db.query(CourseEnrollment)
        .filter(
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.user_id == user_id,
        )
        .delete()
    )
    db.commit()
