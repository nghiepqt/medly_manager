import os
import sys
from pathlib import Path
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool

# Thêm project root (chứa thư mục 'backend') vào sys.path
root = Path(__file__).resolve().parents[2]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

# Alembic config
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

def _compose_url_from_env() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    user = os.getenv("DB_USER", "postgres")
    pwd = os.getenv("DB_PASSWORD", "postgres")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "medly")
    ssl = os.getenv("DB_SSLMODE")
    base = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{name}"
    return f"{base}?sslmode={ssl}" if ssl else base

_db_url = _compose_url_from_env()
config.set_main_option("DATABASE_URL", _db_url)
config.set_main_option("sqlalchemy.url", _db_url)

# Import models để có metadata
from backend.models import Base  # type: ignore
target_metadata = Base.metadata

def get_url() -> str:
    # dùng giá trị đã tiêm ở trên
    return _db_url

def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

