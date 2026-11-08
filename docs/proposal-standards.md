# Catalog Proposal Standards

What a good Catalog Item proposal contains, field by field, and what its cover
should look like. Reviewers apply these rules whether a proposal comes from the
App or from the ingest inbox.

The field lists follow `contracts/catalog-item-v1.json`, which covers the
released kinds: Comic, Game, Hardware, Toy and Music. Validation enforces types
and required fields only; the meanings here are the editorial standard.

## General rules

- One Catalog Item is one concrete collectible: an issue variant, a game on one
  platform and edition, one hardware model, one pressing.
- Propose facts about the product. Never propose personal data such as
  condition, grade, price paid, location, notes or serial numbers.
- Leave a field empty when it is unknown. Do not write `N/A`, `Unknown` or `-`.
- Write titles as printed, in title case, with no store text such as
  `(Brand New)` or `Free Shipping`.
- Dates are partial when that is all that is known. Never invent a day or month.
- Fields a kind does not recognize are dropped; Music refuses them instead.

## Fields shared by several kinds

| Field | Meaning |
| --- | --- |
| `title` | Required. The item's name as printed. For comics, the story or issue title if it has one, otherwise the series and number. |
| `sort_key`, `sort_title` | How the title files alphabetically, with a leading article moved: `Amazing Spider-Man, The`. Empty when the title already sorts correctly. |
| `subtitle` | Secondary title line printed under the title. |
| `original_title` | The title in the original language, for translated editions. |
| `localized_title` | The title in this edition's language when it differs from `title`. |
| `title_extension` | A qualifier that is part of the name, such as `Annual` or `Director's Cut`. |
| `search_aliases` | Other names people search for. Not for misspellings of the title. |
| `series_title` | The series or product line the item belongs to. |
| `edition_title` | The named edition: `Collector's Edition`, `Game of the Year`. |
| `publisher` | The company that published this edition. |
| `barcode` | The UPC or EAN printed on the product, digits only. Identifies the product, not your copy. |
| `catalog_number` | The publisher's own product code. |
| `release_status` | Whether the item is announced, released or cancelled. |
| `release_date`, `release_date_parts` | When the item went on sale in this edition. |
| `country` | The market this edition was sold in. |
| `language` | The language of this edition's content. |
| `age_rating`, `audience_rating` | The rating printed on the product and the rating system's audience label. |
| `genres` | Broad genres, one value each. |
| `series_tags` | Short labels that group series across publishers. |
| `physical_format` | The physical form, such as `Single Issue`, `Disc` or `Cartridge`. |
| `description` | The text shown on the details panel: a neutral summary in plain sentences. No marketing claims, spoilers or HTML other than light formatting. |
| `synopsis` | Comics and Games show this instead of `description` when both are set. Leave empty and use `description`. |
| `plot_summary`, `plot_description` | Accepted, but no details panel shows them. Leave empty. |
| `cover_image_url` | The front cover or product image. See [Covers](#covers). |
| `thumbnail_image_url` | Leave empty unless the source supplies a separate small image of the same cover. |
| `external_links` | Official or reference pages for this item. No store affiliate links. |
| `trailer_urls` | Official trailers only. |
| `identifiers` | Other published identifiers, such as an ISBN, with their system named. |

## Comic

| Field | Meaning |
| --- | --- |
| `series_title` | The series as indexed, without the volume year. |
| `volume_start_year`, `volume_name`, `volume_number` | Which run of the series. Two series with one name differ by start year. |
| `issue_number` | The number as printed, such as `1`, `1/2` or `Annual 1`. |
| `variant` | The letter or code that tells covers of one issue apart, such as `A` or `B`. |
| `variant_description` | What makes the cover different: `1:25 Incentive`, `Virgin Cover`, the artist's name. |
| `cover_date` | The date printed on the cover. Often months after the sale date. |
| `release_date_parts` | The day the issue reached stores. **Needs year, month and day to appear in the App's weekly NCBD list.** |
| `cover_price_cents`, `currency` | The printed price in minor units, with its currency. |
| `imprint` | The publisher's imprint, such as `Vertigo`. |
| `publication_age` | The collecting era, such as `Modern`. |
| `series_group` | A larger family of series. |
| `page_count` | Pages as published. |
| `crossover`, `story_arcs` | The crossover event and the story arcs the issue belongs to. |
| `creators`, `characters` | People credited with their role, and characters who appear. |
| `key_comic`, `key_reason`, `key_events` | Whether collectors treat the issue as key, and why: `First appearance of ...`. |

## Game

| Field | Meaning |
| --- | --- |
| `platforms` | The one platform this release is for. A game on two platforms is two items. |
| `release_region` | The region of this release: `NTSC-U`, `PAL`, `NTSC-J`. |
| `developers`, `publisher` | Studios that made it and the company that released this edition. |
| `company_roles`, `creators`, `contributors` | Other credited companies and people. |
| `franchise` | The wider franchise, when wider than `series_title`. |
| `item_number` | A number within a line, when printed. |
| `variant_name` | The printing or packaging variant, such as `Greatest Hits`. |
| `physical_format_label` | The format as printed, such as `Blu-ray Disc`. |
| `original_language`, `languages` | The original language, and every language the release supports. |

## Hardware

| Field | Meaning |
| --- | --- |
| `title` | The product with its variant in brackets, such as `Steam Deck [512 GB]`. Each revision is its own item. |
| `series_title` | The product family that groups revisions, when it helps. |
| `platform` | The platform the product belongs to. |
| `hardware_type` | `Console`, `Controller` or `Accessory`, or another established type. |

## Toy

| Field | Meaning |
| --- | --- |
| `toy_type` | The toy line, such as `Amiibo` or `Skylanders`. |
| `toy_subtype` | The subdivision within the line. |
| `series_title` | The series within the line, such as the wave or collection. |

## Music

| Field | Meaning |
| --- | --- |
| `title` | Required. The album as printed. |
| `artist`, `artist_credits` | The display artist, and each credited artist as structured data. Required, may be empty. |
| `credits` | Performers, producers and others, each with a role. Required, may be empty. |
| `discs` | Each disc with its format and tracks in order. Required. |
| `genres`, `extra`, `external_links` | Required, may be empty. `extra` holds release notes that fit no other field. |
| `label`, `catalog_number` | The record label and its catalog number for this pressing. |
| `packaging` | `Jewel Case`, `Digipak`, `Gatefold`. |
| `box_set` | The box set this release belongs to. |
| `release_date`, `original_release_date` | This pressing's date, and the album's first release. |
| `back_cover_image_url` | The back cover, under the same rules as the front. |

## Covers

### What to submit

- The front of the product, straight on, filling the frame.
- No watermarks, store badges, price stickers, borders or visible shelf.
- The correct variant: a variant item uses that variant's cover.
- The real proportions. Do not crop, stretch or pad to reach a ratio.
- Hardware and toys: the whole product on a plain white background. Core
  flattens transparency onto white.

### Typical proportions

A guide for spotting a wrong crop, not a requirement.

| Kind | Usual width : height |
| --- | --- |
| Comic, US standard | 0.65 |
| Game, Nintendo Switch case | 0.62 |
| Game, DVD-style case | 0.71 |
| Game, Blu-ray case | 0.79 |
| Music, CD or vinyl | 1.00 |
| Hardware, Toy | The product's own shape |

### Size

Submit the largest clean image available, with a long edge of at least 640 px
and preferably 1000 px or more. An image smaller than its display size loses
detail that compression settings cannot recover: in the measurements below, a
400 px cover shown at 560 px scored about 0.94 against 0.98 for a 560 px cover.

Core accepts up to 10 MB and 40 megapixels, then stores WebP at quality 82 with
a long edge of at most 1280 px (`IMAGE_QUALITY`, `IMAGE_MAX_LONG_EDGE`). These
apply to every kind.

### Measurements

`python -m scripts.evaluate_cover_encoding` normalizes sample covers as the image
pipeline does and compares them with the originals at display size. SSIM of 1.0
means identical; "worst 5 %" is the fifth percentile.

80 portrait covers, stored as JPEG, compared at 560 px with a 560 px long edge:

| WebP quality | Median size | Mean SSIM | Worst 5 % |
| --- | --- | --- | --- |
| 75 | 32-33 KB | 0.967-0.970 | 0.950-0.956 |
| 80 | 38-40 KB | 0.975-0.977 | 0.959-0.967 |
| 82 (current) | 42-43 KB | 0.978-0.980 | 0.963-0.970 |
| 85 | 46-48 KB | 0.982-0.984 | 0.969-0.975 |
| 90 | 59-60 KB | 0.989-0.990 | 0.981-0.985 |

Limits of this data: every sample was already JPEG and at most about 650 px long,
so sizes above 560 px, square music covers and product photos are unmeasured. The
settings stay shared until originals for each kind have been run through the
script.
