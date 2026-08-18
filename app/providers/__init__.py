"""Metadata provider models and envelopes."""

from app.providers.base import (
    NormalizedBundleMember,
    NormalizedBundleRelease,
    NormalizedCredit,
    NormalizedEpisode,
    NormalizedItem,
    NormalizedRelation,
    NormalizedSeason,
    NormalizedTrack,
    NormalizedVariantCover,
    ProviderCapabilities,
    ProviderItem,
    ProviderSearchResult,
)
from app.providers.envelope import (
    NormalizedProviderEnvelopeV1,
    ProviderAttribution,
    ProviderImageRef,
    ProviderProvenance,
)
from app.providers.registry import ProviderRegistry, ProviderRegistryStatus

__all__ = [
    "NormalizedBundleMember",
    "NormalizedBundleRelease",
    "NormalizedCredit",
    "NormalizedEpisode",
    "NormalizedItem",
    "NormalizedRelation",
    "NormalizedSeason",
    "NormalizedTrack",
    "NormalizedVariantCover",
    "ProviderCapabilities",
    "ProviderItem",
    "ProviderSearchResult",
    "NormalizedProviderEnvelopeV1",
    "ProviderAttribution",
    "ProviderImageRef",
    "ProviderProvenance",
    "ProviderRegistry",
    "ProviderRegistryStatus",
]
