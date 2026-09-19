from fastapi import APIRouter, Depends, Query

from app.models.user import User
from app.schemas.community import CommentCreate, TopicCreate, TopicFromBank
from app.schemas.exam import Difficulty, QuestionType
from app.services.auth_service import get_current_user
from app.services.community_service import CommunityService
from app.services.rate_limit import SlidingWindowRateLimiter

router = APIRouter(prefix="/community/topics", tags=["community"])
community_service = CommunityService()
community_limiter = SlidingWindowRateLimiter()


def member(user: User = Depends(get_current_user)):
    community_service.require_member(user)
    return user


def contributor(user: User = Depends(member)):
    community_limiter.check(str(user.id), limit=30, window_seconds=60)
    return user


@router.get("")
def list_topics(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50),
                search: str | None = Query(None, max_length=200), grade: int | None = Query(None, ge=6, le=9),
                type: QuestionType | None = None, difficulty: Difficulty | None = None,
                user: User = Depends(member)):
    return community_service.list_topics(actor=user, page=page, page_size=page_size, search=search, grade=grade, type=type, difficulty=difficulty)


@router.post("", status_code=201)
def create_topic(request: TopicCreate, user: User = Depends(contributor)):
    return community_service.create_topic(request, actor=user)


@router.post("/from-bank", status_code=201)
def from_bank(request: TopicFromBank, user: User = Depends(contributor)):
    return community_service.publish_bank_question(request, actor=user)


@router.get("/{topic_id}")
def get_topic(topic_id: int, user: User = Depends(member)):
    return community_service.get_topic(topic_id, actor=user)


@router.delete("/{topic_id}")
def delete_topic(topic_id: int, user: User = Depends(contributor)):
    return community_service.delete_topic(topic_id, actor=user)


@router.get("/{topic_id}/comments")
def list_comments(topic_id: int, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=50), user: User = Depends(member)):
    return community_service.list_comments(topic_id, actor=user, page=page, page_size=page_size)


@router.post("/{topic_id}/comments", status_code=201)
def add_comment(topic_id: int, request: CommentCreate, user: User = Depends(contributor)):
    return community_service.add_comment(topic_id, request, actor=user)


@router.delete("/{topic_id}/comments/{comment_id}")
def delete_comment(topic_id: int, comment_id: int, user: User = Depends(contributor)):
    return community_service.delete_comment(topic_id, comment_id, actor=user)


@router.post("/{topic_id}/save", status_code=201)
def save_topic(topic_id: int, user: User = Depends(contributor)):
    return community_service.save_to_bank(topic_id, actor=user)
