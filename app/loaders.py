"""Готовые наборы eager-загрузок, чтобы не дублировать их по роутам.

Событие вместе с участниками, их пользователями и собаками — всё нужное
для карточки события одним набором запросов вместо запроса на каждого участника.
"""
from sqlalchemy.orm import joinedload, selectinload

from .models import Course, CourseSection, Event, EventRegistration, User

EVENT_DETAIL_LOADS = (
    selectinload(Event.registrations)
    .joinedload(EventRegistration.user)
    .selectinload(User.dogs),
)


# Курс целиком: секции и упражнения внутри каждой секции — одним набором
# запросов, а не по запросу на секцию (иначе на курсе из 10 прогулок их было
# бы 11). Используется при детальном просмотре курса и в админке.
COURSE_DETAIL_LOADS = (
    selectinload(Course.sections).selectinload(CourseSection.exercises),
)
