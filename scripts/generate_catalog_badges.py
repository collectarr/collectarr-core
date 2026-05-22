from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any
from urllib import error, request


KIND_SPECS = [
    ("total", "Catalog items", "catalog-total.svg", "#2f6feb"),
    ("comic", "Comics", "catalog-comic.svg", "#d73a49"),
    ("manga", "Manga", "catalog-manga.svg", "#fb8c00"),
    ("anime", "Anime", "catalog-anime.svg", "#8e44ad"),
    ("book", "Books", "catalog-book.svg", "#2da44e"),
    ("game", "Games", "catalog-game.svg", "#0f766e"),
    ("boardgame", "Board Games", "catalog-boardgame.svg", "#6f42c1"),
    ("movie", "Movies", "catalog-movie.svg", "#c2410c"),
    ("tv", "TV", "catalog-tv.svg", "#2563eb"),
    ("music", "Music", "catalog-music.svg", "#db2777"),
    ("bluray", "Blu-ray", "catalog-bluray.svg", "#1d4ed8"),
]
LEFT_COLOR = "#555"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("COLLECTARR_BADGES_BASE_URL"))
    parser.add_argument("--token", default=os.getenv("COLLECTARR_BADGES_TOKEN"))
    parser.add_argument("--email", default=os.getenv("COLLECTARR_BADGES_EMAIL"))
    parser.add_argument("--password", default=os.getenv("COLLECTARR_BADGES_PASSWORD"))
    parser.add_argument("--output-dir", default="docs/badges")
    parser.add_argument("--placeholder", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.placeholder or not args.base_url:
        payload = {
            "items": None,
            "items_by_kind": {kind: None for kind, *_ in KIND_SPECS if kind != "total"},
            "generated_at": datetime.now(UTC).isoformat(),
            "mode": "placeholder",
        }
    else:
        token = args.token or _login(args.base_url, args.email, args.password)
        payload = _fetch_summary(args.base_url, token)
        payload["generated_at"] = datetime.now(UTC).isoformat()
        payload["mode"] = "live"

    _write_manifest(output_dir / "catalog-summary.json", payload)
    _write_badges(output_dir, payload)


def _login(base_url: str, email: str | None, password: str | None) -> str:
    if not email or not password:
        raise SystemExit(
            "Provide COLLECTARR_BADGES_TOKEN or both COLLECTARR_BADGES_EMAIL and COLLECTARR_BADGES_PASSWORD."
        )
    body = json.dumps({"email": email, "password": password}).encode("utf-8")
    req = request.Request(
        _url(base_url, "/auth/login"),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    response = _request_json(req)
    token = response.get("access_token")
    if not isinstance(token, str) or not token:
        raise SystemExit("Auth login did not return an access token.")
    return token


def _fetch_summary(base_url: str, token: str) -> dict[str, Any]:
    req = request.Request(
        _url(base_url, "/admin/catalog/summary"),
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    response = _request_json(req)
    if not isinstance(response, dict):
        raise SystemExit("Catalog summary response was not a JSON object.")
    return response


def _request_json(req: request.Request) -> Any:
    try:
        with request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} for {req.full_url}: {detail}") from exc
    except error.URLError as exc:
        raise SystemExit(f"Request failed for {req.full_url}: {exc.reason}") from exc


def _url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_badges(output_dir: Path, payload: dict[str, Any]) -> None:
    total_items = payload.get("items")
    items_by_kind = payload.get("items_by_kind") or {}
    for kind, label, filename, color in KIND_SPECS:
        value = total_items if kind == "total" else items_by_kind.get(kind)
        message = "n/a" if value is None else str(value)
        svg = _badge_svg(label, message, "#9ca3af" if value is None else color)
        (output_dir / filename).write_text(svg, encoding="utf-8")


def _badge_svg(label: str, message: str, color: str) -> str:
    label_text = escape(label)
    message_text = escape(message)
    label_width = max(38, 7 * len(label) + 12)
    message_width = max(24, 7 * len(message) + 12)
    total_width = label_width + message_width
    message_x = label_width + message_width / 2
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" '
        f'role="img" aria-label="{label_text}: {message_text}">'
        f'<linearGradient id="smooth" x2="0" y2="100%">'
        '<stop offset="0" stop-color="#fff" stop-opacity=".1"/>'
        '<stop offset="1" stop-opacity=".1"/>'
        '</linearGradient>'
        f'<clipPath id="clip"><rect width="{total_width}" height="20" rx="3" fill="#fff"/></clipPath>'
        '<g clip-path="url(#clip)">'
        f'<rect width="{label_width}" height="20" fill="{LEFT_COLOR}"/>'
        f'<rect x="{label_width}" width="{message_width}" height="20" fill="{color}"/>'
        f'<rect width="{total_width}" height="20" fill="url(#smooth)"/>'
        '</g>'
        '<g fill="#fff" text-anchor="middle" '
        'font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">'
        f'<text x="{label_width / 2}" y="15" fill="#010101" fill-opacity=".3">{label_text}</text>'
        f'<text x="{label_width / 2}" y="14">{label_text}</text>'
        f'<text x="{message_x}" y="15" fill="#010101" fill-opacity=".3">{message_text}</text>'
        f'<text x="{message_x}" y="14">{message_text}</text>'
        '</g>'
        '</svg>'
    )


if __name__ == "__main__":
    main()