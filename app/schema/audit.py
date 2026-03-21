from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class AuditLogActor(BaseModel):
    user_id: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None

class AuditLogRequestContext(BaseModel):
    endpoint: Optional[str] = None
    method: Optional[str] = None

class AuditLogBusinessContext(BaseModel):
    reason: Optional[str] = None

class AuditLogResult(BaseModel):
    success: bool
    message: Optional[str] = None

class AuditLogResponse(BaseModel):
    event_id: str
    event_time: datetime
    service_name: str
    source_db: str
    source_table: str
    branch_code: Optional[str] = None
    action: str
    entity_type: str
    entity_pk: Optional[Dict[str, Any]] = None
    booking_code: Optional[str] = None
    actor: Optional[AuditLogActor] = None
    request_context: Optional[AuditLogRequestContext] = None
    business_context: Optional[AuditLogBusinessContext] = None
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    changed_fields: List[str] = []
    result: Optional[AuditLogResult] = None
    tags: List[str] = []

class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
