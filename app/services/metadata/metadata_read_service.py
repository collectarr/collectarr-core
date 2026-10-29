from __future__ import annotations

from app.services.metadata.metadata_common_support import MetadataCommonSupport
from app.services.metadata.metadata_response_builders import MetadataResponseBuilders


class MetadataReadService(
    MetadataCommonSupport,
    MetadataResponseBuilders,
):
    """Composed typed read surface mixed directly into MetadataFacade."""
