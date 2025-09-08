from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import settings


class Base(DeclarativeBase):
    """Base class for all database models"""


class Character(Base):
    """Character model for storing Rick & Morty character data"""

    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    species: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(100), nullable=True)
    gender: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    origin_name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    origin_url: Mapped[str] = mapped_column(String(500), nullable=True)
    location_name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    location_url: Mapped[str] = mapped_column(String(500), nullable=True)
    image: Mapped[str] = mapped_column(String(500), nullable=True)
    episode_urls: Mapped[list] = mapped_column(JSON, nullable=True)
    url: Mapped[str] = mapped_column(String(500), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True
    )

    # Additional fields for filtering
    is_earth_human: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True
    )
    is_alive: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Table constraints and indexes
    __table_args__ = (
        # Unique constraint on URL to prevent duplicates
        UniqueConstraint("url", name="uq_character_url"),
        # Check constraints for data validation
        CheckConstraint(
            "status IN ('Alive', 'Dead', 'unknown')",
            name="ck_character_status",
        ),
        CheckConstraint(
            "gender IN ('Male', 'Female', 'Genderless', 'unknown')",
            name="ck_character_gender",
        ),
        CheckConstraint(
            "species IS NOT NULL AND species != ''",
            name="ck_character_species_not_empty",
        ),
        CheckConstraint(
            "name IS NOT NULL AND name != ''",
            name="ck_character_name_not_empty",
        ),
        # Composite indexes for common query patterns
        Index("ix_character_species_status", "species", "status"),
        Index("ix_character_origin_species", "origin_name", "species"),
        Index("ix_character_earth_alive", "is_earth_human", "is_alive"),
        Index("ix_character_name_species", "name", "species"),
        Index("ix_character_created_updated", "created_at", "updated_at"),
    )

    def __repr__(self):
        return f"<Character(id={self.id}, name='{self.name}', status='{self.status}', species='{self.species}')>"


class CacheEntry(Base):
    """Cache entry model for storing API response cache"""

    __tablename__ = "cache_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Table constraints and indexes
    __table_args__ = (
        # Check constraints for data validation
        CheckConstraint(
            "key IS NOT NULL AND key != ''", name="ck_cache_key_not_empty"
        ),
        CheckConstraint(
            "expires_at > created_at", name="ck_cache_expires_after_created"
        ),
        # Index for cleanup operations
        Index("ix_cache_expires_created", "expires_at", "created_at"),
    )

    def __repr__(self):
        return (
            f"<CacheEntry(key='{self.key}', expires_at='{self.expires_at}')>"
        )


# Database engine and session with enhanced pooling
engine = create_async_engine(
    settings.database_url_computed,
    echo=settings.db_echo,
    echo_pool=settings.db_echo_pool,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=settings.db_pool_pre_ping,
    # Additional connection pool optimizations
    pool_reset_on_return="commit",
    connect_args={
        "server_settings": {
            "application_name": "rick_morty_api",
            "jit": "off",  # Disable JIT for better connection performance
        },
        "command_timeout": 30,
    },
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections"""
    await engine.dispose()


async def get_db_health() -> dict:
    """Get database health information including connection pool stats"""
    try:
        # Test basic connectivity
        async with AsyncSessionLocal() as session:
            result = await session.execute("SELECT 1 as health_check")
            health_check = result.scalar()

        # Get connection pool statistics
        pool = engine.pool
        pool_stats = {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid(),
        }

        # Calculate pool utilization
        total_connections = pool_stats["size"] + pool_stats["overflow"]
        active_connections = pool_stats["checked_out"]
        utilization = (
            (active_connections / total_connections * 100)
            if total_connections > 0
            else 0
        )

        return {
            "status": "healthy" if health_check == 1 else "unhealthy",
            "health_check": health_check,
            "pool_stats": pool_stats,
            "pool_utilization_percent": round(utilization, 2),
            "pool_healthy": pool_stats["invalid"] == 0,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


async def cleanup_expired_cache_entries():
    """Clean up expired cache entries from the database"""
    try:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import delete

            result = await session.execute(
                delete(CacheEntry).where(
                    CacheEntry.expires_at < datetime.utcnow()
                )
            )
            await session.commit()
            return result.rowcount
    except Exception as e:
        print(f"Error cleaning up expired cache entries: {e}")
        return 0
