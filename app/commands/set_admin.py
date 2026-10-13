import argparse
import asyncio
import sys
from collections.abc import Sequence

from app.db.session import AsyncSessionLocal
from app.models.base import UserRole
from app.repositories.users import UserRepository


def _parse_role(value: str) -> UserRole:
    try:
        return UserRole(value.strip().lower())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected viewer, editor, or admin") from exc


async def set_user_role(email: str, role: UserRole) -> int:
    async with AsyncSessionLocal() as db:
        repo = UserRepository(db)
        user = await repo.get_by_email(email)
        if user is None:
            print(f"No user found for {email.lower()}", file=sys.stderr)
            return 1
        user.role = role
        await db.commit()
        print(f"{user.email} is now a {role.value}")
        return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Grant or revoke Collectarr Core admin access."
    )
    parser.add_argument("email", help="Account email to update")
    parser.add_argument(
        "role",
        type=_parse_role,
        choices=tuple(UserRole),
        help="viewer, editor, or admin",
    )
    args = parser.parse_args(argv)
    return asyncio.run(set_user_role(args.email, args.role))


if __name__ == "__main__":
    raise SystemExit(main())
