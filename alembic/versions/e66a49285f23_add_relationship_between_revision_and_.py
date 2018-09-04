"""add relationship between revision and status event

Revision ID: e66a49285f23
Revises: 090e1bd0d7ce
Create Date: 2018-09-04 14:01:31.548665

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e66a49285f23'
down_revision = '090e1bd0d7ce'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('request_status_events', sa.Column('request_revision_id', postgresql.UUID(as_uuid=True), nullable=False))
    op.create_foreign_key(None, 'request_status_events', 'request_revisions', ['request_revision_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'request_status_events', type_='foreignkey')
    op.drop_column('request_status_events', 'request_revision_id')
    # ### end Alembic commands ###
