from fastapi import APIRouter, HTTPException, status, Form, File, UploadFile
from psycopg.rows import dict_row

from app.db.cockroach import get_connection
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
from app.core.google_drive import upload_file_to_drive

router = APIRouter(prefix="/room-images", tags=["Room Images"])


def _resolve_branch_room_id(branch_room_id: str | None, room_id: str, branch_id: str) -> str:
    if branch_room_id:
        return branch_room_id

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT branch_room_id::text AS branch_room_id
                FROM branch_rooms
                WHERE branch_id = %s
                  AND room_id = %s
                  AND del_flg = 0
                ORDER BY room_number, branch_room_id
                LIMIT 1;
                """,
                (branch_id, room_id),
            )
            branch_room = cur.fetchone()

    if not branch_room:
        raise HTTPException(status_code=400, detail="Không tìm thấy phòng chi nhánh phù hợp để gắn ảnh")

    return branch_room["branch_room_id"]


@router.post("/", response_model=RoomImageResponse, status_code=status.HTTP_201_CREATED)
async def create_room_image_api(payload: RoomImageCreate):
    doc = await create_room_image(payload)
    return doc


@router.post("/upload", response_model=RoomImageResponse, status_code=status.HTTP_201_CREATED)
async def upload_room_image_api(
    branch_room_id: str | None = Form(None),
    room_id: str = Form(...),
    branch_code: str = Form(...),
    is_thumbnail: bool = Form(False),
    sort_order: int = Form(1),
    created_user: str | None = Form(None),
    file: UploadFile = File(...),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File phải là ảnh")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File rỗng")

    image_url = upload_file_to_drive(
        file_bytes=file_bytes,
        filename=file.filename or "room-image.jpg",
        content_type=file.content_type,
    )

    resolved_branch_room_id = _resolve_branch_room_id(branch_room_id, room_id, branch_id)

    payload = RoomImageCreate(
        branch_room_id=resolved_branch_room_id,
        room_id=room_id,
        branch_code=branch_code,
        image_url=image_url,
        is_thumbnail=is_thumbnail,
        sort_order=sort_order,
        created_user=created_user,
    )

    doc = await create_room_image(payload)
    return doc


@router.get("/branch-room/{branch_room_id}", response_model=RoomImageListResponse)
async def get_room_images_api(branch_room_id: str):
    docs = await get_room_images_by_branch_room_id(branch_room_id)
    return {"items": docs}


@router.get("/room/{room_id}", response_model=RoomImageListResponse)
async def get_room_images_by_room_api(room_id: str):
    docs = await get_room_images_by_room_id(room_id)
    return {"items": docs}


@router.get("/{image_id}", response_model=RoomImageResponse)
async def get_room_image_api(image_id: str):
    doc = await get_room_image_by_id(image_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Room image not found")
    return doc


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