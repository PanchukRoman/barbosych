from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Article, Event, EventRegistration, User
from ..schemas import (
    ArticleCreate,
    ArticleUpdate,
    ArticleRead,
    ArticleList,
    EventCreate,
    EventUpdate,
    EventRead,
    EventRegistrationRead,
)

router = APIRouter(prefix="/admin", tags=["Admin"])


def require_admin(current_user: User = Depends(get_current_user)):
    """Проверяет, что текущий пользователь — админ."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ только для администраторов",
        )
    return current_user


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
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """Список всех статей (без полного контента)."""
    articles = db.query(Article).order_by(Article.created_at.desc()).offset(skip).limit(limit).all()
    return articles


@router.get("/articles/{article_id}", response_model=ArticleRead)
def get_article(
    article_id: int,
    db: Session = Depends(get_db),
):
    """Получение одной статьи по ID."""
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
    """Создание нового события. Только админ."""
    from datetime import datetime as dt
    event = Event(
        title=data.title,
        description=data.description,
        date=dt.fromisoformat(data.date.replace("Z", "+00:00")),
        location=data.location,
        max_participants=data.max_participants,
        author_id=admin.id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/events", response_model=list[EventRead])
def list_events(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список всех событий."""
    events = db.query(Event).order_by(Event.date.desc()).offset(skip).limit(limit).all()
    return events


@router.get("/events/{event_id}", response_model=EventRead)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
):
    """Получение одного события по ID."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    return event


@router.put("/events/{event_id}", response_model=EventRead)
def update_event(
    event_id: int,
    data: EventUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Обновление события. Только админ."""
    from datetime import datetime as dt
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")

    if data.title is not None:
        event.title = data.title
    if data.description is not None:
        event.description = data.description
    if data.date is not None:
        event.date = dt.fromisoformat(data.date.replace("Z", "+00:00"))
    if data.location is not None:
        event.location = data.location
    if data.max_participants is not None:
        event.max_participants = data.max_participants

    db.commit()
    db.refresh(event)
    return event


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
