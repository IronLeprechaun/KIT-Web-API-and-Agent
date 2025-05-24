from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add the backend directory to sys.path to find KITCore.models
# Assuming env.py is in backend/api/alembic/
# We need to go up to backend/ to find KITCore directory
_alembic_dir = os.path.dirname(os.path.abspath(__file__)) # .../backend/api/alembic
_api_dir = os.path.dirname(_alembic_dir) # .../backend/api
_backend_dir = os.path.dirname(_api_dir) # .../backend

# Add backend to sys.path to allow alembic to find KITCore.models
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# Import your models here so Alembic can see them
# This assumes your SQLAlchemy models are defined using a declarative base called 'Base'
# in KITCore/models.py (or accessible via KITCore.models)
from KITCore.models import Base 
target_metadata = Base.metadata

# --- CUSTOM IMPORTS AND CONFIGURATION FOR KITCore ---
# import os # Commented out as os is already imported
# import sys # Commented out as sys is already imported

# Adjust sys.path to allow importing from KITCore
# Assuming env.py is in KIT_Web/backend/api/alembic/
# We need to go up three levels to KIT_Web/backend/
# BACKEND_ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
# if BACKEND_ROOT_PATH not in sys.path:
# sys.path.append(BACKEND_ROOT_PATH)

# Now try to import your Base from KITCore.database_manager
# This assumes your SQLAlchemy models are defined using a declarative base called 'Base'
# in KITCore/database_manager.py or accessible through it.
# If your base is named differently or located elsewhere, this will need adjustment.
# try:
# from KITCore.database_manager import Base as KITCoreBase # Or your actual Base object
# target_metadata = KITCoreBase.metadata
# except ImportError as e:
# print(f"Could not import Base from KITCore.database_manager: {e}")
# print("Please ensure KITCore.database_manager.py defines SQLAlchemy models correctly and is in sys.path.")
# target_metadata = None # Fallback
# --- END CUSTOM IMPORTS AND CONFIGURATION ---

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
