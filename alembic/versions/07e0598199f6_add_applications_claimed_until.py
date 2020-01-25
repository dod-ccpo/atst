"""add applications.claimed_until

Revision ID: 07e0598199f6
Revises: 26319c44a8d5
Create Date: 2020-01-25 13:33:17.711548

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '07e0598199f6' # pragma: allowlist secret
down_revision = '26319c44a8d5' # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('applications', sa.Column('claimed_until', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('applications', sa.Column('cloud_id', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('applications', 'claimed_until')
    op.drop_column('applications', 'cloud_id')
    # ### end Alembic commands ###
