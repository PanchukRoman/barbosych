"""Создание уведомлений о новом контенте.

Вынесено из роутеров, потому что писать в ленту нужно из разных мест админки
(статьи, события, курс) и по разным поводам. Здесь — единственное место, где
решается, кому и какой текст уходит.
"""
from collections.abc import Iterable, Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .models import CourseEnrollment, Notification, User

# Длина колонки notifications.text — длинный заголовок статьи в неё не влезает.
TEXT_LIMIT = 255
# Сколько записей храним на пользователя: колокольчик показывает новое, а не
# служит архивом. Таблица не растёт бесконечно.
HISTORY_LIMIT = 100


def _clip(text: str) -> str:
    """Обрезает текст до длины колонки, сохраняя признак обрезки."""
    if len(text) <= TEXT_LIMIT:
        return text
    return text[: TEXT_LIMIT - 1] + "\u2026"


def notify_users(db: Session, user_ids: Iterable[int], kind: str, text: str) -> list[int]:
    """Готовит уведомления перечисленным пользователям.

    Коммит — на вызывающем: уведомление о публикации уходит в той же
    транзакции, что и сама публикация, поэтому «контент есть, а уведомления
    нет» невозможно. Возвращает список получателей (дубликаты отброшены).
    """
    recipients = list(dict.fromkeys(user_ids))
    if not recipients:
        return []

    message = _clip(text)
    db.add_all(
        Notification(user_id=user_id, type=kind, text=message) for user_id in recipients
    )
    # flush нужен до чистки истории: новые строки должны получить id, иначе
    # row_number() может отнести их к «старым» и удалить только что созданное.
    db.flush()
    _trim_history(db, recipients)
    return recipients


def notify_all_users(
    db: Session, kind: str, text: str, *, exclude_user_id: int | None = None
) -> list[int]:
    """Уведомить всех зарегистрированных, кроме автора действия.

    Автор (админ, который только что опубликовал материал) уведомление о своей
    же публикации не получает — иначе лента заполняется «эхом» собственных
    действий.
    """
    query = select(User.id)
    if exclude_user_id is not None:
        query = query.where(User.id != exclude_user_id)
    return notify_users(db, db.scalars(query).all(), kind, text)


def notify_course_students(db: Session, course_id: int, kind: str, text: str) -> list[int]:
    """Уведомить тех, у кого есть доступ к курсу (зачисленных).

    Курс видят только зачисленные, поэтому про новую прогулку или упражнение
    узнают именно они, а не все пользователи подряд.
    """
    user_ids = db.scalars(
        select(CourseEnrollment.user_id).where(CourseEnrollment.course_id == course_id)
    ).all()
    return notify_users(db, user_ids, kind, text)


def _trim_history(db: Session, user_ids: Sequence[int]) -> None:
    """Оставляет каждому получателю последние HISTORY_LIMIT записей.

    Один запрос на всех: нумеруем записи окном внутри пользователя и удаляем
    всё, что вышло за предел.
    """
    ranked = (
        select(
            Notification.id.label("id"),
            func.row_number()
            .over(partition_by=Notification.user_id, order_by=Notification.id.desc())
            .label("rn"),
        )
        .where(Notification.user_id.in_(user_ids))
        .subquery()
    )
    db.execute(
        delete(Notification).where(
            Notification.id.in_(select(ranked.c.id).where(ranked.c.rn > HISTORY_LIMIT))
        )
    )
