"""Курс дрессировки: прохождение пользователем.

Наполнение курса (создание секций/упражнений, медиа) живёт в admin.py, а
здесь — то, что видит и делает обычный пользователь: список курсов, детальный
просмотр, отметки упражнений, выбор собаки, дневник прогулки и статистика.
"""
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..loaders import COURSE_DETAIL_LOADS
from ..models import (
    Course,
    CourseEnrollment,
    CourseSection,
    Dog,
    Exercise,
    ExerciseProgress,
    SectionProgress,
    User,
)
from ..schemas import (
    AdminCourseList,
    CourseList,
    CourseRead,
    CourseStatsRead,
    ExerciseComplete,
    ExerciseProgressRead,
    SectionDiaryUpdate,
    SectionProgressRead,
)
from ..serializers import course_detail_read

router = APIRouter(tags=["Course"])


# ========================
# Вспомогательные запросы (одним запросом вместо N+1)
# ========================


def sections_count_by_course(db: Session, course_ids: list[int]) -> dict[int, int]:
    """Сколько секций в каждом курсе — одним запросом, без N+1."""
    if not course_ids:
        return {}
    rows = (
        db.query(CourseSection.course_id, func.count(CourseSection.id))
        .filter(CourseSection.course_id.in_(course_ids))
        .group_by(CourseSection.course_id)
        .all()
    )
    return {course_id: count for course_id, count in rows}


def exercises_count_by_course(db: Session, course_ids: list[int]) -> dict[int, int]:
    """Сколько всего упражнений в каждом курсе — одним запросом."""
    if not course_ids:
        return {}
    rows = (
        db.query(CourseSection.course_id, func.count(Exercise.id))
        .join(Exercise, Exercise.section_id == CourseSection.id)
        .filter(CourseSection.course_id.in_(course_ids))
        .group_by(CourseSection.course_id)
        .all()
    )
    return {course_id: count for course_id, count in rows}


def completed_count_by_course(
    db: Session, user_id: int, course_ids: list[int]
) -> dict[int, int]:
    """Сколько секций каждого курса зачтено пользователю (completed_at задан)."""
    if not course_ids:
        return {}
    rows = (
        db.query(CourseSection.course_id, func.count(SectionProgress.id))
        .join(SectionProgress, SectionProgress.section_id == CourseSection.id)
        .filter(
            CourseSection.course_id.in_(course_ids),
            SectionProgress.user_id == user_id,
            SectionProgress.completed_at.isnot(None),
        )
        .group_by(CourseSection.course_id)
        .all()
    )
    return {course_id: count for course_id, count in rows}


def completed_exercise_counts_by_course(
    db: Session, user_id: int, course_ids: list[int]
) -> dict[int, int]:
    """Сколько упражнений каждого курса выполнено пользователем."""
    if not course_ids:
        return {}
    rows = (
        db.query(CourseSection.course_id, func.count(ExerciseProgress.id))
        .join(Exercise, Exercise.section_id == CourseSection.id)
        .join(ExerciseProgress, ExerciseProgress.exercise_id == Exercise.id)
        .filter(
            CourseSection.course_id.in_(course_ids),
            ExerciseProgress.user_id == user_id,
        )
        .group_by(CourseSection.course_id)
        .all()
    )
    return {course_id: count for course_id, count in rows}


def enrolled_count_by_course(db: Session, course_ids: list[int]) -> dict[int, int]:
    """Сколько пользователей зачислено на каждый курс — одним запросом."""
    if not course_ids:
        return {}
    rows = (
        db.query(CourseEnrollment.course_id, func.count(CourseEnrollment.id))
        .filter(CourseEnrollment.course_id.in_(course_ids))
        .group_by(CourseEnrollment.course_id)
        .all()
    )
    return {course_id: count for course_id, count in rows}


def section_progress_map(
    db: Session, user_id: int, section_ids: list[int]
) -> dict[int, SectionProgress]:
    """Записи о прогулках пользователя: «id секции → запись (дневник/собака)»."""
    if not section_ids:
        return {}
    rows = (
        db.query(SectionProgress)
        .filter(
            SectionProgress.user_id == user_id,
            SectionProgress.section_id.in_(section_ids),
        )
        .all()
    )
    return {row.section_id: row for row in rows}


