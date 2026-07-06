from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

__path__ = [str(Path(__file__).with_name("metadata"))]

if TYPE_CHECKING:
    from app.services.facade import MetadataFacade as MetadataService
else:
    MetadataService = None

__all__ = ["MetadataService"]
