# Catalog Item Image Pipeline

Core stores external image URLs in the typed Catalog Item details and uploaded
image assets in `image_assets`. Every uploaded asset references one
`catalog_item_id`; Core does not accept Work, Release, edition, variant, or
Owned Copy image identities.

## URL and Upload Paths

- `external_url`: the Catalog Item keeps the external URL and clients render it
  directly.
- `uploaded_asset`: the App uploads image bytes to the typed
  `/api/v1/images/catalog-items/{catalog_item_id}` endpoint. Core validates the
  image, normalizes it to WebP, and stores the asset in MinIO/S3.
- `missing`: the item has no image and the client may show its generated cover.

The image cache records processed external sources by URL. Cache keys and
uploads do not carry provider IDs or provenance.

Image mutation endpoints are admin-only. Catalog Items retain their own cover
URLs; uploaded assets are managed through the catalog-item image endpoints.

## Client Fallback

Flutter accepts valid `http` and `https` image URLs. Empty, malformed, blocked,
or failed loads can fall back to `LibraryGeneratedCover`.

## Local Check

1. Create a Catalog Item and upload an image through its Catalog Item image
   endpoint.
2. Confirm the response includes the same `catalog_item_id` and the object URL.
3. Confirm the asset appears in the Core admin image tools and can be removed or
   promoted.
