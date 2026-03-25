from datetime import datetime
from typing import Optional, Dict, Any, List
from bson import ObjectId
from app.db.mongo import get_mongo_db
from app.crud.audit import log_audit_event

async def create_review(review_data: dict) -> str:
    db = get_mongo_db()
    collection = db["reviews"]
    
    now = datetime.utcnow()
    review_data["created_at"] = now
    review_data["updated_at"] = now
    review_data["status"] = "published"
    
    result = await collection.insert_one(review_data)
    inserted_id = str(result.inserted_id)
    
    # Audit log
    try:
        actor_id = review_data.get("customer", {}).get("user_id")
        actor_name = review_data.get("customer", {}).get("name")
        actor_role = "Customer"
            
        await log_audit_event(
            action="CREATE_REVIEW",
            entity_type="review",
            source_table="reviews",
            entity_pk={"_id": inserted_id},
            branch_code=review_data.get("branch_code"),
            booking_id=review_data.get("booking_id"),
            booking_code=review_data.get("booking_info", {}).get("booking_code"),
            actor_id=actor_id,
            actor_name=actor_name,
            actor_role=actor_role,
            endpoint="POST /reviews/",
            method="POST",
            after=review_data,
            reason="Khách hàng gửi đánh giá mới",
            success=True,
            message="Đánh giá đã được tạo thành công"
        )
    except Exception as e:
        print(f"Failed to write audit log for CREATE_REVIEW: {e}")
        
    return inserted_id

async def get_reviews_by_room(room_id: str, skip: int = 0, limit: int = 20) -> List[Dict[str, Any]]:
    db = get_mongo_db()
    collection = db["reviews"]
    
    query = {"room_id": room_id, "status": "published"}
    cursor = collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
    
    reviews = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        reviews.append(doc)
        
    # Audit log for viewing reviews
    try:
        await log_audit_event(
            action="VIEW_REVIEWS",
            entity_type="review",
            source_table="reviews",
            entity_pk={"room_id": room_id},
            actor_name="Guest/User",
            actor_role="Viewer",
            endpoint=f"GET /reviews/room/{room_id}",
            method="GET",
            reason="Người dùng xem đánh giá phòng",
            success=True,
            message=f"Lấy {len(reviews)} đánh giá",
            tags=["review", "view_reviews", "system"]
        )
    except Exception as e:
        print(f"Failed to write audit log for VIEW_REVIEWS: {e}")
        
    return reviews


async def create_reviews_bulk(reviews_list: List[dict]) -> List[str]:
    """
    Bulk create reviews in MongoDB for high performance.
    """
    if not reviews_list:
        return []

    db = get_mongo_db()
    collection = db["reviews"]
    
    now = datetime.utcnow()
    for review in reviews_list:
        review["created_at"] = now
        review["updated_at"] = now
        review["status"] = "published"
        
    result = await collection.insert_many(reviews_list)
    inserted_ids = [str(sid) for sid in result.inserted_ids]
    
    return inserted_ids
