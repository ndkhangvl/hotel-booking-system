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
            # Convert ObjectId to str if needed
            doc["_id"] = str(doc["_id"])
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
