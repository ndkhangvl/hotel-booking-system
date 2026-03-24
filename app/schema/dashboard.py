from pydantic import BaseModel
from typing import List, Optional

class StatItem(BaseModel):
    key: str
    value: str
    change: str
    up: bool

class RecentBooking(BaseModel):
    id: str
    guest: str
    branch: Optional[str]
    checkIn: str
    checkOut: str
    amount: str
    status: str

class TopBranch(BaseModel):
    name: str
    revenue: str
    bookings: int
    fill: int

class DashboardResponse(BaseModel):
    stats: List[StatItem]
    recentBookings: List[RecentBooking]
    topBranches: List[TopBranch]
