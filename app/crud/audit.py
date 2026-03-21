import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from app.db.mongo import get_mongo_db

async def log_audit_event(
    action: str,
    entity_type: str = "booking",
    source_table: str = "bookings",
    entity_pk: Optional[Dict[str, Any]] = None,
    branch_code: Optional[str] = None,
    booking_id: Optional[str] = None,
    booking_code: Optional[str] = None,
    actor_id: Optional[str] = None,
    actor_name: Optional[str] = None,
    actor_role: Optional[str] = None,
    endpoint: Optional[str] = None,
    method: Optional[str] = None,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    changed_fields: Optional[List[str]] = None,
    reason: Optional[str] = None,
    success: bool = True,
    message: str = "Tác vụ thành công",
    **kwargs
):
    try:
        db = get_mongo_db()
        collection = db["audit_logs"]
        
        now = datetime.utcnow()
        expire_at = now + timedelta(days=365 * 3) # 3 years

        event_id = f"AUD-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"

        if not entity_pk:
            entity_pk = {
                "branch_code": branch_code,
                "booking_id": booking_id
            }

        log_data = {
            "event_id": event_id,
            "event_time": now,
            "service_name": "hotel-booking-api",
            "source_db": "cockroachdb",
            "source_table": source_table,
            "branch_code": branch_code,
            "action": action.upper(),
            "entity_type": entity_type,
            "entity_pk": entity_pk,
            "actor": {
                "user_id": actor_id,
                "name": actor_name,
                "role": actor_role,
            },
            "request_context": {
                "endpoint": endpoint,
                "method": method
            },
            "business_context": {
                "reason": reason
            },
            "before": before or {},
            "after": after or {},
            "changed_fields": changed_fields or [],
            "result": {
                "success": success,
                "message": message
            },
            "tags": [entity_type.lower(), action.lower(), branch_code.lower() if branch_code else "system"],
            "expire_at": expire_at
        }
        
        if booking_code:
            log_data["booking_code"] = booking_code

        # Merge other extra kwargs
        for k, v in kwargs.items():
            if v is not None:
                log_data[k] = v

        await collection.insert_one(log_data)
    except Exception as e:
        print(f"❌ Failed to write audit log: {e}")
