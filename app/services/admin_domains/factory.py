from dataclasses import dataclass
from logging import Logger
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.search.client import SearchClient
from app.services.admin_domains.duplicates import AdminDuplicateService
from app.services.admin_domains.image_cache import AdminImageCacheService
from app.services.admin_domains.overview import AdminOverviewService
from app.services.admin_domains.support import AdminSupportService
from app.services.admin_domains.users import AdminUserService


@dataclass(slots=True)
class AdminDomainServices:
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
    duplicates_admin = AdminDuplicateService(
        db,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
    )
    overview_admin = AdminOverviewService(
        db=db,
        search_client_cls=search_client_cls,
        duplicate_group_count=duplicates_admin.duplicate_group_count,
    )
    return AdminDomainServices(
        duplicates_admin=duplicates_admin,
        overview_admin=overview_admin,
        user_admin=AdminUserService(db, support.record_admin_audit),
        image_cache_admin=AdminImageCacheService(db, support.record_admin_audit, logger),
    )
