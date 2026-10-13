"""write phone numbers one way

Revision ID: 0005
Revises: 0004

Phone numbers were kept as their digits (« 0199001234 », « +33199001234 »: two traces for one
number); they are now in E.164. Seeds and traces already stored are rewritten, but where the new
form is already taken in the profile (then the old one stays: a scan relates them again).
"""

from collections.abc import Sequence

import phonenumbers
import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _e164(digits: str) -> str:
    # The rule of `normalize.phone_e164` on 2026-10-13, kept here as it was.
    try:
        number = phonenumbers.parse(digits, "FR")
    except phonenumbers.NumberParseException:
        return digits
    if not phonenumbers.is_possible_number(number):
        return digits
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def _rewrite(table: str) -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(f"SELECT id, profile_id, normalized FROM {table} WHERE kind = 'phone'")
    ).all()
    taken = {(profile, normalized) for _, profile, normalized in rows}
    for row_id, profile, normalized in rows:
        new = _e164(normalized)
        if new == normalized or (profile, new) in taken:
            continue
        connection.execute(
            sa.text(f"UPDATE {table} SET normalized = :new WHERE id = :id"),
            {"new": new, "id": row_id},
        )
        taken.add((profile, new))


def upgrade() -> None:
    _rewrite("seed")
    _rewrite("entity")


def downgrade() -> None:
    # The digits form is still accepted as it is: nothing to undo.
    pass
