from fastapi import APIRouter, HTTPException, status, Query, Request
from typing import List
from app.schema.review import ReviewCreate, ReviewResponse
from app.crud.audit import log_audit_event, log_audit_events_bulk
from app.crud import review as crud_review
from app.crud.user import get_user_by_id
from app.crud.booking import check_user_stayed_in_room
from jose import jwt, JWTError
from app.core.security import SECRET_KEY, ALGORITHM

router = APIRouter(
    prefix="/reviews",
    tags=["Reviews"]
)

@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def submit_review(review: ReviewCreate, req: Request):
    try:
        # Get Auth token
        token = None
        auth_header = req.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        user_id = None
        user_name = review.customer.name
        user_avatar = None
        
        if token:
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                uid = payload.get("sub")
                if uid:
                    user_db = get_user_by_id(uid)
                    if user_db:
                        user_id = uid
                        user_name = user_db.get("name")
                        # assume no avatar for now or fetch if exist
            except JWTError:
                pass
                
        email = review.customer.email
        phone = review.customer.phone
        
        # Verify Booking
        booking_info_db = check_user_stayed_in_room(
            room_id=review.room_id, 
            user_id=user_id, 
            email=email, 
            phone=phone
        )
        
        if not booking_info_db:
            raise HTTPException(status_code=403, detail="Hệ thống không tìm thấy lịch sử đặt phòng với thông tin này. Bạn cần thanh toán hoặc nhận phòng trước khi đánh giá.")

        review_data = review.model_dump()
        
        # Override metadata
        review_data["branch_code"] = booking_info_db["branch_code"]
        review_data["booking_id"] = str(booking_info_db["booking_id"])
        review_data["customer"] = {
            "user_id": user_id or f"guest-{booking_info_db['booking_id']}",
            "name": user_name,
            "avatar_url": user_avatar
        }
        review_data["booking_info"]["booking_code"] = booking_info_db["booking_code"]

        inserted_id = await crud_review.create_review(review_data)
        return {"id": inserted_id, "message": "Đánh giá đã được gửi thành công"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit review: {str(e)}"
        )

@router.get("/room/{room_id}", response_model=List[ReviewResponse])
async def fetch_room_reviews(
    room_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    try:
        reviews = await crud_review.get_reviews_by_room(room_id, skip, limit)
        return reviews
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch reviews: {str(e)}"
        )

@router.post("/bulk", response_model=dict, status_code=status.HTTP_201_CREATED)
async def submit_reviews_bulk(reviews: List[ReviewCreate]):
    """
    Bulk submit reviews, primarily for automation or admin tasks.
    """
    try:
        reviews_data = []
        for r in reviews:
            rd = r.model_dump()
            # In bulk mode for automation, we assume data (ids, branch_code) is already correct
            # because automation knows the valid booking/branch info.
            reviews_data.append(rd)
            
        inserted_ids = await crud_review.create_reviews_bulk(reviews_data)
        
        # Prepare bulk audit logs
        audit_events = []
        for i, rid in enumerate(inserted_ids):
            rd = reviews_data[i]
            audit_events.append({
                "action": "CREATE_REVIEW",
                "entity_type": "review",
                "source_table": "reviews",
                "entity_pk": {"_id": rid},
                "branch_code": rd.get("branch_code"),
                "booking_id": rd.get("booking_id"),
                "booking_code": rd.get("booking_info", {}).get("booking_code"),
                "actor_id": rd.get("customer", {}).get("user_id"),
                "actor_name": rd.get("customer", {}).get("name"),
                "actor_role": "Customer (Bulk)",
                "endpoint": "POST /reviews/bulk",
                "method": "POST",
                "after": rd,
                "reason": "Khách hàng gửi đánh giá bulk (Automation)",
                "success": True,
                "message": "Đánh giá bulk đã được tạo thành công"
            })
            
        if audit_events:
            await log_audit_events_bulk(audit_events)
            
        return {
            "count": len(inserted_ids),
            "ids": inserted_ids,
            "message": f"Đã gửi thành công {len(inserted_ids)} đánh giá"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit bulk reviews: {str(e)}"
        )
