# Database Optimization & Async Pooling

This document describes the comprehensive database optimizations implemented for the Rick & Morty API, including async pooling, unique constraints, indexes, and Alembic migrations.

## Overview

The database layer has been enhanced with:
- **Async Connection Pooling**: Optimized connection management with configurable pool settings
- **Unique Constraints**: Data integrity enforcement to prevent duplicates
- **Comprehensive Indexing**: Performance optimization for common query patterns
- **Alembic Migrations**: Version-controlled database schema management
- **Health Monitoring**: Connection pool metrics and database health checks

## Database Models

### Character Model

```python
class Character(Base):
    __tablename__ = "characters"
    
    # Primary fields
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    species: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    gender: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    origin_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    location_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    # Computed fields for filtering
    is_earth_human: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_alive: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
```

### Cache Entry Model

```python
class CacheEntry(Base):
    __tablename__ = "cache_entries"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
```

## Unique Constraints

### Character Table
- **`uq_character_url`**: Ensures each character URL is unique to prevent duplicates

### Cache Entry Table
- **`uq_cache_entries_key`**: Ensures each cache key is unique

## Check Constraints

### Character Table
- **`ck_character_status`**: Validates status is one of: 'Alive', 'Dead', 'unknown'
- **`ck_character_gender`**: Validates gender is one of: 'Male', 'Female', 'Genderless', 'unknown'
- **`ck_character_species_not_empty`**: Ensures species is not null or empty
- **`ck_character_name_not_empty`**: Ensures name is not null or empty

### Cache Entry Table
- **`ck_cache_key_not_empty`**: Ensures cache key is not null or empty
- **`ck_cache_expires_after_created`**: Ensures expiration is after creation time

## Indexes

### Single Column Indexes

#### Character Table
- `ix_characters_id` - Primary key index
- `ix_characters_name` - Name lookups
- `ix_characters_status` - Status filtering
- `ix_characters_species` - Species filtering
- `ix_characters_gender` - Gender filtering
- `ix_characters_origin_name` - Origin filtering
- `ix_characters_location_name` - Location filtering
- `ix_characters_is_earth_human` - Earth human filtering
- `ix_characters_is_alive` - Alive status filtering
- `ix_characters_created_at` - Creation time sorting
- `ix_characters_updated_at` - Update time sorting

#### Cache Entry Table
- `ix_cache_entries_id` - Primary key index
- `ix_cache_entries_key` - Unique cache key lookups
- `ix_cache_entries_expires_at` - Expiration time filtering
- `ix_cache_entries_created_at` - Creation time sorting

### Composite Indexes

#### Character Table
- **`ix_character_species_status`**: Optimizes queries filtering by species AND status
- **`ix_character_origin_species`**: Optimizes queries filtering by origin AND species
- **`ix_character_earth_alive`**: Optimizes Earth human + alive queries
- **`ix_character_name_species`**: Optimizes name + species lookups
- **`ix_character_created_updated`**: Optimizes time-based queries

#### Cache Entry Table
- **`ix_cache_expires_created`**: Optimizes cleanup operations by expiration and creation time

## Async Connection Pooling

### Configuration

```python
engine = create_async_engine(
    settings.database_url_computed,
    echo=settings.db_echo,
    echo_pool=settings.db_echo_pool,
    pool_size=settings.db_pool_size,           # 20 connections
    max_overflow=settings.db_max_overflow,     # 30 additional connections
    pool_timeout=settings.db_pool_timeout,     # 30 seconds
    pool_recycle=settings.db_pool_recycle,     # 1 hour
    pool_pre_ping=settings.db_pool_pre_ping,   # Connection validation
    pool_reset_on_return='commit',             # Reset connections on return
    connect_args={
        "server_settings": {
            "application_name": "rick_morty_api",
            "jit": "off",  # Disable JIT for better connection performance
        },
        "command_timeout": 30,
    }
)
```

### Pool Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `DB_POOL_SIZE` | 20 | Base number of connections in pool |
| `DB_MAX_OVERFLOW` | 30 | Additional connections when pool is exhausted |
| `DB_POOL_TIMEOUT` | 30 | Seconds to wait for connection |
| `DB_POOL_RECYCLE` | 3600 | Seconds before connection is recycled |
| `DB_POOL_PRE_PING` | true | Validate connections before use |
| `DB_ECHO` | false | Log SQL statements |
| `DB_ECHO_POOL` | false | Log connection pool events |

## Alembic Migrations

### Setup

Alembic is configured for async SQLAlchemy with:
- Async engine support
- Automatic migration generation
- Version control for database schema

### Migration Commands

