"""数据库模型定义"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime,
    ForeignKey, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _now():
    return datetime.now(timezone.utc)


class User(Base):
    """用户（以自定义昵称/口令作为唯一标识，无密码）"""
    __tablename__ = "users"

    id = Column(String(100), primary_key=True)  # 用户自填的唯一标识，直接作为 PK
    created_at = Column(DateTime(timezone=True), default=_now)
    last_seen_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    visits = relationship("ParkVisit", back_populates="user", cascade="all, delete-orphan")


class ParkVisit(Base):
    """一次游园记录（对应一个 AI 会话）"""
    __tablename__ = "park_visits"

    id = Column(String(50), primary_key=True)  # UUID，同时作为 Redis session_id
    user_id = Column(String(100), ForeignKey("users.id"), nullable=False)
    park_id = Column(String(50), ForeignKey("parks.id"), nullable=False)
    visit_date = Column(String(20))  # "2026-05-18"
    status = Column(String(20), default="active")  # active | archived
    planning_snapshot = Column(JSON)  # 入园前填写的规划信息快照
    completed_attractions = Column(JSON, default=list)
    current_location = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    user = relationship("User", back_populates="visits")
    park = relationship("Park")

    __table_args__ = (
        Index("ix_park_visits_user_status", "user_id", "status"),
    )


class Park(Base):
    """乐园基本信息"""
    __tablename__ = "parks"

    id = Column(String(50), primary_key=True)  # e.g. "hongkong_disney"
    name = Column(String(100), nullable=False)
    name_en = Column(String(100))
    location = Column(String(100))
    timezone = Column(String(50), default="Asia/Hong_Kong")
    queue_times_park_id = Column(Integer)  # queue-times.com park ID
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    attractions = relationship("Attraction", back_populates="park", cascade="all, delete-orphan")
    strategies = relationship("Strategy", back_populates="park", cascade="all, delete-orphan")


class Attraction(Base):
    """乐园项目（游乐设施/表演/餐厅等）"""
    __tablename__ = "attractions"

    id = Column(String(100), primary_key=True)  # e.g. "hyperspace_mountain"
    park_id = Column(String(50), ForeignKey("parks.id"), nullable=False)
    queue_times_ride_id = Column(Integer, index=True)  # queue-times.com ride ID，用于匹配实时数据
    name = Column(String(200), nullable=False)
    name_en = Column(String(200))
    category = Column(String(50))  # thrill_ride / family_ride / show / character_meet / dining
    area_name = Column(String(100))
    description = Column(Text)
    duration_minutes = Column(Integer)
    min_height_cm = Column(Integer)
    lat = Column(Float)
    lng = Column(Float)
    is_lightning_lane = Column(Boolean, default=False)
    suitable_for = Column(JSON, default=list)   # ["adults", "children", ...]
    not_suitable_for = Column(JSON, default=list)
    tips = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    park = relationship("Park", back_populates="attractions")

    __table_args__ = (
        Index("ix_attractions_park_category", "park_id", "category"),
    )


class Strategy(Base):
    """从小红书/抖音采集的游园攻略"""
    __tablename__ = "strategies"

    id = Column(String(100), primary_key=True)  # MD5 of source_url
    park_id = Column(String(50), ForeignKey("parks.id"), nullable=False)
    platform = Column(String(20), nullable=False)  # "xhs" / "douyin"
    source_url = Column(String(500), unique=True)
    title = Column(String(500))
    content = Column(Text)
    author = Column(String(200))
    likes = Column(Integer, default=0)
    collects = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    tags = Column(JSON, default=list)  # 提取的标签/关键词
    mentioned_attractions = Column(JSON, default=list)  # 提到的项目名称
    image_urls = Column(JSON, default=list)  # 图片 CDN URL 列表
    ai_summary = Column(Text)  # AI 提炼的摘要（Claude 处理后）
    collected_at = Column(DateTime(timezone=True), default=_now)
    is_active = Column(Boolean, default=True)

    park = relationship("Park", back_populates="strategies")

    __table_args__ = (
        Index("ix_strategies_park_platform", "park_id", "platform"),
        Index("ix_strategies_likes", "likes"),
    )
