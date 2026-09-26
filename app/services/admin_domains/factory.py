from dataclasses import dataclass
from logging import Logger
from typing import Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.search.client import SearchClient
from app.services.admin_domains.catalog import AdminCatalogService
from app.services.admin_domains.duplicates import AdminDuplicateService
from app.services.admin_domains.image_cache import AdminImageCacheService
from app.services.admin_domains.overview import AdminOverviewService
from app.services.admin_domains.shared import character_role_rank, sort_key
from app.services.admin_domains.support import AdminSupportService
from app.services.admin_domains.users import AdminUserService


@dataclass(slots=True)
class AdminDomainServices:
    catalog_admin: AdminCatalogService
    duplicates_admin: AdminDuplicateService
    overview_admin: AdminOverviewService
    user_admin: AdminUserService
    image_cache_admin: AdminImageCacheService


def build_admin_domain_services(
    *,
    db: AsyncSession,
    actor_user_id: UUID | None,
    actor_email: str | None,
    logger: Logger,
    search_client_cls: type[SearchClient] = SearchClient,
) -> AdminDomainServices:
    support = AdminSupportService(
        db=db,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
    )
    catalog_admin = AdminCatalogService(
        db=db,
        item_response_loader=support.item_response,
        audit_recorder=support.record_admin_audit,
        reindex_items=support.reindex_items,
        sort_key_builder=sort_key,
        get_or_create_tag=support.get_or_create_tag,
    )
    duplicates_admin = AdminDuplicateService(
        db,
        support.item_response,
        support.record_admin_audit,
        character_role_rank,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
    )
    overview_admin = AdminOverviewService(
        db=db,
        search_client_cls=search_client_cls,
        duplicate_group_count=duplicates_admin.duplicate_group_count,
    )
    return AdminDomainServices(
        catalog_admin=catalog_admin,
        duplicates_admin=duplicates_admin,
        overview_admin=overview_admin,
        user_admin=AdminUserService(db, support.record_admin_audit),
        image_cache_admin=AdminImageCacheService(db, support.record_admin_audit, logger),
    )
