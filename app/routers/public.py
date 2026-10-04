from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Article, Event, EventRegistration, User
from ..schemas import EventRead, EventRegistrationRead

router = APIRouter(tags=["Public"])


@router.get("/articles", response_model=list[dict])
def list_articles(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """Публичный список статей."""
    articles = db.query(Article).order_by(Article.created_at.desc()).offset(skip).limit(limit).all()
    result = []
    for a in articles:
        result.append({
            "id": a.id,
            "title": a.title,
            "excerpt": a.excerpt or a.content[:200] + "..." if len(a.content) > 200 else a.content,
            "author_id": a.author_id,
            "created_at": a.created_at.isoformat(),
        })
    return result


@router.get("/articles/{article_id}", response_model=dict)
def get_article(
    article_id: int,
    db: Session = Depends(get_db),
):
    """Публичное чтение одной статьи."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Статья не найдена")
    return {
        "id": article.id,
        "title": article.title,
        "content": article.content,
        "excerpt": article.excerpt,
        "author_id": article.author_id,
        "created_at": article.created_at.isoformat(),
        "updated_at": article.updated_at.isoformat() if article.updated_at else None,
    }


@router.get("/events", response_model=list[dict])
def list_events(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Публичный список событий с информацией о записи."""
    events = db.query(Event).order_by(Event.date.desc()).offset(skip).limit(limit).all()
    result = []
    for e in events:
        registered_count = db.query(EventRegistration).filter(
            EventRegistration.event_id == e.id
        ).count()
        is_registered = bool(
            db.query(EventRegistration).filter(
                EventRegistration.event_id == e.id,
                EventRegistration.user_id == current_user.id,
            ).first()
        )
        result.append({
            "id": e.id,
            "title": e.title,
            "description": e.description,
            "date": e.date.isoformat(),
            "location": e.location,
            "max_participants": e.max_participants,
            "registered_count": registered_count,
            "is_registered": is_registered,
            "created_at": e.created_at.isoformat(),
        })
    return result


@router.get("/events/{event_id}", response_model=dict)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Публичное чтение одного события."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")

    registered_count = db.query(EventRegistration).filter(
        EventRegistration.event_id == event.id
    ).count()
    is_registered = bool(
        db.query(EventRegistration).filter(
            EventRegistration.event_id == event.id,
            EventRegistration.user_id == current_user.id,
        ).first()
    )

    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "date": event.date.isoformat(),
        "location": event.location,
        "max_participants": event.max_participants,
        "registered_count": registered_count,
        "is_registered": is_registered,
        "created_at": event.created_at.isoformat(),
    }


# ========================
# Записи на события
# ========================

@router.post("/events/{event_id}/register", response_model=dict, status_code=status.HTTP_201_CREATED)
def register_for_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Запись пользователя на событие."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")

    # Проверка: не записан ли уже
    existing = db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id,
        EventRegistration.user_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Вы уже записаны на это событие")

    # Проверка: не переполнено ли
    registered_count = db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id
    ).count()
    if registered_count >= event.max_participants:
        raise HTTPException(status_code=400, detail="Мест на событии больше нет")

    registration = EventRegistration(
        user_id=current_user.id,
        event_id=event_id,
    )
    db.add(registration)
    db.commit()
    db.refresh(registration)

    return {
        "id": registration.id,
        "user_id": registration.user_id,
        "event_id": registration.event_id,
        "registered_at": registration.registered_at.isoformat(),
    }


@router.delete("/events/{event_id}/register", status_code=status.HTTP_204_NO_CONTENT)
def cancel_registration(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отмена записи на событие."""
    registration = db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id,
        EventRegistration.user_id == current_user.id,
    ).first()
    if not registration:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    db.delete(registration)
    db.commit()


@router.get("/my-events", response_model=list[dict])
def my_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список событий, на которые записан текущий пользователь."""
    registrations = db.query(EventRegistration).filter(
        EventRegistration.user_id == current_user.id
    ).all()

    result = []
    for reg in registrations:
        event = db.query(Event).filter(Event.id == reg.event_id).first()
        if event:
            result.append({
                "registration_id": reg.id,
                "event_id": event.id,
                "event_title": event.title,
                "event_date": event.date.isoformat(),
                "event_location": event.location,
                "registered_at": reg.registered_at.isoformat(),
            })
    return result
