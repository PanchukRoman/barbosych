from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..loaders import EVENT_DETAIL_LOADS
from ..models import Article, Event, EventRegistration, User
from ..schemas import ArticleList, ArticleRead, EventRead, EventRegistrationRead, MyEventRead
from ..serializers import article_list_item, event_read, participants_of

router = APIRouter(tags=["Public"])


@router.get("/articles", response_model=list[ArticleList])
def list_articles(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Публичный список статей."""
    articles = (
        db.query(Article).order_by(Article.created_at.desc()).offset(skip).limit(limit).all()
    )
    return [article_list_item(article) for article in articles]


@router.get("/articles/{article_id}", response_model=ArticleRead)
def get_article(
    article_id: int,
    db: Session = Depends(get_db),
):
    """Публичное чтение одной статьи."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Статья не найдена")
    return article


@router.get("/events", response_model=list[EventRead])
def list_events(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Публичный список событий с информацией о записи.

    Раньше на каждое событие делалось 2 отдельных запроса (count + «записан ли я»).
    Теперь это ровно 3 запроса на весь список независимо от его длины.
    """
    events = db.query(Event).order_by(Event.date.desc()).offset(skip).limit(limit).all()
    event_ids = [event.id for event in events]

    counts: dict[int, int] = {}
    my_event_ids: set[int] = set()
    if event_ids:
        counts = {
            event_id: count
            for event_id, count in db.query(
                EventRegistration.event_id, func.count(EventRegistration.id)
            )
            .filter(EventRegistration.event_id.in_(event_ids))
            .group_by(EventRegistration.event_id)
            .all()
        }
        my_event_ids = {
            event_id
            for (event_id,) in db.query(EventRegistration.event_id)
            .filter(
                EventRegistration.user_id == current_user.id,
                EventRegistration.event_id.in_(event_ids),
            )
            .all()
        }

    return [
        event_read(
            event,
            registered_count=counts.get(event.id, 0),
            is_registered=event.id in my_event_ids,
        )
        for event in events
    ]


@router.get("/events/{event_id}", response_model=EventRead)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Публичное чтение одного события вместе с участниками.

    Участники, их пользователи и собаки подгружаются заранее (EVENT_DETAIL_LOADS) —
    иначе на каждого участника уходило по два лишних запроса.
    """
    event = (
        db.query(Event).options(*EVENT_DETAIL_LOADS).filter(Event.id == event_id).first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")

    return event_read(
        event,
        registered_count=len(event.registrations),
        is_registered=any(reg.user_id == current_user.id for reg in event.registrations),
        participants=participants_of(event),
    )


# ========================
# Записи на события
# ========================

@router.post(
    "/events/{event_id}/register",
    response_model=EventRegistrationRead,
    status_code=status.HTTP_201_CREATED,
)
def register_for_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Запись пользователя на событие."""
    # with_for_update блокирует строку события до конца транзакции: два
    # параллельных запроса не смогут одновременно занять последнее место.
    event = db.query(Event).filter(Event.id == event_id).with_for_update().first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")

    # Проверка: не записан ли уже
    existing = (
        db.query(EventRegistration)
        .filter(
            EventRegistration.event_id == event_id,
            EventRegistration.user_id == current_user.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Вы уже записаны на это событие")

    # Проверка: не переполнено ли
    registered_count = (
        db.query(EventRegistration).filter(EventRegistration.event_id == event_id).count()
    )
    if registered_count >= event.max_participants:
        raise HTTPException(status_code=400, detail="Мест на событии больше нет")

    registration = EventRegistration(user_id=current_user.id, event_id=event_id)
    db.add(registration)
    try:
        db.commit()
    except IntegrityError:
        # Уникальный индекс (user_id, event_id) — финальная защита от дублей
        # при одновременных запросах от одного и того же пользователя.
        db.rollback()
        raise HTTPException(status_code=409, detail="Вы уже записаны на это событие")
    db.refresh(registration)
    return registration


@router.delete("/events/{event_id}/register", status_code=status.HTTP_204_NO_CONTENT)
def cancel_registration(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отмена записи на событие."""
    registration = (
        db.query(EventRegistration)
        .filter(
            EventRegistration.event_id == event_id,
            EventRegistration.user_id == current_user.id,
        )
        .first()
    )
    if not registration:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    db.delete(registration)
    db.commit()


@router.get("/my-events", response_model=list[MyEventRead])
def my_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список событий, на которые записан текущий пользователь."""
    rows = (
        db.query(EventRegistration, Event)
        .join(Event, Event.id == EventRegistration.event_id)
        .filter(EventRegistration.user_id == current_user.id)
        .order_by(Event.date.asc())
        .all()
    )
    return [
        MyEventRead(
            registration_id=registration.id,
            event_id=event.id,
            event_title=event.title,
            event_date=event.date,
            event_location=event.location,
            registered_at=registration.registered_at,
        )
        for registration, event in rows
    ]
