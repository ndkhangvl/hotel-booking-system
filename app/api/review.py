from fastapi import APIRouter, HTTPException, status, Query, Request
from typing import List
from app.schema.review import ReviewCreate, ReviewResponse
from app.crud.review import create_review, get_reviews_by_room
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

        inserted_id = await create_review(review_data)
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
        reviews = await get_reviews_by_room(room_id, skip, limit)
        return reviews
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch reviews: {str(e)}"
        )
