# coding=utf-8
"""数据库层：SQLAlchemy 模型 + 会话管理
MySQL 优先（读 DATABASE_URL），连不上自动回退本地 SQLite，保证开箱可用。
"""
import logging
import os
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, Boolean, Integer, create_engine
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
    # 短信记录表（含队列状态机：queued → sending → sent / failed，可重试）
    __tablename__ = "sms_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(20), index=True)
    content: Mapped[str] = mapped_column(Text)
    sender: Mapped[str] = mapped_column(String(50), default="TelegramBot")
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    note: Mapped[str] = mapped_column(String(255), default="")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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


class SystemConfig(Base):
    # 系统配置表（原PHP system.config：站点/上传等键值）
    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    remark: Mapped[str] = mapped_column(String(255), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UploadFile(Base):
    # 上传文件记录表（原PHP system.uploadfile）
    __tablename__ = "upload_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(500))
    size: Mapped[int] = mapped_column(Integer, default=0)
    uploader: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AdminUser(Base):
    # 后台账号表（原PHP system.admin，多账号+角色）
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="operator")
    status: Mapped[int] = mapped_column(Integer, default=1)
    login_num: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MallCate(Base):
    # 商城分类表（原PHP mall.cate）
    __tablename__ = "mall_cate"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(50), unique=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MallGoods(Base):    # 商城商品表（原PHP mall.goods）
    __tablename__ = "mall_goods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cate_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    title: Mapped[str] = mapped_column(String(100))
    price: Mapped[float] = mapped_column(default=0.0)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BotInstance(Base):
    # 机器人实例表：多token并行（上限10个），凭证入库不再依赖单文件
    __tablename__ = "bot_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), default="")
    bot_token: Mapped[str] = mapped_column(String(100), default="")
    api_id: Mapped[str] = mapped_column(String(20), default="")
    api_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PhonePrefix(Base):    # 号段表：定向生成用（实号率/推荐度为外部平台参考值，可自行维护）
    __tablename__ = "phone_prefix"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prefix: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    country: Mapped[str] = mapped_column(String(10), default="HK")
    live_rate: Mapped[int] = mapped_column(Integer, default=0)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    remark: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LangString(Base):
    # 语言文案改写表：覆盖机器人内置文案（lang/key唯一）
    __tablename__ = "lang_strings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lang: Mapped[str] = mapped_column(String(10), default="zh", index=True)
    key: Mapped[str] = mapped_column(String(100), index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    # 建表（已存在则跳过）+ 存量表补列（SQLite/MySQL 通用）
    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def _ensure_columns() -> None:
    from sqlalchemy import inspect, text
    wanted = {
        "sms_records": [("retry_count", "INTEGER DEFAULT 0"), ("error", "VARCHAR(500) DEFAULT ''"),
                        ("updated_at", "DATETIME NULL")],
    }
    try:
        existing = {t: {c["name"] for c in inspect(engine).get_columns(t)} for t in wanted}
    except Exception as e:
        logger.warning(f"表结构探测失败: {e}")
        return
    with engine.begin() as conn:
        for table, cols in wanted.items():
            for name, ddl in cols:
                if name not in existing.get(table, set()):
                    try:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                        logger.info(f"补列 {table}.{name}")
                    except Exception as e:
                        logger.warning(f"补列失败 {table}.{name}: {e}")


def get_db():
    # FastAPI 依赖：按请求提供会话
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
