# Music Album Catalog Contract v1

> This describes the earlier Music-only API slice. It is transitional under
> the all-kind [Catalog Item v1 cutover](catalog-item-v1-cutover.md), which
> will make Music one typed Catalog Item kind rather than a separate contract
> root.

The Music catalog API is based on `MusicAlbumV1`, exported from the Pydantic
schemas in `app/schemas/metadata_music.py` to
`contracts/music-catalog-v1.json`. One album is one catalog edition. Two
editions with the same title remain separate album records.

An album contains its artist and label credits, CLZ-style catalog fields,
external links, disc titles, and ordered tracks. A disc title is keyed by its
one-based disc number inside the album; a disc has no independent identity. A
track is keyed by `(album_id, disc_number, position)` and has a required
position. Partial dates retain year, month, and day precision in the API.

Core writes accept canonical album data only. Provider search, credentials,
mapping, source IDs, import history, snapshots, and provenance belong to
`collectarr-app`; none are part of the Core request or response. Owned copies,
tracking, listening history, local images, and personal fields also stay in the
App. `OwnedCopyV1` is an App-owned contract and is not included in Core's bundle.

`metadata-field-schema.json` describes editable field ownership for the shared
forms. It does not replace the nested album contract. App pins
`music-catalog-v1.json` and generates its Dart transport DTO from that artifact.

## Fresh database baseline

Core's final catalog schema is created on a fresh PostgreSQL database from the
SQLAlchemy models. App's final local schema is Drift v1. Existing databases,
backups, and search indexes from the previous Music graph are incompatible with
this baseline. Stop both apps, keep old backups only for archival recovery,
create empty databases, and rebuild the search index from the new catalog.
`create_all()` creates missing tables; it does not reshape or remove old ones.

## Contract export

Run `python -m scripts.export_contract_bundle` from the Core repository after
changing the schemas. CI checks the checked-in JSON against the generated
OpenAPI, album, field-schema, and active-kind artifacts and their manifest
hashes. The exported contract version is `1.0.0`.
