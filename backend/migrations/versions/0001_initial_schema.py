"""Create payment domain tables."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("spending_limit", sa.Numeric(12, 2), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table(
        "products",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("stock", sa.Integer, nullable=False),
    )
    op.create_index("ix_products_category", "products", ["category"])
    op.create_table(
        "purchase_intentions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("product_id", sa.String(32), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "PAID", name="intentionstatus"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_purchase_intentions_user_id", "purchase_intentions", ["user_id"])
    op.create_index("ix_purchase_intentions_session_id", "purchase_intentions", ["session_id"])
    op.create_table(
        "purchases",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "intention_id",
            sa.String(32),
            sa.ForeignKey("purchase_intentions.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_method", sa.Enum("CARD", "PIX", name="paymentmethod"), nullable=False),
        sa.Column("remaining_limit", sa.Numeric(12, 2), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "idempotency_key"),
    )
    op.create_index("ix_purchases_user_id", "purchases", ["user_id"])


def downgrade() -> None:
    op.drop_table("purchases")
    op.drop_table("purchase_intentions")
    op.drop_table("products")
    op.drop_table("users")
