from contextlib import contextmanager
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

def _build_database_url() -> str:
    # Prefer full DATABASE_URL (kèm ?sslmode=require từ Neon)
    url = os.getenv("DATABASE_URL")
    if url:
        # Cho phép cả postgresql:// và postgresql+psycopg2://
        return url
    # Fallback từ từng biến (nếu cần)
    user = os.getenv("DB_USER", "postgres")
    pwd = os.getenv("DB_PASSWORD", "postgres")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "medly")
    sslmode = os.getenv("DB_SSLMODE")  # ví dụ: require
    base = f"postgresql+psycopg2://{user}:{quote_plus(pwd)}@{host}:{port}/{name}"
    return f"{base}?sslmode={sslmode}" if sslmode else base

DATABASE_URL = _build_database_url()

# Neon + Pooler: giữ pool nhỏ và pre_ping
engine = create_engine(
    DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://"),
    pool_pre_ping=True,
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "5")),
    pool_recycle=1800,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

@contextmanager
def get_session():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
