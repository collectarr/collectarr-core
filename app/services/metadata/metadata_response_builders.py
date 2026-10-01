from app.services.metadata.metadata_builders_anime import AnimeMetadataResponseBuilders
from app.services.metadata.metadata_builders_tv import TVMetadataResponseBuilders


class MetadataResponseBuilders(
    AnimeMetadataResponseBuilders,
    TVMetadataResponseBuilders,
):
    """Response builders for kinds that still have real child resources."""
