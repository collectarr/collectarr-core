from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminAuditLog, AdminAuditLogDetail
from app.services.typed_values import flatten_typed_values


class AdminSupportService:
    def __init__(
        self,
        *,
        db: AsyncSession,
        actor_user_id: UUID | None,
        actor_email: str | None,
    ) -> None:
        self.db = db
        self.actor_user_id = actor_user_id
        self.actor_email = actor_email

    def record_admin_audit(
        self,
        action: str,
        entity_type: str,
        entity_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        audit_log = AdminAuditLog(
            action=action,
            actor_user_id=self.actor_user_id,
            actor_email=self.actor_email,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        audit_log.details = [
            AdminAuditLogDetail(**row) for row in flatten_typed_values(details or {})
        ]
        self.db.add(audit_log)
