
"""Initial migration with characters and cache tables

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create characters table
    op.create_table('characters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('species', sa.String(length=100), nullable=False),
        sa.Column('type', sa.String(length=100), nullable=True),
        sa.Column('gender', sa.String(length=50), nullable=False),
        sa.Column('origin_name', sa.String(length=255), nullable=False),
        sa.Column('origin_url', sa.String(length=500), nullable=True),
        sa.Column('location_name', sa.String(length=255), nullable=False),
        sa.Column('location_url', sa.String(length=500), nullable=True),
        sa.Column('image', sa.String(length=500), nullable=True),
        sa.Column('episode_urls', sa.JSON(), nullable=True),
        sa.Column('url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_earth_human', sa.Boolean(), nullable=True),
        sa.Column('is_alive', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for characters table
    op.create_index(op.f('ix_characters_id'), 'characters', ['id'], unique=False)
    op.create_index(op.f('ix_characters_name'), 'characters', ['name'], unique=False)
    op.create_index(op.f('ix_characters_status'), 'characters', ['status'], unique=False)
    op.create_index(op.f('ix_characters_species'), 'characters', ['species'], unique=False)
    op.create_index(op.f('ix_characters_gender'), 'characters', ['gender'], unique=False)
    op.create_index(op.f('ix_characters_origin_name'), 'characters', ['origin_name'], unique=False)
    op.create_index(op.f('ix_characters_location_name'), 'characters', ['location_name'], unique=False)
    op.create_index(op.f('ix_characters_created_at'), 'characters', ['created_at'], unique=False)
    op.create_index(op.f('ix_characters_updated_at'), 'characters', ['updated_at'], unique=False)
    op.create_index(op.f('ix_characters_is_earth_human'), 'characters', ['is_earth_human'], unique=False)
    op.create_index(op.f('ix_characters_is_alive'), 'characters', ['is_alive'], unique=False)
    
    # Create composite indexes for common query patterns
    op.create_index('ix_character_species_status', 'characters', ['species', 'status'], unique=False)
    op.create_index('ix_character_origin_species', 'characters', ['origin_name', 'species'], unique=False)
    op.create_index('ix_character_earth_alive', 'characters', ['is_earth_human', 'is_alive'], unique=False)
    op.create_index('ix_character_name_species', 'characters', ['name', 'species'], unique=False)
    op.create_index('ix_character_created_updated', 'characters', ['created_at', 'updated_at'], unique=False)
    
    # Create unique constraint on URL
    op.create_unique_constraint('uq_character_url', 'characters', ['url'])
    
    # Create check constraints for data validation
    op.create_check_constraint('ck_character_status', 'characters', "status IN ('Alive', 'Dead', 'unknown')")
    op.create_check_constraint('ck_character_gender', 'characters', "gender IN ('Male', 'Female', 'Genderless', 'unknown')")
    op.create_check_constraint('ck_character_species_not_empty', 'characters', "species IS NOT NULL AND species != ''")
    op.create_check_constraint('ck_character_name_not_empty', 'characters', "name IS NOT NULL AND name != ''")
    
    # Create cache_entries table
    op.create_table('cache_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for cache_entries table
    op.create_index(op.f('ix_cache_entries_id'), 'cache_entries', ['id'], unique=False)
    op.create_index(op.f('ix_cache_entries_key'), 'cache_entries', ['key'], unique=True)
    op.create_index(op.f('ix_cache_entries_expires_at'), 'cache_entries', ['expires_at'], unique=False)
    op.create_index(op.f('ix_cache_entries_created_at'), 'cache_entries', ['created_at'], unique=False)
    
    # Create composite index for cleanup operations
    op.create_index('ix_cache_expires_created', 'cache_entries', ['expires_at', 'created_at'], unique=False)
    
    # Create unique constraint on cache key
    op.create_unique_constraint('uq_cache_entries_key', 'cache_entries', ['key'])
    
    # Create check constraints for cache validation
    op.create_check_constraint('ck_cache_key_not_empty', 'cache_entries', "key IS NOT NULL AND key != ''")
    op.create_check_constraint('ck_cache_expires_after_created', 'cache_entries', "expires_at > created_at")


def downgrade() -> None:
    # Drop cache_entries table
    op.drop_table('cache_entries')
    
    # Drop characters table
    op.drop_table('characters')
