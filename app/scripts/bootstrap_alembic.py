from __future__ import annotations

from pathlib import Path

from alembic.config import Config

from alembic import command


def _alembic_config() -> Config:
    repo_root = Path(__file__).resolve().parents[2]
    return Config(str(repo_root / "alembic.ini"))


def main() -> None:
    config = _alembic_config()
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
