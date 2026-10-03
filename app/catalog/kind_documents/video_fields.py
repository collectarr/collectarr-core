"""Metadata field specifications shared by the video kinds."""

from app.catalog.metadata_field_spec import (
    INPUT_NUMBER,
    SECTION_PUBLISHING,
    SECTION_TECHNICAL,
    VALUE_TYPE_INTEGER,
    VALUE_TYPE_STRING,
    VIDEO_KINDS,
    MetadataFieldSpec,
)

FIELD_SPECS = (
    MetadataFieldSpec("color", VALUE_TYPE_STRING, "Color", typed=True,
                      normalized=True, section=SECTION_TECHNICAL,
                      kinds=VIDEO_KINDS),
    MetadataFieldSpec("runtime_minutes", VALUE_TYPE_INTEGER, "Runtime minutes",
                      section=SECTION_PUBLISHING, input=INPUT_NUMBER,
                      kinds=VIDEO_KINDS),
    MetadataFieldSpec("nr_discs", VALUE_TYPE_INTEGER, "Number of discs",
                      section=SECTION_TECHNICAL, input=INPUT_NUMBER,
                      kinds=VIDEO_KINDS),
    MetadataFieldSpec("screen_ratio", VALUE_TYPE_STRING, "Screen ratio",
                      section=SECTION_TECHNICAL, kinds=VIDEO_KINDS),
    MetadataFieldSpec("audio_tracks", VALUE_TYPE_STRING, "Audio tracks",
                      section=SECTION_TECHNICAL, kinds=VIDEO_KINDS),
    MetadataFieldSpec("subtitles", VALUE_TYPE_STRING, "Subtitles",
                      section=SECTION_TECHNICAL, kinds=VIDEO_KINDS),
    MetadataFieldSpec("layers", VALUE_TYPE_STRING, "Layers",
                      section=SECTION_TECHNICAL, kinds=VIDEO_KINDS),
)

__all__ = ["FIELD_SPECS"]
