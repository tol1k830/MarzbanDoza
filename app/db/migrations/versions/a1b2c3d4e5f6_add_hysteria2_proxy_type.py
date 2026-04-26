"""add hysteria2 proxy type

Revision ID: a1b2c3d4e5f6
Revises: 2b231de97dc3
Create Date: 2025-04-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '2b231de97dc3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'sqlite':
        # SQLite doesn't support ALTER COLUMN for enums — the column is stored
        # as VARCHAR so no DDL change is needed; the new value is accepted as-is.
        pass

    elif dialect in ('mysql', 'mariadb'):
        op.execute(
            "ALTER TABLE proxies MODIFY COLUMN type "
            "ENUM('VMess','VLESS','Trojan','Shadowsocks','Hysteria2') NOT NULL"
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'sqlite':
        pass

    elif dialect in ('mysql', 'mariadb'):
        # Remove any hysteria2 proxies before downgrading the enum
        op.execute("DELETE FROM proxies WHERE type = 'Hysteria2'")
        op.execute(
            "ALTER TABLE proxies MODIFY COLUMN type "
            "ENUM('VMess','VLESS','Trojan','Shadowsocks') NOT NULL"
        )
