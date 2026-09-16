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
)
from app.providers.envelope import (
    NormalizedProviderEnvelopeV1,
    ProviderAttribution,
    ProviderImageRef,
    ProviderProvenance,
)

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
    "NormalizedProviderEnvelopeV1",
    "ProviderAttribution",
    "ProviderImageRef",
    "ProviderProvenance",
]
