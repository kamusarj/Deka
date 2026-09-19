from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text, func

from app.core.database import Base


class CommunityTopic(Base):
    __tablename__ = "community_topics"

    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    content = Column(Text, nullable=False)
    grade = Column(Integer, nullable=True, index=True)
    type = Column(String(32), nullable=False, index=True)
    difficulty = Column(String(32), nullable=False)
    question = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)


class CommunityComment(Base):
    __tablename__ = "community_comments"

    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("community_topics.id"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("community_comments.id"), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
