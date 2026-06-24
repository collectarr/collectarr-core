# Metadata Field Schema

> Generated from `app.catalog.metadata_fields`. Re-run `python -m scripts.export_field_schema` after changing the registry.

Schema version: **1**

This is the single source of truth that the admin edit panel and the Flutter app edit dialog render from, exposed at `GET /metadata/field-schema`.

## Fields

| Key | Value type | Section | Input | Editable | Normalized | Kinds |
| --- | --- | --- | --- | --- | --- | --- |
| `physical_format_label` | string | internal | text | No | Yes | _all_ |
| `physical_format_media_family` | string | internal | text | No | Yes | _all_ |
| `physical_format_variant_type` | string | internal | text | No | Yes | _all_ |
| `associated_image_id` | string | internal | text | No | Yes | _all_ |
| `cover_delivery_url` | string | internal | text | No | Yes | _all_ |
| `cover_policy` | string | internal | text | No | Yes | _all_ |
| `cover_source_url` | string | internal | text | No | Yes | _all_ |
| `cover_status` | string | internal | text | No | Yes | _all_ |
| `cover_storage` | string | internal | text | No | Yes | _all_ |
| `audience_rating` | string | regional | text | Yes | Yes | _all_ |
| `physical_format` | string | publishing | text | Yes | Yes | _all_ |
| `genres` | string_list | relations | list | Yes | Yes | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `platforms` | string_list | relations | list | Yes | Yes | boardgame, game |
| `track_count` | integer | technical | number | Yes | Yes | music |
| `tracks` | track_list | technical | list | Yes | Yes | music |
| `color` | string | technical | text | Yes | Yes | anime, bluray, movie, tv |
| `nr_discs` | integer | technical | number | Yes | Yes | anime, bluray, movie, tv |
| `screen_ratio` | string | technical | text | Yes | Yes | anime, bluray, movie, tv |
| `audio_tracks` | string | technical | text | Yes | Yes | anime, bluray, movie, tv |
| `subtitles` | string | technical | text | Yes | Yes | anime, bluray, movie, tv |
| `layers` | string | technical | text | Yes | Yes | anime, bluray, movie, tv |
| `title` | string | item | text | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `original_title` | string | item | text | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `localized_title` | string | item | text | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `title_extension` | string | item | text | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `sort_key` | string | item | text | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `search_aliases` | string_list | item | list | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `item_number` | string | item | text | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `edition_title` | string | item | text | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `release_date` | date | item | date | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `publisher` | string | publishing | text | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `imprint` | string | publishing | text | Yes | No | book, comic, manga |
| `subtitle` | string | publishing | text | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `series_group` | string | publishing | text | Yes | No | book, comic, manga |
| `barcode` | string | publishing | text | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `variant_name` | string | publishing | text | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `page_count` | integer | publishing | number | Yes | No | book, comic, manga |
| `runtime_minutes` | integer | publishing | number | Yes | No | anime, bluray, movie, tv |
| `catalog_number` | string | technical | text | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `release_status` | string | technical | text | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `country` | string | regional | text | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `language` | string | regional | text | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `age_rating` | string | regional | text | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `series_tags` | string_list | regional | list | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `cover_image_url` | string | artwork | text | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `thumbnail_image_url` | string | artwork | text | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `synopsis` | string | artwork | multiline | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `crossover` | string | artwork | text | Yes | No | comic, manga |
| `plot_summary` | string | artwork | multiline | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `plot_description` | string | artwork | multiline | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |
| `trailer_urls` | link_list | relations | multiline | Yes | No | anime, bluray, game, movie, tv |
| `external_links` | link_list | relations | multiline | Yes | No | anime, bluray, boardgame, book, collection, comic, game, manga, movie, music, tv |

## Fields per kind

- **anime**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `audience_rating`, `physical_format`, `genres`, `color`, `nr_discs`, `screen_ratio`, `audio_tracks`, `subtitles`, `layers`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `edition_title`, `release_date`, `publisher`, `subtitle`, `barcode`, `variant_name`, `runtime_minutes`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `trailer_urls`, `external_links`
- **bluray**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `audience_rating`, `physical_format`, `genres`, `color`, `nr_discs`, `screen_ratio`, `audio_tracks`, `subtitles`, `layers`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `edition_title`, `release_date`, `publisher`, `subtitle`, `barcode`, `variant_name`, `runtime_minutes`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `trailer_urls`, `external_links`
- **boardgame**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `audience_rating`, `physical_format`, `genres`, `platforms`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `edition_title`, `release_date`, `publisher`, `subtitle`, `barcode`, `variant_name`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `external_links`
- **book**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `audience_rating`, `physical_format`, `genres`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `edition_title`, `release_date`, `publisher`, `imprint`, `subtitle`, `series_group`, `barcode`, `variant_name`, `page_count`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `external_links`
- **collection**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `audience_rating`, `physical_format`, `genres`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `edition_title`, `release_date`, `publisher`, `subtitle`, `barcode`, `variant_name`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `external_links`
- **comic**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `audience_rating`, `physical_format`, `genres`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `edition_title`, `release_date`, `publisher`, `imprint`, `subtitle`, `series_group`, `barcode`, `variant_name`, `page_count`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `crossover`, `plot_summary`, `plot_description`, `external_links`
- **game**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `audience_rating`, `physical_format`, `genres`, `platforms`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `edition_title`, `release_date`, `publisher`, `subtitle`, `barcode`, `variant_name`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `trailer_urls`, `external_links`
- **manga**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `audience_rating`, `physical_format`, `genres`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `edition_title`, `release_date`, `publisher`, `imprint`, `subtitle`, `series_group`, `barcode`, `variant_name`, `page_count`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `crossover`, `plot_summary`, `plot_description`, `external_links`
- **movie**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `audience_rating`, `physical_format`, `genres`, `color`, `nr_discs`, `screen_ratio`, `audio_tracks`, `subtitles`, `layers`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `edition_title`, `release_date`, `publisher`, `subtitle`, `barcode`, `variant_name`, `runtime_minutes`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `trailer_urls`, `external_links`
- **music**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `audience_rating`, `physical_format`, `genres`, `track_count`, `tracks`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `edition_title`, `release_date`, `publisher`, `subtitle`, `barcode`, `variant_name`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `external_links`
- **tv**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `audience_rating`, `physical_format`, `genres`, `color`, `nr_discs`, `screen_ratio`, `audio_tracks`, `subtitles`, `layers`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `edition_title`, `release_date`, `publisher`, `subtitle`, `barcode`, `variant_name`, `runtime_minutes`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `trailer_urls`, `external_links`
