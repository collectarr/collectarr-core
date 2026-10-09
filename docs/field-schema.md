# Metadata Field Schema

> Generated from `app.catalog.metadata_fields`. Re-run `python -m scripts.export_field_schema` after changing the registry.

Schema version: **2**

This is the single source of truth that the admin edit panel and the Flutter app edit dialog render from, exposed at `GET /api/v1/metadata/field-schema`.

## Fields

| Key | Value type | Section | Input | Editable | Kinds |
| --- | --- | --- | --- | --- | --- |
| `physical_format_label` | string | internal | text | No | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `physical_format_media_family` | string | internal | text | No | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `physical_format_variant_type` | string | internal | text | No | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `format_templateimage` | string | internal | text | No | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `format_scaledimage` | string | internal | text | No | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `country_scaledimage` | string | internal | text | No | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `language_scaledimage` | string | internal | text | No | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `audiencerating_templateimage` | string | internal | text | No | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `region_scaledimage` | string | internal | text | No | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `audio_templateimage` | string | internal | text | No | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `associated_image_id` | string | internal | text | No | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `cover_delivery_url` | string | internal | text | No | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `cover_policy` | string | internal | text | No | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `cover_source_url` | string | internal | text | No | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `cover_status` | string | internal | text | No | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `cover_storage` | string | internal | text | No | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `physical_format` | string | publishing | text | Yes | anime, boardgame, book, comic, game, manga, movie, tv |
| `genres` | string_list | relations | list | Yes | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `color` | string | technical | text | Yes | anime, movie, tv |
| `runtime_minutes` | integer | publishing | number | Yes | anime, movie, tv |
| `nr_discs` | integer | technical | number | Yes | anime, movie, tv |
| `screen_ratio` | string | technical | text | Yes | anime, movie, tv |
| `audio_tracks` | string | technical | text | Yes | anime, movie, tv |
| `subtitles` | string | technical | text | Yes | anime, movie, tv |
| `layers` | string | technical | text | Yes | anime, movie, tv |
| `platforms` | string_list | relations | list | Yes | boardgame, game |
| `identifiers` | string_list | relations | list | Yes | boardgame, game |
| `contributors` | string_list | relations | list | Yes | boardgame |
| `mechanics` | string_list | relations | list | Yes | boardgame |
| `categories` | string_list | relations | list | Yes | boardgame |
| `families` | string_list | relations | list | Yes | boardgame |
| `expansions` | string_list | relations | list | Yes | boardgame |
| `rankings` | string_list | relations | list | Yes | boardgame |
| `designers` | string_list | relations | list | Yes | boardgame |
| `artists` | string_list | relations | list | Yes | boardgame |
| `publishers` | string_list | publishing | list | Yes | boardgame |
| `themes` | string_list | relations | list | Yes | boardgame |
| `languages` | string_list | regional | list | Yes | boardgame, game |
| `characters` | string_list | relations | list | Yes | boardgame |
| `original_language` | string | regional | text | Yes | boardgame, book, game, movie |
| `expansion_for` | string | relations | text | Yes | boardgame |
| `recommended_players` | string | item | text | Yes | boardgame |
| `best_players` | string | item | text | Yes | boardgame |
| `min_playtime_minutes` | integer | item | number | Yes | boardgame |
| `max_playtime_minutes` | integer | item | number | Yes | boardgame |
| `complexity_weight` | number | item | number | Yes | boardgame |
| `bgg_rating` | number | item | number | Yes | boardgame |
| `bgg_rating_count` | integer | item | number | Yes | boardgame |
| `bgg_rank` | integer | item | number | Yes | boardgame |
| `imprint` | string | publishing | text | Yes | book, comic, manga |
| `series_group` | string | publishing | text | Yes | book, comic, manga |
| `page_count` | integer | publishing | number | Yes | book, comic, manga |
| `first_publication_date` | partial_date | publishing | date | Yes | book |
| `original_publication_date` | partial_date | publishing | date | Yes | book |
| `subjects` | string_list | relations | list | Yes | book |
| `distributor` | string | publishing | text | Yes | book |
| `region` | string | regional | text | Yes | book |
| `edition_statement` | string | publishing | text | Yes | book |
| `dimensions` | string | technical | text | Yes | book |
| `first_edition` | boolean | item | text | Yes | book |
| `audio_length_minutes` | integer | technical | number | Yes | book |
| `binding` | string | publishing | text | Yes | book |
| `back_cover_image_url` | string | artwork | text | Yes | book |
| `crossover` | string | artwork | text | Yes | comic, manga |
| `toy_subtype` | string | item | text | Yes | game |
| `toy_type` | string | item | text | Yes | game |
| `company_roles` | string_list | relations | list | Yes | game |
| `franchise` | string | relations | text | Yes | game |
| `display_title` | string | item | text | Yes | movie |
| `studio` | string | publishing | text | Yes | movie |
| `production_companies` | string_list | publishing | text | Yes | movie |
| `artist` | string | item | text | Yes | music |
| `sort_title` | string | item | text | Yes | music |
| `label` | string | publishing | text | Yes | music |
| `original_release_date` | partial_date | item | date | Yes | music |
| `packaging` | string | publishing | text | Yes | music |
| `extra` | string_list | technical | list | Yes | music |
| `box_set` | string | technical | text | Yes | music |
| `title` | string | item | text | Yes | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `original_title` | string | item | text | Yes | anime, boardgame, book, comic, game, manga, movie, tv |
| `localized_title` | string | item | text | Yes | anime, boardgame, book, comic, game, manga, movie, tv |
| `title_extension` | string | item | text | Yes | anime, boardgame, book, comic, game, manga, movie, tv |
| `sort_key` | string | item | text | Yes | anime, boardgame, book, comic, game, manga, movie, tv |
| `search_aliases` | string_list | item | list | Yes | anime, boardgame, book, comic, game, manga, movie, tv |
| `item_number` | string | item | text | Yes | anime, boardgame, book, comic, game, manga, movie, tv |
| `series_title` | string | item | text | Yes | anime, boardgame, book, comic, game, manga, movie, tv |
| `edition_title` | string | item | text | Yes | anime, boardgame, book, comic, game, manga, movie, tv |
| `release_date` | partial_date | item | date | Yes | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `publisher` | string | publishing | text | Yes | anime, boardgame, book, comic, game, manga, movie, tv |
| `subtitle` | string | publishing | text | Yes | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `barcode` | string | publishing | text | Yes | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `variant_name` | string | publishing | text | Yes | anime, boardgame, book, comic, game, manga, movie, tv |
| `catalog_number` | string | technical | text | Yes | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `release_status` | string | technical | text | Yes | anime, boardgame, book, comic, game, manga, movie, tv |
| `country` | string | regional | text | Yes | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `language` | string | regional | text | Yes | anime, boardgame, book, comic, game, manga, movie, tv |
| `age_rating` | string | regional | text | Yes | anime, boardgame, book, comic, game, manga, movie, tv |
| `audience_rating` | string | regional | text | Yes | anime, boardgame, book, comic, game, manga, movie, tv |
| `series_tags` | string_list | regional | list | Yes | anime, boardgame, book, comic, game, manga, movie, tv |
| `cover_image_url` | string | artwork | text | Yes | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `thumbnail_image_url` | string | artwork | text | Yes | anime, boardgame, book, comic, game, manga, movie, music, tv |
| `synopsis` | string | artwork | multiline | Yes | anime, boardgame, book, comic, game, manga, movie, tv |
| `plot_summary` | string | artwork | multiline | Yes | anime, boardgame, book, comic, game, manga, movie, tv |
| `plot_description` | string | artwork | multiline | Yes | anime, boardgame, book, comic, game, manga, movie, tv |
| `trailer_urls` | link_list | relations | multiline | Yes | anime, game, movie, tv |
| `external_links` | link_list | relations | multiline | Yes | anime, boardgame, book, comic, game, manga, movie, music, tv |

