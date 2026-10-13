"""Курс дрессировки: прохождение пользователем.

Наполнение курса (создание секций/упражнений) живёт в admin.py, а здесь —
то, что видит и делает обычный пользователь: список курсов, детальный
просмотр и отметки о пройденных прогулках.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..loaders import COURSE_DETAIL_LOADS
from ..models import Course, CourseEnrollment, CourseSection, SectionProgress, User
from ..schemas import AdminCourseList, CourseList, CourseRead, SectionProgressRead
from ..serializers import course_detail_read

router = APIRouter(tags=["Course"])


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


def completed_count_by_course(
    db: Session, user_id: int, course_ids: list[int]
) -> dict[int, int]:
    """Сколько секций каждого курса прошёл пользователь — тоже одним запросом."""
    if not course_ids:
        return {}
    rows = (
        db.query(CourseSection.course_id, func.count(SectionProgress.id))
        .join(SectionProgress, SectionProgress.section_id == CourseSection.id)
        .filter(
            CourseSection.course_id.in_(course_ids),
            SectionProgress.user_id == user_id,
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
    done = completed_count_by_course(db, user_id, course_ids)
    enrolled = enrolled_count_by_course(db, course_ids) if with_enrollment_counts else {}
    model = AdminCourseList if with_enrollment_counts else CourseList
    return [
        model(
            id=course.id,
            title=course.title,
            description=course.description,
            sections_count=totals.get(course.id, 0),
            completed_count=done.get(course.id, 0),
            **({"enrolled_count": enrolled.get(course.id, 0)} if with_enrollment_counts else {}),
        )
        for course in courses
    ]


def completed_section_ids(db: Session, user_id: int, section_ids: list[int]) -> set[int]:
    """Какие из перечисленных секций пользователь уже прошёл."""
    if not section_ids:
        return set()
    rows = (
        db.query(SectionProgress.section_id)
        .filter(
            SectionProgress.user_id == user_id,
            SectionProgress.section_id.in_(section_ids),
        )
        .all()
    )
    return {section_id for (section_id,) in rows}


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

    done = completed_section_ids(
        db, current_user.id, [section.id for section in course.sections]
    )
    return course_detail_read(course, done)


@router.post("/sections/{section_id}/complete", response_model=SectionProgressRead)
def complete_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отметить секцию (прогулку) пройденной. Идемпотентно: повторный вызов
    не ошибка, а возврат уже существующей отметки."""
    section = db.get(CourseSection, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Секция не найдена")
    ensure_course_access(db, current_user, section.course_id)

    existing = (
        db.query(SectionProgress)
        .filter(
            SectionProgress.user_id == current_user.id,
            SectionProgress.section_id == section_id,
        )
        .first()
    )
    if existing:
        return existing

    progress = SectionProgress(user_id=current_user.id, section_id=section_id)
    db.add(progress)
    try:
        db.commit()
    except IntegrityError:
        # Уникальный индекс (user_id, section_id) — защита от двух параллельных
        # отметок. Возвращаем уже созданную запись, а не ошибку.
        db.rollback()
        existing = (
            db.query(SectionProgress)
            .filter(
                SectionProgress.user_id == current_user.id,
                SectionProgress.section_id == section_id,
            )
            .first()
        )
        if existing:
            return existing
        raise
    db.refresh(progress)
    return progress


@router.delete("/sections/{section_id}/complete", status_code=status.HTTP_204_NO_CONTENT)
def reset_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Снять отметку о прохождении (пройти прогулку заново)."""
    section = db.get(CourseSection, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Секция не найдена")
    ensure_course_access(db, current_user, section.course_id)

    (
        db.query(SectionProgress)
        .filter(
            SectionProgress.user_id == current_user.id,
            SectionProgress.section_id == section_id,
        )
        .delete()
    )
    db.commit()
