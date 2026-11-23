from logging.config import fileConfig
import os
from alembic import context
from sqlalchemy import engine_from_config, pool
from app.db import Base
from app import models

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
url = os.getenv("DATABASE_URL_DIRECT") or os.getenv("DATABASE_URL")
if url:
    url = url.replace("postgres://", "postgresql+psycopg://", 1).replace("postgresql://", "postgresql+psycopg://", 1)
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"}, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    section = config.get_section(config.config_ini_section)
    db_url = section.get("sqlalchemy.url", "")
    connect_args = {} if db_url.startswith("sqlite") else {"connect_timeout": 10}
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool,
                                     connect_args=connect_args)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