## Fields per kind

- **anime**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `format_templateimage`, `format_scaledimage`, `country_scaledimage`, `language_scaledimage`, `audiencerating_templateimage`, `region_scaledimage`, `audio_templateimage`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `physical_format`, `genres`, `color`, `runtime_minutes`, `nr_discs`, `screen_ratio`, `audio_tracks`, `subtitles`, `layers`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `series_title`, `edition_title`, `release_date`, `publisher`, `subtitle`, `barcode`, `variant_name`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `audience_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `trailer_urls`, `external_links`
- **boardgame**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `format_templateimage`, `format_scaledimage`, `country_scaledimage`, `language_scaledimage`, `audiencerating_templateimage`, `region_scaledimage`, `audio_templateimage`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `physical_format`, `genres`, `platforms`, `identifiers`, `contributors`, `mechanics`, `categories`, `families`, `expansions`, `rankings`, `designers`, `artists`, `publishers`, `themes`, `languages`, `characters`, `original_language`, `expansion_for`, `recommended_players`, `best_players`, `min_playtime_minutes`, `max_playtime_minutes`, `complexity_weight`, `bgg_rating`, `bgg_rating_count`, `bgg_rank`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `series_title`, `edition_title`, `release_date`, `publisher`, `subtitle`, `barcode`, `variant_name`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `audience_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `external_links`
- **book**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `format_templateimage`, `format_scaledimage`, `country_scaledimage`, `language_scaledimage`, `audiencerating_templateimage`, `region_scaledimage`, `audio_templateimage`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `physical_format`, `genres`, `original_language`, `imprint`, `series_group`, `page_count`, `first_publication_date`, `original_publication_date`, `subjects`, `distributor`, `region`, `edition_statement`, `dimensions`, `first_edition`, `audio_length_minutes`, `binding`, `back_cover_image_url`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `series_title`, `edition_title`, `release_date`, `publisher`, `subtitle`, `barcode`, `variant_name`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `audience_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `external_links`
- **comic**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `format_templateimage`, `format_scaledimage`, `country_scaledimage`, `language_scaledimage`, `audiencerating_templateimage`, `region_scaledimage`, `audio_templateimage`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `physical_format`, `genres`, `imprint`, `series_group`, `page_count`, `crossover`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `series_title`, `edition_title`, `release_date`, `publisher`, `subtitle`, `barcode`, `variant_name`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `audience_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `external_links`
- **game**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `format_templateimage`, `format_scaledimage`, `country_scaledimage`, `language_scaledimage`, `audiencerating_templateimage`, `region_scaledimage`, `audio_templateimage`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `physical_format`, `genres`, `platforms`, `identifiers`, `languages`, `original_language`, `toy_subtype`, `toy_type`, `company_roles`, `franchise`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `series_title`, `edition_title`, `release_date`, `publisher`, `subtitle`, `barcode`, `variant_name`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `audience_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `trailer_urls`, `external_links`
- **manga**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `format_templateimage`, `format_scaledimage`, `country_scaledimage`, `language_scaledimage`, `audiencerating_templateimage`, `region_scaledimage`, `audio_templateimage`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `physical_format`, `genres`, `imprint`, `series_group`, `page_count`, `crossover`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `series_title`, `edition_title`, `release_date`, `publisher`, `subtitle`, `barcode`, `variant_name`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `audience_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `external_links`
- **movie**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `format_templateimage`, `format_scaledimage`, `country_scaledimage`, `language_scaledimage`, `audiencerating_templateimage`, `region_scaledimage`, `audio_templateimage`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `physical_format`, `genres`, `color`, `runtime_minutes`, `nr_discs`, `screen_ratio`, `audio_tracks`, `subtitles`, `layers`, `original_language`, `display_title`, `studio`, `production_companies`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `series_title`, `edition_title`, `release_date`, `publisher`, `subtitle`, `barcode`, `variant_name`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `audience_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `trailer_urls`, `external_links`
- **music**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `format_templateimage`, `format_scaledimage`, `country_scaledimage`, `language_scaledimage`, `audiencerating_templateimage`, `region_scaledimage`, `audio_templateimage`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `genres`, `artist`, `sort_title`, `label`, `original_release_date`, `packaging`, `extra`, `box_set`, `title`, `release_date`, `subtitle`, `barcode`, `catalog_number`, `country`, `cover_image_url`, `thumbnail_image_url`, `external_links`
- **tv**: `physical_format_label`, `physical_format_media_family`, `physical_format_variant_type`, `format_templateimage`, `format_scaledimage`, `country_scaledimage`, `language_scaledimage`, `audiencerating_templateimage`, `region_scaledimage`, `audio_templateimage`, `associated_image_id`, `cover_delivery_url`, `cover_policy`, `cover_source_url`, `cover_status`, `cover_storage`, `physical_format`, `genres`, `color`, `runtime_minutes`, `nr_discs`, `screen_ratio`, `audio_tracks`, `subtitles`, `layers`, `title`, `original_title`, `localized_title`, `title_extension`, `sort_key`, `search_aliases`, `item_number`, `series_title`, `edition_title`, `release_date`, `publisher`, `subtitle`, `barcode`, `variant_name`, `catalog_number`, `release_status`, `country`, `language`, `age_rating`, `audience_rating`, `series_tags`, `cover_image_url`, `thumbnail_image_url`, `synopsis`, `plot_summary`, `plot_description`, `trailer_urls`, `external_links`