def exercise_progress_map(
    db: Session, user_id: int, section_ids: list[int]
) -> dict[int, ExerciseProgress]:
    """Отметки упражнений пользователя: «id упражнения → отметка»."""
    if not section_ids:
        return {}
    rows = (
        db.query(ExerciseProgress)
        .join(Exercise, Exercise.id == ExerciseProgress.exercise_id)
        .filter(
            ExerciseProgress.user_id == user_id,
            Exercise.section_id.in_(section_ids),
        )
        .all()
    )
    return {row.exercise_id: row for row in rows}


def dog_names_map(db: Session, user_id: int, dog_ids: list[int]) -> dict[int, str]:
    """Клички собак пользователя — чтобы показать, с кем гуляли."""
    ids = [dog_id for dog_id in dog_ids if dog_id is not None]
    if not ids:
        return {}
    rows = (
        db.query(Dog.id, Dog.name)
        .filter(Dog.owner_id == user_id, Dog.id.in_(ids))
        .all()
    )
    return {dog_id: name for dog_id, name in rows}


def completed_section_ids(db: Session, user_id: int, section_ids: list[int]) -> set[int]:
    """Какие из перечисленных секций пользователь зачёл как пройденные."""
    if not section_ids:
        return set()
    rows = (
        db.query(SectionProgress.section_id)
        .filter(
            SectionProgress.user_id == user_id,
            SectionProgress.section_id.in_(section_ids),
            SectionProgress.completed_at.isnot(None),
        )
        .all()
    )
    return {section_id for (section_id,) in rows}


def ensure_course_access(db: Session, user: User, course_id: int) -> None:
    """Пускает к курсу только зачислённых (админ — исключение: он наполняет курс).

    Нет зачисления → 403, а не 404: курс существует, но доступ не открыт.
    """
    if user.role == "admin":
        return
    enrolled = (
        db.query(CourseEnrollment.id)
        .filter(
            CourseEnrollment.user_id == user.id,
            CourseEnrollment.course_id == course_id,
        )
        .first()
    )
    if not enrolled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ к курсу не открыт. Попросите администратора пригласить вас на курс",
        )


def course_list_items(
    db: Session,
    courses: list[Course],
    user_id: int,
    *,
    with_enrollment_counts: bool = False,
) -> list[CourseList]:
    """Единая форма карточки курса для пользователя и админки.

    with_enrollment_counts=True — в карточку добавляется число зачисленных
    (нужно админке), тип карточки при этом AdminCourseList.
    """
    course_ids = [course.id for course in courses]
    totals = sections_count_by_course(db, course_ids)
    exercises = exercises_count_by_course(db, course_ids)
    done = completed_count_by_course(db, user_id, course_ids)
    done_exercises = completed_exercise_counts_by_course(db, user_id, course_ids)
    enrolled = enrolled_count_by_course(db, course_ids) if with_enrollment_counts else {}
    model = AdminCourseList if with_enrollment_counts else CourseList

    items = []
    for course in courses:
        total_exercises = exercises.get(course.id, 0)
        completed_exercises = done_exercises.get(course.id, 0)
        # Процент считаем по упражнениям: «3 из 5 упражнений» честнее, чем
        # «0 из 1 прогулки». Если упражнений нет — по зачтённым прогулкам.
        if total_exercises:
            percent = round(completed_exercises / total_exercises * 100)
        else:
            total_sections = totals.get(course.id, 0)
            percent = round(done.get(course.id, 0) / total_sections * 100) if total_sections else 0
        items.append(
            model(
                id=course.id,
                title=course.title,
                description=course.description,
                sections_count=totals.get(course.id, 0),
                completed_count=done.get(course.id, 0),
                exercises_count=total_exercises,
                completed_exercises_count=completed_exercises,
                percent=percent,
                **(
                    {"enrolled_count": enrolled.get(course.id, 0)}
                    if with_enrollment_counts
                    else {}
                ),
            )
        )
    return items


