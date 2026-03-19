from uuid import uuid4
from datetime import datetime
from typing import Optional, List

from bson import ObjectId
from pymongo import ReturnDocument

from app.db.mongo import get_mongo_db
from app.schema.room_image import RoomImageCreate, RoomImageUpdate


COLLECTION_NAME = "room_images"


def _now_strings() -> tuple[str, str]:
    now = datetime.now()
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")


def _normalize_doc(doc: dict | None) -> dict | None:
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    return doc


async def create_room_image(data: RoomImageCreate) -> dict:
    db = get_mongo_db()
    collection = db[COLLECTION_NAME]

    created_date, created_time = _now_strings()

    if data.is_thumbnail:
        await collection.update_many(
            {
                "branch_room_id": data.branch_room_id,
                "del_flg": 0,
            },
            {
                "$set": {
                    "is_thumbnail": False,
                    "updated_date": created_date,
                    "updated_time": created_time,
                    "updated_user": data.created_user,
                }
            }
        )

    doc = {
        "_id": str(uuid4()),
        "branch_room_id": data.branch_room_id,
        "room_id": data.room_id,
        "branch_id": data.branch_id,
        "image_url": str(data.image_url),
        "is_thumbnail": data.is_thumbnail,
        "sort_order": data.sort_order,
        "created_date": created_date,
        "created_time": created_time,
        "created_user": data.created_user,
        "updated_date": created_date,
        "updated_time": created_time,
        "updated_user": data.created_user,
        "del_flg": 0,
    }

    await collection.insert_one(doc)
    return doc


async def get_room_image_by_id(image_id: str) -> dict | None:
    db = get_mongo_db()
    collection = db[COLLECTION_NAME]

    doc = await collection.find_one({"_id": image_id, "del_flg": 0})
    return _normalize_doc(doc)


async def get_room_images_by_branch_room_id(branch_room_id: str) -> List[dict]:
    db = get_mongo_db()
    collection = db[COLLECTION_NAME]

    cursor = collection.find(
        {
            "branch_room_id": branch_room_id,
            "del_flg": 0,
        }
    ).sort("sort_order", 1)

    docs = await cursor.to_list(length=None)
    return list(filter(None, [_normalize_doc(doc) for doc in docs]))


async def get_room_images_by_room_id(room_id: str) -> List[dict]:
    db = get_mongo_db()
    collection = db[COLLECTION_NAME]

    cursor = collection.find(
        {
            "room_id": room_id,
            "del_flg": 0,
        }
    ).sort("sort_order", 1)

    docs = await cursor.to_list(length=None)
    return list(filter(None, [_normalize_doc(doc) for doc in docs]))


async def update_room_image(image_id: str, data: RoomImageUpdate) -> dict | None:
    db = get_mongo_db()
    collection = db[COLLECTION_NAME]

    updated_date, updated_time = _now_strings()

    update_data = {}
    if data.image_url is not None:
        update_data["image_url"] = str(data.image_url)
    if data.is_thumbnail is not None:
        update_data["is_thumbnail"] = data.is_thumbnail
    if data.sort_order is not None:
        update_data["sort_order"] = data.sort_order

    update_data["updated_date"] = updated_date
    update_data["updated_time"] = updated_time
    update_data["updated_user"] = data.updated_user

    current_doc = await collection.find_one({"_id": image_id, "del_flg": 0})
    if not current_doc:
        return None

    if data.is_thumbnail is True:
        await collection.update_many(
            {
                "branch_room_id": current_doc["branch_room_id"],
                "del_flg": 0,
                "_id": {"$ne": image_id},
            },
            {
                "$set": {
                    "is_thumbnail": False,
                    "updated_date": updated_date,
                    "updated_time": updated_time,
                    "updated_user": data.updated_user,
                }
            }
        )

    updated_doc = await collection.find_one_and_update(
        {"_id": image_id, "del_flg": 0},
        {"$set": update_data},
        return_document=ReturnDocument.AFTER,
    )

    return _normalize_doc(updated_doc)


async def soft_delete_room_image(image_id: str, updated_user: Optional[str] = None) -> bool:
    db = get_mongo_db()
    collection = db[COLLECTION_NAME]

    updated_date, updated_time = _now_strings()

    result = await collection.update_one(
        {"_id": image_id, "del_flg": 0},
        {
            "$set": {
                "del_flg": 1,
                "updated_date": updated_date,
                "updated_time": updated_time,
                "updated_user": updated_user,
            }
        }
    )

    return result.modified_count > 0


async def set_thumbnail(image_id: str, updated_user: Optional[str] = None) -> dict | None:
    db = get_mongo_db()
    collection = db[COLLECTION_NAME]

    updated_date, updated_time = _now_strings()

    target_doc = await collection.find_one({"_id": image_id, "del_flg": 0})
    if not target_doc:
        return None

    branch_room_id = target_doc["branch_room_id"]

    await collection.update_many(
        {
            "branch_room_id": branch_room_id,
            "del_flg": 0,
        },
        {
            "$set": {
                "is_thumbnail": False,
                "updated_date": updated_date,
                "updated_time": updated_time,
                "updated_user": updated_user,
            }
        }
    )

    updated_doc = await collection.find_one_and_update(
        {"_id": image_id, "del_flg": 0},
        {
            "$set": {
                "is_thumbnail": True,
                "updated_date": updated_date,
                "updated_time": updated_time,
                "updated_user": updated_user,
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    return _normalize_doc(updated_doc)


async def reorder_room_image(
    image_id: str,
    sort_order: int,
    updated_user: Optional[str] = None
) -> dict | None:
    db = get_mongo_db()
    collection = db[COLLECTION_NAME]

    updated_date, updated_time = _now_strings()

    updated_doc = await collection.find_one_and_update(
        {"_id": image_id, "del_flg": 0},
        {
            "$set": {
                "sort_order": sort_order,
                "updated_date": updated_date,
                "updated_time": updated_time,
                "updated_user": updated_user,
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    return _normalize_doc(updated_doc)