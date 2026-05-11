from uuid import UUID

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.collection import CollectionAddRequest, CollectionPatchRequest, OwnedItemResponse
from app.services.collection import CollectionService

router = APIRouter(prefix="/collection", tags=["collection"])


@router.post("/add", response_model=OwnedItemResponse, status_code=201)
async def add_collection_item(
    payload: CollectionAddRequest, db: DbSession, user: CurrentUser
) -> OwnedItemResponse:
    return await CollectionService(db).add_owned(user, payload)


@router.get("", response_model=list[OwnedItemResponse])
async def list_collection(db: DbSession, user: CurrentUser) -> list[OwnedItemResponse]:
    return await CollectionService(db).list_owned(user)


@router.patch("/{owned_item_id}", response_model=OwnedItemResponse)
async def patch_collection_item(
    owned_item_id: UUID, payload: CollectionPatchRequest, db: DbSession, user: CurrentUser
) -> OwnedItemResponse:
    return await CollectionService(db).patch_owned(user, owned_item_id, payload)


@router.delete("/{owned_item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection_item(owned_item_id: UUID, db: DbSession, user: CurrentUser) -> Response:
    await CollectionService(db).delete_owned(user, owned_item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