def _get_section(db: Session, current_user: User, section_id: int) -> CourseSection:
    """Секция с проверкой доступа пользователя к её курсу."""
    section = db.get(CourseSection, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Секция не найдена")
    ensure_course_access(db, current_user, section.course_id)
    return section


def _maybe_complete_section(db: Session, user_id: int, section_id: int) -> bool:
    """Если все упражнения прогулки отмечены — зачитываем прогулку.

    Вызывать ПОСЛЕ db.flush(): сессия создана с autoflush=False, иначе свежая
    отметка не попадёт в подсчёт. Возвращает True, если прогулка зачтена.
    """
    total = (
        db.query(func.count(Exercise.id))
        .filter(Exercise.section_id == section_id)
        .scalar()
    )
    if not total:
        return False
    done = (
        db.query(func.count(ExerciseProgress.id))
        .join(Exercise, Exercise.id == ExerciseProgress.exercise_id)
        .filter(
            Exercise.section_id == section_id,
            ExerciseProgress.user_id == user_id,
        )
        .scalar()
    )
    if done < total:
        return False

    progress = (
        db.query(SectionProgress)
        .filter(
            SectionProgress.user_id == user_id,
            SectionProgress.section_id == section_id,
        )
        .first()
    )
    if progress is None:
        db.add(
            SectionProgress(
                user_id=user_id,
                section_id=section_id,
                completed_at=datetime.now(timezone.utc),
            )
        )
        return True
    if progress.completed_at is None:
        progress.completed_at = datetime.now(timezone.utc)
        return True
    return False


# ========================
# Эндпоинты пользователя
# ========================


@router.get("/courses", response_model=list[CourseList])
def list_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список курсов, доступных пользователю, с его прогрессом.

    Обычный пользователь видит только курсы, на которые его зачислил админ.
    Администратору показываем все курсы — он их наполняет.
    """
    if current_user.role == "admin":
        courses = db.query(Course).order_by(Course.id.asc()).all()
    else:
        courses = (
            db.query(Course)
            .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
            .filter(CourseEnrollment.user_id == current_user.id)
            .order_by(Course.id.asc())
            .all()
        )
    return course_list_items(db, courses, current_user.id)


@router.get("/courses/stats", response_model=CourseStatsRead)
def course_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Статистика прохождения: серия дней, время и оценки.

    Объявлен ДО /courses/{course_id}: иначе «stats» попал бы в числовой
    параметр пути и вернулась бы ошибка валидации.
    """
    walks = (
        db.query(SectionProgress.completed_at, SectionProgress.actual_minutes, SectionProgress.rating)
        .filter(
            SectionProgress.user_id == current_user.id,
            SectionProgress.completed_at.isnot(None),
        )
        .all()
    )
    today = datetime.now(timezone.utc).date()
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    days = sorted({completed_at.date() for completed_at, _, _ in walks})
    total_minutes = sum(minutes or 0 for _, minutes, _ in walks)
    ratings = [rating for _, _, rating in walks if rating is not None]

    walks_this_week = sum(
        1 for completed_at, _, _ in walks if completed_at >= week_ago
    )

    current_streak = 0
    if days and (today - days[-1]).days <= 1:
        current_streak = 1
        for index in range(len(days) - 1, 0, -1):
            if (days[index] - days[index - 1]).days == 1:
                current_streak += 1
            else:
                break

    best_streak = 0
    run = 0
    previous: date | None = None
    for day in days:
        run = run + 1 if previous is not None and (day - previous).days == 1 else 1
        best_streak = max(best_streak, run)
        previous = day

    completed_exercises = (
        db.query(func.count(ExerciseProgress.id))
        .filter(ExerciseProgress.user_id == current_user.id)
        .scalar()
    )

    return CourseStatsRead(
        total_walks=len(walks),
        walks_this_week=walks_this_week,
        current_streak=current_streak,
        best_streak=best_streak,
        total_minutes=total_minutes,
        completed_exercises=completed_exercises or 0,
        average_rating=round(sum(ratings) / len(ratings), 1) if ratings else None,
    )


@router.get("/courses/{course_id}", response_model=CourseRead)
def get_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Курс целиком: секции (прогулки) и упражнения, с отметками пользователя."""
    course = (
        db.query(Course).options(*COURSE_DETAIL_LOADS).filter(Course.id == course_id).first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    # Курс существует, но доступен только зачисленным пользователям.
    ensure_course_access(db, current_user, course.id)

    section_ids = [section.id for section in course.sections]
    progress = section_progress_map(db, current_user.id, section_ids)
    exercise_progress = exercise_progress_map(db, current_user.id, section_ids)
    dog_names = dog_names_map(
        db,
        current_user.id,
        [row.dog_id for row in progress.values()],
    )
    return course_detail_read(
        course,
        section_progress=progress,
        exercise_progress=exercise_progress,
        dog_names=dog_names,
    )


# ========================
# Прогулка: зачёт, дневник и собака
# ========================


@router.post("/sections/{section_id}/complete", response_model=SectionProgressRead)
def complete_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Зачесть прогулку пройденной. Идемпотентно: повторный вызов не ошибка,
    а возврат уже существующей отметки (дата первой отметки сохраняется)."""
    section = _get_section(db, current_user, section_id)

    progress = (
        db.query(SectionProgress)
        .filter(
            SectionProgress.user_id == current_user.id,
            SectionProgress.section_id == section.id,
        )
        .first()
    )
    if progress is not None and progress.completed_at is not None:
        return progress

    if progress is None:
        progress = SectionProgress(
            user_id=current_user.id,
            section_id=section.id,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(progress)
    else:
        # Запись уже была (прогулку начали, выбрав собаку) — только зачитываем.
        progress.completed_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except IntegrityError:
        # Уникальный индекс (user_id, section_id) — защита от двух параллельных
        # отметок. Возвращаем уже созданную запись, а не ошибку.
        db.rollback()
        progress = (
            db.query(SectionProgress)
            .filter(
                SectionProgress.user_id == current_user.id,
                SectionProgress.section_id == section.id,
            )
            .first()
        )
        if progress:
            return progress
        raise
    db.refresh(progress)
    return progress


@router.delete("/sections/{section_id}/complete", status_code=status.HTTP_204_NO_CONTENT)
def reset_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Снять отметку о прохождении (пройти прогулку заново).

    Удаляем всю запись о прогулке вместе с дневником: иначе «пройти заново»
    оставляло бы старую заметку и оценку от прошлого раза.
    """
    section = _get_section(db, current_user, section_id)

    (
        db.query(SectionProgress)
        .filter(
            SectionProgress.user_id == current_user.id,
            SectionProgress.section_id == section.id,
        )
        .delete()
    )
    db.commit()


@router.put("/sections/{section_id}/progress", response_model=SectionProgressRead)
def update_section_progress(
    section_id: int,
    data: SectionDiaryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Сохранить дневник прогулки: собаку, заметку, оценку, погоду и минуты.

    Запись создаётся при первом сохранении (это и есть «старт прогулки»):
    started_at заполняет сервер, completed_at остаётся пустым, пока прогулку
    не зачтут. Присылаем только изменённые поля — остальные не трогаем.
    """
    section = _get_section(db, current_user, section_id)

    changes = data.model_dump(exclude_unset=True)

    # Собака должна принадлежать пользователю: чужой id — 404, как и у собак.
    if changes.get("dog_id") is not None:
        owns = (
            db.query(Dog.id)
            .filter(Dog.id == changes["dog_id"], Dog.owner_id == current_user.id)
            .first()
        )
        if not owns:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Собака не найдена или не принадлежит вам",
            )

    progress = (
        db.query(SectionProgress)
        .filter(
            SectionProgress.user_id == current_user.id,
            SectionProgress.section_id == section.id,
        )
        .first()
    )
    if progress is None:
        progress = SectionProgress(user_id=current_user.id, section_id=section.id)
        db.add(progress)

    for field, value in changes.items():
        setattr(progress, field, value)

    db.commit()
    db.refresh(progress)
    return progress


# ========================
# Отметки упражнений
# ========================


@router.post("/exercises/{exercise_id}/complete", response_model=ExerciseProgressRead)
def complete_exercise(
    exercise_id: int,
    data: ExerciseComplete | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отметить упражнение отработанным. Идемпотентно.

    Тело необязательно: {actual_seconds} — фактическое время по таймеру.
    Когда отмечены все упражнения прогулки, прогулка зачитывается автоматически.
    """
    exercise = db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Упражнение не найдено")
    ensure_course_access(db, current_user, exercise.section.course_id)

    actual_seconds = data.actual_seconds if data else 0

    item = (
        db.query(ExerciseProgress)
        .filter(
            ExerciseProgress.user_id == current_user.id,
            ExerciseProgress.exercise_id == exercise.id,
        )
        .first()
    )
    if item is None:
        item = ExerciseProgress(
            user_id=current_user.id,
            exercise_id=exercise.id,
            actual_seconds=actual_seconds,
        )
        db.add(item)
    elif actual_seconds > item.actual_seconds:
        # Повторный запуск таймера — оставляем лучшее (наибольшее) время.
        item.actual_seconds = actual_seconds

    db.flush()
    _maybe_complete_section(db, current_user.id, exercise.section_id)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/exercises/{exercise_id}/complete", status_code=status.HTTP_204_NO_CONTENT)
def reset_exercise(
    exercise_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Снять отметку с упражнения (сделать его снова невыполненным)."""
    exercise = db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Упражнение не найдено")
    ensure_course_access(db, current_user, exercise.section.course_id)

    (
        db.query(ExerciseProgress)
        .filter(
            ExerciseProgress.user_id == current_user.id,
            ExerciseProgress.exercise_id == exercise.id,
        )
        .delete()
    )
    db.commit()
