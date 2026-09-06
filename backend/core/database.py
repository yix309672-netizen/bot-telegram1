# coding=utf-8
"""数据库层：SQLAlchemy 模型 + 会话管理
MySQL 优先（读 DATABASE_URL），连不上自动回退本地 SQLite，保证开箱可用。
"""
import logging
import os
from datetime import datetime

from sqlalchemy import DateTime, String, Text, Boolean, Integer, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class PhoneNumber(Base):
    # 号码表：number 唯一，防重复生成
    __tablename__ = "phone_numbers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    country: Mapped[str] = mapped_column(String(10), default="HK")
    status: Mapped[str] = mapped_column(String(20), default="generated", index=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SmsRecord(Base):
    # 短信记录表
    __tablename__ = "sms_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(20), index=True)
    content: Mapped[str] = mapped_column(Text)
    sender: Mapped[str] = mapped_column(String(50), default="TelegramBot")
    status: Mapped[str] = mapped_column(String(20), default="queued")
    note: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    # 审计日志表：记录变更类请求（操作人/IP/路径/结果）
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), default="")
    ip: Mapped[str] = mapped_column(String(50), default="")
    method: Mapped[str] = mapped_column(String(10), default="")
    path: Mapped[str] = mapped_column(String(255), default="")
    status_code: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def _default_sqlite_url() -> str:
    # 默认 SQLite 落到 backend/data/app.db，与代码同盘，开箱可用
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    return "sqlite:///" + os.path.join(data_dir, "app.db")


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return url
    # 兼容 docker-compose 外的分散变量
    host = os.getenv("DB_HOST", "")
    if host:
        user = os.getenv("DB_USER", "telegram")
        pwd = os.getenv("DB_PASSWORD", "telegrampass")
        port = os.getenv("DB_PORT", "3306")
        name = os.getenv("DB_NAME", "telegramdb")
        return f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{name}?charset=utf8mb4"
    return _default_sqlite_url()


def _make_engine(url: str):
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600)


DATABASE_URL = get_database_url()
try:
    engine = _make_engine(DATABASE_URL)
    # 建连探测，MySQL 挂了就回退 SQLite
    with engine.connect():
        pass
    logger.info(f"数据库已连接: {DATABASE_URL.split('@')[-1]}")
except Exception as e:
    logger.warning(f"主数据库连接失败，回退本地 SQLite: {e}")
    DATABASE_URL = _default_sqlite_url()
    engine = _make_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    # 建表（已存在则跳过）
    Base.metadata.create_all(bind=engine)


def get_db():
    # FastAPI 依赖：按请求提供会话
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
