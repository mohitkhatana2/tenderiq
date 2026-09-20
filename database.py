"""Persistence foundation. Defaults to SQLite; set DATABASE_URL for PostgreSQL."""
import os
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tenderiq.db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

class Base(DeclarativeBase):
    pass

class TenderRecord(Base):
    __tablename__ = "tenders"
    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    organization: Mapped[str] = mapped_column(String(300), index=True)
    deadline: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class TenderDocument(Base):
    __tablename__ = "tender_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    tender_id: Mapped[int | None] = mapped_column(ForeignKey("tenders.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(500))
    extracted_text: Mapped[str] = mapped_column(Text)
    analysis_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
