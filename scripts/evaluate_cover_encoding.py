"""Compare cover sizes and WebP qualities on sample images, per kind.

Point it at a folder with one subfolder per kind holding original covers. Each
image is normalized as the image pipeline does, for every long edge the image
can fill and every quality, then compared with the original at the sizes
clients show it. Luma SSIM, 1.0 meaning identical. It only reads the samples.

    python -m scripts.evaluate_cover_encoding samples --view 300 --view 600
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from scipy.ndimage import gaussian_filter

DEFAULT_EDGES = (400, 480, 560, 640, 800, 1000, 1280, 1600)
DEFAULT_QUALITIES = (50, 60, 70, 75, 80, 82, 85, 90)
_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class Sample:
    kind: str
    edge: int
    quality: int
    view: int
    size: int
    ssim: float


def _luma(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("L"), dtype=np.float64)


def ssim(first: np.ndarray, second: np.ndarray) -> float:
    """Mean structural similarity with the usual 1.5 sigma window on 8-bit luma."""
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    mean1, mean2 = gaussian_filter(first, 1.5), gaussian_filter(second, 1.5)
    var1 = gaussian_filter(first**2, 1.5) - mean1**2
    var2 = gaussian_filter(second**2, 1.5) - mean2**2
    cov = gaussian_filter(first * second, 1.5) - mean1 * mean2
    return float(
        np.mean(
            ((2 * mean1 * mean2 + c1) * (2 * cov + c2))
            / ((mean1**2 + mean2**2 + c1) * (var1 + var2 + c2))
        )
    )


def _shown(image: Image.Image, view: int) -> Image.Image:
    """[image] with its long edge at [view], as a client scales it for display."""
    width, height = image.size
    scale = view / max(width, height)
    return image.resize(
        (max(1, round(width * scale)), max(1, round(height * scale))),
        Image.Resampling.LANCZOS,
    )


def _evaluate(job: tuple[str, Path, tuple[int, ...], tuple[int, ...], tuple[int, ...]]) -> list[Sample]:
    kind, path, edges, qualities, views = job
    with Image.open(path) as opened:
        source = ImageOps.exif_transpose(opened).convert("RGB")
    long_edge = max(source.size)
    samples = []
    references = {view: _luma(_shown(source, view)) for view in views if view <= long_edge}
    # An edge above the original's only stores the original again.
    for edge in (edge for edge in edges if edge <= long_edge):
        scaled = source.copy()
        scaled.thumbnail((edge, edge), Image.Resampling.LANCZOS)
        for quality in qualities:
            output = BytesIO()
            scaled.save(output, format="WEBP", quality=quality, method=6)
            with Image.open(BytesIO(output.getvalue())) as encoded:
                decoded = encoded.convert("RGB")
            for view, reference in references.items():
                # The exact reference size: rounding can differ by a pixel.
                shown = decoded.resize(
                    (reference.shape[1], reference.shape[0]), Image.Resampling.LANCZOS
                )
                samples.append(
                    Sample(kind, edge, quality, view, output.tell(), ssim(reference, _luma(shown)))
                )
    return samples


def _jobs(root: Path, edges, qualities, views, limit: int):
    for folder in sorted(path for path in root.iterdir() if path.is_dir()):
        paths = sorted(path for path in folder.iterdir() if path.suffix.lower() in _SUFFIXES)
        step = max(1, len(paths) // limit)
        for path in paths[::step][:limit]:
            yield folder.name, path, edges, qualities, views


def _summary(samples: list[Sample]) -> list[dict[str, object]]:
    groups: dict[tuple[str, int, int, int], list[Sample]] = defaultdict(list)
    for sample in samples:
        groups[(sample.kind, sample.view, sample.edge, sample.quality)].append(sample)
    rows = []
    for (kind, view, edge, quality), group in sorted(groups.items()):
        scores = np.array([sample.ssim for sample in group])
        rows.append(
            {
                "kind": kind,
                "view": view,
                "edge": edge,
                "quality": quality,
                "images": len(group),
                "median_kb": round(float(np.median([sample.size for sample in group])) / 1024, 1),
                "ssim_mean": round(float(scores.mean()), 4),
                "ssim_p5": round(float(np.percentile(scores, 5)), 4),
            }
        )
    return rows


def smallest_meeting(rows: list[dict[str, object]], kind: str, view: int, target: float):
    """The smallest setting whose worst 5 % still reach [target] at [view]."""
    passing = [
        row for row in rows if row["kind"] == kind and row["view"] == view and row["ssim_p5"] >= target
    ]
    return min(passing, key=lambda row: row["median_kb"], default=None)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("samples", type=Path)
    parser.add_argument("--view", type=int, action="append", dest="views")
    parser.add_argument("--limit", type=int, default=60, help="Images per kind")
    parser.add_argument("--target", type=float, default=0.98, help="SSIM the worst 5 %% must reach")
    parser.add_argument("--json", type=Path, help="Write every row to this file")
    args = parser.parse_args()
    views = tuple(args.views or (300, 600))
    jobs = list(_jobs(args.samples, DEFAULT_EDGES, DEFAULT_QUALITIES, views, args.limit))
    with ProcessPoolExecutor() as pool:
        samples = [sample for result in pool.map(_evaluate, jobs) for sample in result]
    rows = _summary(samples)
    if args.json:
        args.json.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    for kind in sorted({row["kind"] for row in rows}):
        for view in views:
            best = smallest_meeting(rows, kind, view, args.target)
            print(f"{kind} view {view}: {best if best else 'no setting reaches the target'}")


if __name__ == "__main__":
    main()
