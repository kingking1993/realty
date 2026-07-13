"""테이블 정의."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Complex(Base):
    __tablename__ = "complexes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    naver_complex_no: Mapped[str] = mapped_column(String, unique=True)
    lawd_cd: Mapped[str] = mapped_column(String)  # 법정동코드 앞 5자리
    umd_nm: Mapped[str] = mapped_column(String, default="")  # 법정동 이름 (동명 단지 구분용)
    apt_name_molit: Mapped[str] = mapped_column(String, default="")

    listings: Mapped[list["Listing"]] = relationship(back_populates="complex")


class Listing(Base):
    """네이버 부동산 매물. 스냅샷 diff 로 상태를 관리한다."""

    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_no: Mapped[str] = mapped_column(String, unique=True, index=True)
    complex_id: Mapped[int] = mapped_column(ForeignKey("complexes.id"), index=True)
    trade_type: Mapped[str] = mapped_column(String)  # 매매/전세/월세
    dong: Mapped[str] = mapped_column(String, default="")  # 동(棟) 예: "101동"
    floor_info: Mapped[str] = mapped_column(String, default="")  # 예: "12/25", "중/25"
    area_exclusive: Mapped[float] = mapped_column(Float, default=0.0)  # 전용면적 ㎡
    price: Mapped[int] = mapped_column(Integer, default=0)  # 매매가/보증금 (만원)
    price_monthly: Mapped[int] = mapped_column(Integer, default=0)  # 월세 (만원)
    description: Mapped[str] = mapped_column(Text, default="")
    first_seen: Mapped[datetime] = mapped_column(DateTime)
    last_seen: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String, default="active", index=True)  # active/removed
    removed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    complex: Mapped["Complex"] = relationship(back_populates="listings")
    events: Mapped[list["ListingEvent"]] = relationship(back_populates="listing")


class ListingEvent(Base):
    """매물 변동 로그: NEW / PRICE_CHANGED / REMOVED."""

    __tablename__ = "listing_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    event: Mapped[str] = mapped_column(String, index=True)
    old_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    listing: Mapped["Listing"] = relationship(back_populates="events")


class DailyCount(Base):
    """매물 수 추이 (수집 시점 집계)."""

    __tablename__ = "daily_counts"
    __table_args__ = (UniqueConstraint("complex_id", "date", "trade_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complex_id: Mapped[int] = mapped_column(ForeignKey("complexes.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    trade_type: Mapped[str] = mapped_column(String)
    count: Mapped[int] = mapped_column(Integer)


class Transaction(Base):
    """국토부 실거래 (매매)."""

    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("complex_id", "deal_date", "price", "area_exclusive", "floor", "apt_dong"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complex_id: Mapped[int] = mapped_column(ForeignKey("complexes.id"), index=True)
    deal_date: Mapped[date] = mapped_column(Date, index=True)
    price: Mapped[int] = mapped_column(Integer)  # 만원
    area_exclusive: Mapped[float] = mapped_column(Float)
    floor: Mapped[int] = mapped_column(Integer)
    apt_dong: Mapped[str] = mapped_column(String, default="")  # 등기 완료 건만 제공됨
    is_canceled: Mapped[bool] = mapped_column(Boolean, default=False)


class Match(Base):
    """소멸 매물 ↔ 실거래 매칭 추정 로그."""

    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("listing_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True)
    confidence: Mapped[str] = mapped_column(String)  # HIGH/MEDIUM/LOW
    matched_at: Mapped[datetime] = mapped_column(DateTime)

    listing: Mapped["Listing"] = relationship()
    transaction: Mapped["Transaction"] = relationship()


class Article(Base):
    """뉴스/카페 글."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String, index=True)  # news/cafe
    complex_id: Mapped[int] = mapped_column(ForeignKey("complexes.id"), index=True)
    keyword: Mapped[str] = mapped_column(String, default="")
    title: Mapped[str] = mapped_column(String)
    link: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    pub_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime)


class CollectionLog(Base):
    """수집 잡 실행 기록."""

    __tablename__ = "collection_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job: Mapped[str] = mapped_column(String, index=True)  # listings/transactions/articles
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    detail: Mapped[str] = mapped_column(Text, default="")
