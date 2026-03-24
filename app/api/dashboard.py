from fastapi import APIRouter, HTTPException, Depends
from app.schema.dashboard import DashboardResponse
from app.crud.dashboard import get_dashboard_stats

router = APIRouter(prefix="/admin/dashboard", tags=["Admin - Dashboard"])

@router.get("/stats", response_model=DashboardResponse)
async def fetch_dashboard_stats():
    try:
        data = get_dashboard_stats()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy thông tin dashboard: {str(e)}")
