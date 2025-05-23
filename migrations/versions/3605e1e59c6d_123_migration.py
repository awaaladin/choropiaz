"""123 migration

Revision ID: 3605e1e59c6d
Revises: c859a71497c1
Create Date: 2025-05-19 11:56:04.510347

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3605e1e59c6d'
down_revision = 'c859a71497c1'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('conversations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('conversation_participants',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('conversation_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('last_read_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('conversation_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('read_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('notification',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('recipient_id', sa.Integer(), nullable=False),
    sa.Column('sender_id', sa.Integer(), nullable=True),
    sa.Column('type', sa.String(length=20), nullable=False),
    sa.Column('message', sa.String(length=200), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=True),
    sa.Column('comment_id', sa.Integer(), nullable=True),
    sa.Column('preview_text', sa.String(length=200), nullable=True),
    sa.Column('link', sa.String(length=200), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('is_read', sa.Boolean(), nullable=True),
    sa.Column('is_seen', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['comment_id'], ['comment.id'], ),
    sa.ForeignKeyConstraint(['post_id'], ['post.id'], ),
    sa.ForeignKeyConstraint(['recipient_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['sender_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('comment', schema=None) as batch_op:
        batch_op.alter_column('content',
               existing_type=sa.TEXT(),
               type_=sa.String(length=200),
               existing_nullable=False)
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.alter_column('post_id',
               existing_type=sa.INTEGER(),
               nullable=False)

    with op.batch_alter_table('like', schema=None) as batch_op:
        batch_op.add_column(sa.Column('timestamp', sa.DateTime(), nullable=True))
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.alter_column('post_id',
               existing_type=sa.INTEGER(),
               nullable=False)

    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.alter_column('media_type',
               existing_type=sa.VARCHAR(length=10),
               type_=sa.String(length=20),
               existing_nullable=True)
        batch_op.alter_column('category',
               existing_type=sa.VARCHAR(length=8),
               nullable=True)

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('timestamp', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('notification_preferences', sa.String(length=500), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('notification_preferences')
        batch_op.drop_column('timestamp')

    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.alter_column('category',
               existing_type=sa.VARCHAR(length=8),
               nullable=False)
        batch_op.alter_column('media_type',
               existing_type=sa.String(length=20),
               type_=sa.VARCHAR(length=10),
               existing_nullable=True)

    with op.batch_alter_table('like', schema=None) as batch_op:
        batch_op.alter_column('post_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.drop_column('timestamp')

    with op.batch_alter_table('comment', schema=None) as batch_op:
        batch_op.alter_column('post_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('content',
               existing_type=sa.String(length=200),
               type_=sa.TEXT(),
               existing_nullable=False)

    op.drop_table('notification')
    op.drop_table('messages')
    op.drop_table('conversation_participants')
    op.drop_table('conversations')
    # ### end Alembic commands ###
