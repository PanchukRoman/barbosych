"""Лента уведомлений текущего пользователя (колокольчик в кабинете).

Каждая запись адресована конкретному пользователю, поэтому фильтр по
current_user.id стоит во всех запросах: ни посмотреть, ни очистить чужую ленту
через API нельзя. Создаются записи не здесь, а в момент публикации контента —
см. app/notifications.py.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Notification, User
from ..schemas import NotificationList, NotificationRead

router = APIRouter(prefix="/notifications", tags=["Notifications"])

# Сколько записей отдаём в ленту. Колокольчик — про «что нового», а не архив.
LIST_LIMIT = 50


def _feed(db: Session, user: User) -> NotificationList:
    """Лента пользователя: последние записи (новые сверху) и счётчик непрочитанных.

    Счётчик считаем отдельным запросом по всей таблице пользователя: в items попадает не больше
    LIST_LIMIT строк, и по ним бейдж занижал бы число.
    """
    items = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.id.desc())
        .limit(LIST_LIMIT)
        .all()
    )
    unread = (
        db.query(func.count(Notification.id))
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .scalar()
        or 0
    )
    return NotificationList(
        items=[NotificationRead.model_validate(item) for item in items],
        unread_count=unread,
    )


@router.get("", response_model=NotificationList)
def list_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Уведомления текущего пользователя, новые сверху."""
    return _feed(db, current_user)


@router.post("/read", response_model=NotificationList)
def mark_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отметить все уведомления прочитанными — пользователь открыл ленту.

    Записи не удаляем: иначе «прочитал» и «очистил» стали бы одним действием и
    история исчезала бы при первом открытии колокольчика. Идемпотентно.
    """
    (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.read_at.is_(None))
        .update({Notification.read_at: func.now()}, synchronize_session=False)
    )
    db.commit()
    return _feed(db, current_user)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Очистить ленту пользователя (кнопка «Очистить» в колокольчике)."""
    (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .delete(synchronize_session=False)
    )
    db.commit()
