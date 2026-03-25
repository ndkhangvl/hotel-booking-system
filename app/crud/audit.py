import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from bson import ObjectId
from app.db.mongo import get_mongo_db

def convert_objectids(obj: Any) -> Any:
    if isinstance(obj, list):
        return [convert_objectids(item) for item in obj]
    if isinstance(obj, dict):
        return {k: convert_objectids(v) for k, v in obj.items()}
    if isinstance(obj, ObjectId):
        return str(obj)
    return obj

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

async def get_audit_logs(
    branch_code: Optional[str] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    try:
        db = get_mongo_db()
        collection = db["audit_logs"]

        query = {}
        if branch_code:
            query["branch_code"] = branch_code
        if action:
            query["action"] = action.upper()
        if entity_type:
            query["entity_type"] = entity_type.lower()
            
        if start_date or end_date:
            date_filter = {}
            if start_date:
                try:
                    date_filter["$gte"] = datetime.strptime(start_date, "%Y-%m-%d")
                except ValueError:
                    pass
            if end_date:
                try:
                    # Bao gồm cả ngày end_date
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                    date_filter["$lt"] = end_dt
                except ValueError:
                    pass
            if date_filter:
                query["event_time"] = date_filter

        if keyword:
            # Tìm kiếm keyword trong message, booking_code, hoặc action
            query["$or"] = [
                {"result.message": {"$regex": keyword, "$options": "i"}},
                {"booking_code": {"$regex": keyword, "$options": "i"}},
                {"request_context.endpoint": {"$regex": keyword, "$options": "i"}},
                {"actor.name": {"$regex": keyword, "$options": "i"}},
                {"business_context.reason": {"$regex": keyword, "$options": "i"}}
            ]

        totalCount = await collection.count_documents(query)
        total_pages = (totalCount + page_size - 1) // page_size

        cursor = collection.find(query).sort("event_time", -1).skip((page - 1) * page_size).limit(page_size)
        items = []
        async for doc in cursor:
            # Convert ObjectId to str recursively
            doc = convert_objectids(doc)
            items.append(doc)

        return {
            "items": items,
            "total": totalCount,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
    except Exception as e:
        print(f"❌ Error fetching audit logs: {e}")
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

async def log_audit_events_bulk(events: List[Dict[str, Any]]):
    """
    Log multiple audit events at once for better performance.
    """
    if not events:
        return
        
    try:
        db = get_mongo_db()
        collection = db["audit_logs"]
        
        now = datetime.utcnow()
        expire_at = now + timedelta(days=365 * 3)
        
        processed_events = []
        for event in events:
            # Recompute event_id and timestamps for each if not already present
            evt_time = event.get("event_time", now)
            evt_id = event.get("event_id") or f"AUD-{evt_time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
            
            log_data = {
                "event_id": evt_id,
                "event_time": evt_time,
                "service_name": "hotel-booking-api",
                "source_db": "cockroachdb",
                "source_table": event.get("source_table", "bookings"),
                "branch_code": event.get("branch_code"),
                "action": event.get("action", "CREATE").upper(),
                "entity_type": event.get("entity_type", "booking"),
                "entity_pk": event.get("entity_pk") or {
                    "branch_code": event.get("branch_code"),
                    "booking_id": str(event.get("booking_id", ""))
                },
                "actor": {
                    "user_id": str(event.get("actor_id", "")) if event.get("actor_id") else None,
                    "name": event.get("actor_name"),
                    "role": event.get("actor_role"),
                },
                "request_context": {
                    "endpoint": event.get("endpoint"),
                    "method": event.get("method")
                },
                "business_context": {
                    "reason": event.get("reason")
                },
                "before": event.get("before") or {},
                "after": event.get("after") or {},
                "changed_fields": event.get("changed_fields") or [],
                "result": {
                    "success": event.get("success", True),
                    "message": event.get("message", "Tác vụ thành công")
                },
                "tags": [
                    event.get("entity_type", "booking").lower(),
                    event.get("action", "CREATE").lower(),
                    event.get("branch_code", "system").lower()
                ],
                "expire_at": event.get("expire_at", expire_at)
            }
            
            if "booking_code" in event:
                log_data["booking_code"] = event["booking_code"]
                
            processed_events.append(log_data)
            
        if processed_events:
            await collection.insert_many(processed_events)
    except Exception as e:
        print(f"❌ Failed to write bulk audit logs: {e}")
