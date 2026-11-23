import os
import time
import random
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def database_configuration(environ=None):
    """Return normalized SQLAlchemy URL, connect args and whether pooled URL was selected."""
    env = os.environ if environ is None else environ
    pooled_url = env.get("DATABASE_URL_POOLED")
    direct_url = env.get("DATABASE_URL")
    selected_pooled = bool(pooled_url)
    url = pooled_url or direct_url or "sqlite:///./data/elephant_dev.db"
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    else:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        connect_args = {"connect_timeout": 10}
        # Determine pool mode from the selected environment variable, not the
        # normalized URL (which necessarily differs from Neon's raw URL).
        if selected_pooled:
            connect_args["prepare_threshold"] = None
    return url, connect_args, selected_pooled


URL, connect_args, POOLED_DATABASE_URL = database_configuration()
engine_options = {"pool_pre_ping": True, "pool_recycle": 300}
if not URL.startswith("sqlite"):
    engine_options.update(pool_size=3, max_overflow=2, pool_timeout=20)
engine = create_engine(URL, connect_args=connect_args, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ping_with_retry(attempts=5):
    from sqlalchemy import text
    last = None
    for i in range(attempts):
        try:
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            last = exc
            time.sleep(min(8, 0.4 * (2 ** i)) + random.random() * 0.2)
    raise last
