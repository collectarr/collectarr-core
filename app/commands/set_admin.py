import argparse
import asyncio
import sys
from collections.abc import Sequence

from app.db.session import AsyncSessionLocal
from app.models.base import UserRole
from app.repositories.users import UserRepository


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on", "admin"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", "user"}:
        return False
    raise argparse.ArgumentTypeError(
        "expected one of true/false, yes/no, 1/0, admin/user"
    )


async def set_admin_status(email: str, is_admin: bool) -> int:
    async with AsyncSessionLocal() as db:
        repo = UserRepository(db)
        user = await repo.get_by_email(email)
        if user is None:
            print(f"No user found for {email.lower()}", file=sys.stderr)
            return 1
        user.is_admin = is_admin
        user.role = UserRole.admin if is_admin else UserRole.viewer
        await db.commit()
        role = "admin" if is_admin else "standard user"
        print(f"{user.email} is now a {role}")
        return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Grant or revoke Collectarr Core admin access."
    )
    parser.add_argument("email", help="Account email to update")
    parser.add_argument(
        "is_admin",
        type=_parse_bool,
        help="true/false, yes/no, 1/0, admin/user",
    )
    args = parser.parse_args(argv)
    return asyncio.run(set_admin_status(args.email, args.is_admin))


if __name__ == "__main__":
    raise SystemExit(main())
