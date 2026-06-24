# Metadata Field Schema

> Generated from `app.catalog.metadata_fields`. Re-run `python -m scripts.export_field_schema` after changing the registry.

Schema version: **1**

This is the single source of truth that the admin edit panel and the Flutter app edit dialog render from, exposed at `GET /metadata/field-schema`.

## Fields

| Key | Value type | Common | Typed column | Kinds |
| --- | --- | --- | --- | --- |
| `audience_rating` | string | Yes | Yes | _all_ |
| `physical_format` | string | Yes | No | _all_ |
| `physical_format_label` | string | Yes | No | _all_ |
| `physical_format_media_family` | string | Yes | No | _all_ |
| `physical_format_variant_type` | string | Yes | No | _all_ |
| `associated_image_id` | string | Yes | No | _all_ |
| `cover_delivery_url` | string | Yes | No | _all_ |
| `cover_policy` | string | Yes | No | _all_ |
| `cover_source_url` | string | Yes | No | _all_ |
| `cover_status` | string | Yes | No | _all_ |
| `cover_storage` | string | Yes | No | _all_ |
| `genres` | string_list | No | Yes | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `platforms` | string_list | No | Yes | boardgame, game |
| `track_count` | integer | No | Yes | music |
| `tracks` | track_list | No | Yes | music |
| `color` | string | No | Yes | anime, bluray, movie, tv |
| `nr_discs` | integer | No | Yes | anime, bluray, movie, tv |
| `screen_ratio` | string | No | Yes | anime, bluray, movie, tv |
| `audio_tracks` | string | No | Yes | anime, bluray, movie, tv |
| `subtitles` | string | No | Yes | anime, bluray, movie, tv |
| `layers` | string | No | Yes | anime, bluray, movie, tv |

## Fields per kind

- **anime**: `audience_rating`, `physical_format`, `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `genres`, `color`, `nr_discs`, `screen_ratio`, `audio_tracks`, `subtitles`, `layers`
- **bluray**: `audience_rating`, `physical_format`, `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `genres`, `color`, `nr_discs`, `screen_ratio`, `audio_tracks`, `subtitles`, `layers`
- **boardgame**: `audience_rating`, `physical_format`, `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `genres`, `platforms`
- **book**: `audience_rating`, `physical_format`, `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `genres`
- **collection**: `audience_rating`, `physical_format`, `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `genres`
- **comic**: `audience_rating`, `physical_format`, `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `genres`
- **game**: `audience_rating`, `physical_format`, `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `genres`, `platforms`
- **manga**: `audience_rating`, `physical_format`, `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `genres`
- **movie**: `audience_rating`, `physical_format`, `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `genres`, `color`, `nr_discs`, `screen_ratio`, `audio_tracks`, `subtitles`, `layers`
- **music**: `audience_rating`, `physical_format`, `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `genres`, `track_count`, `tracks`
- **tv**: `audience_rating`, `physical_format`, `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `genres`, `color`, `nr_discs`, `screen_ratio`, `audio_tracks`, `subtitles`, `layers`