```bash
# Create a new migration
python scripts/db_migrate.py revision -m "Description of changes"

# Apply migrations
python scripts/db_migrate.py upgrade head

# Rollback migration
python scripts/db_migrate.py downgrade -1

# Show current revision
python scripts/db_migrate.py current

# Show migration history
python scripts/db_migrate.py history
```

### Migration Files

- **`001_initial_migration.py`**: Initial schema with all tables, constraints, and indexes

## Database Health Monitoring

### Health Check Endpoint

The `/health` endpoint now includes comprehensive database health information:

```json
{
  "checks": {
    "database": {
      "status": "healthy",
      "health_check": 1,
      "pool_stats": {
        "size": 20,
        "checked_in": 18,
        "checked_out": 2,
        "overflow": 0,
        "invalid": 0
      },
      "pool_utilization_percent": 10.0,
      "pool_healthy": true,
      "timestamp": "2024-01-01T00:00:00.000000"
    }
  }
}
```

### Pool Metrics

- **Pool Size**: Total connections in pool
- **Checked In**: Available connections
- **Checked Out**: Active connections
- **Overflow**: Additional connections beyond pool size
- **Invalid**: Connections that failed validation
- **Utilization**: Percentage of pool in use

## Performance Optimizations

### Query Optimization

1. **Index Usage**: All common query patterns have appropriate indexes
2. **Composite Indexes**: Multi-column queries use composite indexes
3. **Boolean Indexes**: Fast filtering on computed fields
4. **Timestamp Indexes**: Efficient time-based queries

### Connection Management

1. **Connection Pooling**: Reuses connections to reduce overhead
2. **Pre-ping**: Validates connections before use
3. **Connection Recycling**: Prevents stale connections
4. **Overflow Handling**: Handles traffic spikes gracefully

### Data Integrity

1. **Unique Constraints**: Prevents duplicate data
2. **Check Constraints**: Validates data at database level
3. **Foreign Key Constraints**: Maintains referential integrity
4. **Not Null Constraints**: Ensures required fields are populated

## Monitoring & Alerting

### Key Metrics to Monitor

1. **Pool Utilization**: Should stay below 80%
2. **Connection Timeouts**: Indicates pool exhaustion
3. **Invalid Connections**: Indicates connection issues
4. **Query Performance**: Monitor slow queries
5. **Index Usage**: Ensure indexes are being used

### Recommended Alerts

```yaml
# High pool utilization
- alert: HighDatabasePoolUtilization
  expr: database_pool_utilization_percent > 80
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Database pool utilization is high"

# Connection timeouts
- alert: DatabaseConnectionTimeouts
  expr: database_connection_timeouts_total > 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Database connection timeouts detected"

# Invalid connections
- alert: DatabaseInvalidConnections
  expr: database_pool_invalid > 0
  for: 1m
  labels:
    severity: warning
  annotations:
    summary: "Database has invalid connections"
```

## Best Practices

### Development

1. **Always use migrations**: Never modify schema directly
2. **Test migrations**: Test both upgrade and downgrade paths
3. **Index new queries**: Add indexes for new query patterns
4. **Monitor performance**: Use EXPLAIN ANALYZE for slow queries

### Production

1. **Monitor pool metrics**: Keep utilization below 80%
2. **Regular maintenance**: Clean up expired cache entries
3. **Backup before migrations**: Always backup before schema changes
4. **Gradual rollouts**: Test migrations on staging first

### Security

1. **Connection encryption**: Use SSL for database connections
2. **Access control**: Limit database access to application only
3. **Audit logging**: Log all schema changes
4. **Regular updates**: Keep database drivers updated

## Troubleshooting

### Common Issues

1. **Pool Exhaustion**
   - Increase `DB_POOL_SIZE` or `DB_MAX_OVERFLOW`
   - Check for connection leaks
   - Monitor query performance

2. **Slow Queries**
   - Check if indexes are being used
   - Add missing indexes
   - Optimize query patterns

3. **Connection Timeouts**
   - Check network connectivity
   - Increase `DB_POOL_TIMEOUT`
   - Monitor database server resources

4. **Migration Failures**
   - Check database permissions
   - Verify migration dependencies
   - Test migrations on staging first

### Debug Commands

```bash
# Check current database state
python scripts/db_migrate.py current

# View migration history
python scripts/db_migrate.py history

# Test database connectivity
python -c "from app.database import get_db_health; import asyncio; print(asyncio.run(get_db_health()))"

# Check pool statistics
python -c "from app.database import engine; print(engine.pool.size(), engine.pool.checkedin(), engine.pool.checkedout())"
```

This comprehensive database optimization provides a robust, scalable, and maintainable database layer for the Rick & Morty API with enterprise-grade performance and monitoring capabilities.
