from __future__ import annotations

"""Backward-compatible metadata service facade.

Prefer the split service modules under app.services.* for new code.
"""

from app.services.facade import MetadataFacade as MetadataService

__all__ = ["MetadataService"]

