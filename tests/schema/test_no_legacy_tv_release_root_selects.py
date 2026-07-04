from pathlib import Path


def test_no_legacy_tv_release_root_selects():
    root = Path(__file__).resolve().parents[2] / "app"
    files = [
        root / "repositories" / "metadata.py",
        root / "services" / "tv_service.py",
        root / "services" / "admin_domains" / "catalog.py",
        root / "services" / "admin_domains" / "overview.py",
    ]
    banned = (
        "select(TVRelease)",
        ".where(TVRelease.id ==",
        "ItemKind.tv: TVRelease",
        "await _scan(TVRelease, ItemKind.tv",
    )
    for path in files:
        content = path.read_text(encoding="utf-8")
        assert not any(token in content for token in banned), f"legacy TV root select still in {path}"
