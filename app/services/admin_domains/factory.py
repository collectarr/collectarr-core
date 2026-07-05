from dataclasses import dataclass
from logging import Logger
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.providers.comicvine import ComicVineCharacterDetail
from app.providers.registry import ProviderRegistry
from app.search.client import SearchClient
from app.services.admin_domains.catalog import AdminCatalogService
from app.services.admin_domains.duplicates import AdminDuplicateService
from app.services.admin_domains.image_cache import AdminImageCacheService
from app.services.admin_domains.overview import AdminOverviewService
from app.services.admin_domains.provider_ingest import AdminProviderIngestService
from app.services.admin_domains.rules import AdminRulesService
from app.services.admin_domains.shared import character_role_rank, sort_key
from app.services.admin_domains.support import AdminSupportService
from app.services.admin_domains.users import AdminUserService
from app.services.provider_preview_state import ProviderPreviewState
from app.services.provider_search_state import ProviderSearchState


@dataclass(slots=True)
class AdminDomainServices:
    provider_ingest_admin: AdminProviderIngestService
    rules_admin: AdminRulesService
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
    settings = get_settings()
    providers = ProviderRegistry()
    provider_preview_state = ProviderPreviewState()
    provider_search_state = ProviderSearchState(settings)
    comicvine_character_details: dict[str, ComicVineCharacterDetail | None] = {}

    support_admin = AdminSupportService(
        db=db,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
    )
    provider_ingest_admin = AdminProviderIngestService(
        db=db,
        settings=settings,
        providers=providers,
        provider_preview_state=provider_preview_state,
        history_reader=support_admin.ingest_history,
        audit_recorder=support_admin.record_admin_audit,
        ingest_job_audit_details=support_admin.ingest_job_audit_details,
        record_ingest_history=support_admin.record_ingest_history,
        is_retryable_ingest_error=support_admin.is_retryable_ingest_error,
        error_message=support_admin.error_message,
        reindex_items=support_admin.reindex_items,
        item_response_loader=support_admin.item_response,
        backoff_delay=support_admin.backoff_delay,
        actor_user_id=actor_user_id,
        comicvine_character_details=comicvine_character_details,
    )
    rules_admin = AdminRulesService(
        db=db,
        ingest_history_reader=support_admin.ingest_history,
    )
    catalog_admin = AdminCatalogService(
        db=db,
        item_response_loader=support_admin.item_response,
        audit_recorder=support_admin.record_admin_audit,
        reindex_items=support_admin.reindex_items,
        sort_key_builder=sort_key,
        get_or_create_tag=provider_ingest_admin._get_or_create_tag,
    )
    duplicates_admin = AdminDuplicateService(
        db,
        support_admin.item_response,
        support_admin.record_admin_audit,
        character_role_rank,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
    )
    overview_admin = AdminOverviewService(
        db=db,
        settings=settings,
        providers=providers,
        search_client_cls=search_client_cls,
        provider_search_state=provider_search_state,
        provider_preview_state=provider_preview_state,
        duplicate_group_count=duplicates_admin.duplicate_group_count,
        ingest_history_reader=support_admin.ingest_history,
    )
    user_admin = AdminUserService(db, support_admin.record_admin_audit)
    image_cache_admin = AdminImageCacheService(db, support_admin.record_admin_audit, logger)

    return AdminDomainServices(
        provider_ingest_admin=provider_ingest_admin,
        rules_admin=rules_admin,
        catalog_admin=catalog_admin,
        duplicates_admin=duplicates_admin,
        overview_admin=overview_admin,
        user_admin=user_admin,
        image_cache_admin=image_cache_admin,
    )