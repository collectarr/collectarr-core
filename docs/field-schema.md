# Metadata Field Schema

> Generated from `app.catalog.metadata_fields`. Re-run `python -m scripts.export_field_schema` after changing the registry.

Schema version: **1**

This is the single source of truth that the admin edit panel and the Flutter app edit dialog render from, exposed at `GET /api/v1/metadata/field-schema`.

## Fields

| Key | Value type | Section | Input | Editable | Kinds |
| --- | --- | --- | --- | --- | --- |
| `physical_format_label` | string | internal | text | No | game, game_hardware, game_toy, music |
| `physical_format_media_family` | string | internal | text | No | game, game_hardware, game_toy, music |
| `physical_format_variant_type` | string | internal | text | No | game, game_hardware, game_toy, music |
| `format_templateimage` | string | internal | text | No | game, game_hardware, game_toy, music |
| `format_scaledimage` | string | internal | text | No | game, game_hardware, game_toy, music |
| `country_scaledimage` | string | internal | text | No | game, game_hardware, game_toy, music |
| `language_scaledimage` | string | internal | text | No | game, game_hardware, game_toy, music |
| `audiencerating_templateimage` | string | internal | text | No | game, game_hardware, game_toy, music |
| `region_scaledimage` | string | internal | text | No | game, game_hardware, game_toy, music |
| `audio_templateimage` | string | internal | text | No | game, game_hardware, game_toy, music |
| `associated_image_id` | string | internal | text | No | game, game_hardware, game_toy, music |
| `cover_delivery_url` | string | internal | text | No | game, game_hardware, game_toy, music |
| `cover_policy` | string | internal | text | No | game, game_hardware, game_toy, music |
| `cover_source_url` | string | internal | text | No | game, game_hardware, game_toy, music |
| `cover_status` | string | internal | text | No | game, game_hardware, game_toy, music |
| `cover_storage` | string | internal | text | No | game, game_hardware, game_toy, music |
| `physical_format` | string | publishing | text | Yes | game, game_hardware, game_toy |
| `genres` | string_list | relations | list | Yes | game, game_hardware, game_toy, music |
| `creators` | object_list | item | text | Yes | game |
| `contributors` | object_list | item | text | Yes | game |
| `platforms` | string_list | relations | list | Yes | game |
| `identifiers` | string_list | relations | list | Yes | game |
| `company_roles` | string_list | relations | list | Yes | game |
| `franchise` | string | relations | text | Yes | game |
| `original_language` | string | regional | text | Yes | game |
| `languages` | string_list | regional | list | Yes | game |
| `platform` | string | item | text | Yes | game_hardware |
| `hardware_type` | string | item | text | Yes | game_hardware |
| `toy_type` | string | item | text | Yes | game_toy |
| `toy_subtype` | string | item | text | Yes | game_toy |
| `artist` | string | item | text | Yes | music |
| `sort_title` | string | item | text | Yes | music |
| `label` | string | publishing | text | Yes | music |
| `original_release_date` | partial_date | item | date | Yes | music |
| `packaging` | string | publishing | text | Yes | music |
| `extra` | string_list | technical | list | Yes | music |
| `box_set` | string | technical | text | Yes | music |
| `artist_credits` | object_list | technical | text | Yes | — |
| `credits` | object_list | technical | text | Yes | — |
| `discs` | object_list | technical | text | Yes | — |
| `title` | string | item | text | Yes | game, game_hardware, game_toy, music |
| `original_title` | string | item | text | Yes | game, game_hardware, game_toy |
| `localized_title` | string | item | text | Yes | game, game_hardware, game_toy |
| `title_extension` | string | item | text | Yes | game, game_hardware, game_toy |
| `sort_key` | string | item | text | Yes | game, game_hardware, game_toy |
| `search_aliases` | string_list | item | list | Yes | game, game_hardware, game_toy |
| `item_number` | string | item | text | Yes | game, game_hardware, game_toy |
| `series_title` | string | item | text | Yes | game, game_hardware, game_toy |
| `edition_title` | string | item | text | Yes | game, game_hardware, game_toy |
| `release_date` | partial_date | item | date | Yes | game, game_hardware, game_toy, music |
| `publisher` | string | publishing | text | Yes | game, game_hardware, game_toy |
| `subtitle` | string | publishing | text | Yes | game, game_hardware, game_toy, music |
| `barcode` | string | publishing | text | Yes | game, game_hardware, game_toy, music |
| `variant_name` | string | publishing | text | Yes | game, game_hardware, game_toy |
| `catalog_number` | string | technical | text | Yes | game, game_hardware, game_toy, music |
| `release_status` | string | technical | text | Yes | game, game_hardware, game_toy |
| `country` | string | regional | text | Yes | game, game_hardware, game_toy, music |
| `language` | string | regional | text | Yes | game, game_hardware, game_toy |
| `age_rating` | string | regional | text | Yes | game, game_hardware, game_toy |
| `audience_rating` | string | regional | text | Yes | game, game_hardware, game_toy |
| `series_tags` | string_list | regional | list | Yes | game, game_hardware, game_toy |
| `cover_image_url` | string | artwork | text | Yes | game, game_hardware, game_toy, music |
| `thumbnail_image_url` | string | artwork | text | Yes | game, game_hardware, game_toy, music |
| `synopsis` | string | artwork | multiline | Yes | game, game_hardware, game_toy |
| `plot_summary` | string | artwork | multiline | Yes | game, game_hardware, game_toy |
| `plot_description` | string | artwork | multiline | Yes | game, game_hardware, game_toy |
| `trailer_urls` | link_list | relations | multiline | Yes | game, game_hardware, game_toy |
| `external_links` | link_list | relations | multiline | Yes | game, game_hardware, game_toy, music |

## Fields per kind

- **game**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `format_templateimage`, `format_scaledimage`, `country_scaledimage`, `language_scaledimage`, `audiencerating_templateimage`, `region_scaledimage`, `audio_templateimage`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `physical_format`, `genres`, `creators`, `contributors`, `platforms`, `identifiers`, `company_roles`, `franchise`, `original_language`, `languages`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `series_title`, `edition_title`, `release_date`, `publisher`, `subtitle`, `barcode`, `variant_name`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `audience_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `trailer_urls`, `external_links`
- **game_hardware**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `format_templateimage`, `format_scaledimage`, `country_scaledimage`, `language_scaledimage`, `audiencerating_templateimage`, `region_scaledimage`, `audio_templateimage`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `physical_format`, `genres`, `platform`, `hardware_type`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `series_title`, `edition_title`, `release_date`, `publisher`, `subtitle`, `barcode`, `variant_name`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `audience_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `trailer_urls`, `external_links`
- **game_toy**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `format_templateimage`, `format_scaledimage`, `country_scaledimage`, `language_scaledimage`, `audiencerating_templateimage`, `region_scaledimage`, `audio_templateimage`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `physical_format`, `genres`, `toy_type`, `toy_subtype`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `series_title`, `edition_title`, `release_date`, `publisher`, `subtitle`, `barcode`, `variant_name`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `audience_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `trailer_urls`, `external_links`
- **music**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `format_templateimage`, `format_scaledimage`, `country_scaledimage`, `language_scaledimage`, `audiencerating_templateimage`, `region_scaledimage`, `audio_templateimage`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `genres`, `artist`, `sort_title`, `label`, `original_release_date`, `packaging`, `extra`, `box_set`, `title`, `release_date`, `subtitle`, `barcode`, `catalog_number`, `country`, `cover_image_url`, `thumbnail_image_url`, `external_links`
