from fastapi import APIRouter, HTTPException, status

from app.schema.room_image import (
    RoomImageCreate,
    RoomImageUpdate,
    RoomImageResponse,
    RoomImageListResponse,
    RoomImageDeleteResponse,
    SetThumbnailRequest,
    ReorderRoomImageRequest,
)
from app.crud.room_image import (
    create_room_image,
    get_room_image_by_id,
    get_room_images_by_branch_room_id,
    get_room_images_by_room_id,
    update_room_image,
    soft_delete_room_image,
    set_thumbnail,
    reorder_room_image,
)

router = APIRouter(prefix="/room-images", tags=["Room Images"])


@router.post("/", response_model=RoomImageResponse, status_code=status.HTTP_201_CREATED)
async def create_room_image_api(payload: RoomImageCreate):
    doc = await create_room_image(payload)
    return doc


@router.get("/{image_id}", response_model=RoomImageResponse)
async def get_room_image_api(image_id: str):
    doc = await get_room_image_by_id(image_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Room image not found")
    return doc


@router.get("/branch-room/{branch_room_id}", response_model=RoomImageListResponse)
async def get_room_images_api(branch_room_id: str):
    docs = await get_room_images_by_branch_room_id(branch_room_id)
    return {"items": docs}


@router.get("/room/{room_id}", response_model=RoomImageListResponse)
async def get_room_images_by_room_api(room_id: str):
    docs = await get_room_images_by_room_id(room_id)
    return {"items": docs}


@router.put("/{image_id}", response_model=RoomImageResponse)
async def update_room_image_api(image_id: str, payload: RoomImageUpdate):
    doc = await update_room_image(image_id, payload)
    if not doc:
        raise HTTPException(status_code=404, detail="Room image not found")
    return doc


@router.patch("/{image_id}/thumbnail", response_model=RoomImageResponse)
async def set_thumbnail_api(image_id: str, payload: SetThumbnailRequest):
    doc = await set_thumbnail(image_id=image_id, updated_user=payload.updated_user)
    if not doc:
        raise HTTPException(status_code=404, detail="Room image not found")
    return doc


@router.patch("/{image_id}/reorder", response_model=RoomImageResponse)
async def reorder_room_image_api(image_id: str, payload: ReorderRoomImageRequest):
    doc = await reorder_room_image(
        image_id=image_id,
        sort_order=payload.sort_order,
        updated_user=payload.updated_user,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Room image not found")
    return doc


@router.delete("/{image_id}", response_model=RoomImageDeleteResponse)
async def delete_room_image_api(image_id: str, updated_user: str | None = None):
    success = await soft_delete_room_image(image_id=image_id, updated_user=updated_user)
    if not success:
        raise HTTPException(status_code=404, detail="Room image not found")

    return {
        "success": True,
        "message": "Room image deleted successfully",
    }