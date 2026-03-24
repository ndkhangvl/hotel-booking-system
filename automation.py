import asyncio
import aiohttp
import random
import string
import uuid
from datetime import date, timedelta

BASE_URL = "http://localhost:8000"

def generate_random_string(length=8):
    letters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(letters) for _ in range(length))

def generate_random_phone():
    return f"09{random.randint(10000000, 99999999)}"

async def fetch_branches(session):
    url = f"{BASE_URL}/admin/branches/branches-list?page=1&page_size=100"
    async with session.get(url) as response:
        if response.status == 200:
            data = await response.json()
            return data.get("items", [])
        return []

async def fetch_branch_rooms_for_branch(session, branch_code):
    url = f"{BASE_URL}/admin/rooms/branch-rooms-list?branch_code={branch_code}&page=1&page_size=100"
    async with session.get(url) as response:
        if response.status == 200:
            data = await response.json()
            return data.get("items", [])
        return []

async def create_user(session, sem, i):
    url = f"{BASE_URL}/users/register"
    payload = {
        "name": f"Auto Customer {i}",
        "email": f"autouser_{i}_{generate_random_string(4)}@example.com",
        "phone": generate_random_phone(),
        "role": "Customer",
        "password": "hashed_password_dummy"
    }
    async with sem:
        try:
            async with session.post(url, json=payload) as response:
                if response.status in (200, 201):
                    data = await response.json()
                    return data.get("user_id")
                return None
        except Exception:
            return None

async def create_booking(session, sem, i, available_rooms, user_ids):
    # Dùng Booking Admin để dễ đặt status = Completed
    url = f"{BASE_URL}/Admin/bookings/"
    
    room = random.choice(available_rooms)
    user_id = random.choice(user_ids) if user_ids else None
    
    branch_code = room.get("branch_code")
    branch_room_id = room.get("branch_room_id")
    room_id = room.get("room_id")
    
    start_offset = random.randint(1, 30)
    duration = random.randint(1, 5)
    from_date = date.today() - timedelta(days=start_offset + duration)
    to_date = from_date + timedelta(days=duration)
    
    customer_name = f"Customer {i}"
    customer_email = f"customer_{i}@test.com"
    customer_phonenumber = generate_random_phone()
    
    payload = {
        "user_id": user_id,
        "branch_code": branch_code,
        "branch_room_id": branch_room_id,
        "room_id": room_id,
        "voucher_code": "WELCOME2026" if random.choice([True, False]) else None,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phonenumber": customer_phonenumber,
        "note": "Auto generated historical booking",
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "total_price": round(random.uniform(500000, 5000000), 2),
        "status": "Completed",  # Important for passing review validation
        "payment_status": "paid"
    }
    
    async with sem:
        try:
            async with session.post(url, json=payload) as response:
                if response.status in (200, 201):
                    data = await response.json()
                    # Keep info for the review stage
                    return {
                        "booking_id": data.get("booking_id"),
                        "booking_code": data.get("booking_code"),
                        "branch_code": branch_code,
                        "room_id": room_id,
                        "user_id": user_id,
                        "customer_name": customer_name,
                        "customer_email": customer_email,
                        "customer_phonenumber": customer_phonenumber,
                        "check_in_date": f"{from_date.isoformat()}T14:00:00Z",
                        "check_out_date": f"{to_date.isoformat()}T12:00:00Z",
                        "total_nights": duration,
                        "traveler_type": random.choice(["Gia đình", "Cặp đôi", "Công tác", "Cá nhân"])
                    }
                else:
                    return None
        except Exception:
            return None

async def create_review(session, sem, booking_info):
    url = f"{BASE_URL}/reviews/"
    
    overall = random.randint(3, 5)
    
    comments = {
        3: ["Khách sạn tạm ổn, hơi ồn", "Phòng cũng được nhưng dịch vụ chưa tốt", "Phòng sạch sẽ cơ bản, không có gì nổi bật"],
        4: ["Khách sạn tốt, giá hợp lý", "Nhân viên thân thiện, vị trí đẹp", "Chất lượng khá so với tầm giá"],
        5: ["Tuyệt vời, sẽ quay lại lần sau", "Trải nghiệm vượt sức mong đợi", "Combo dịch vụ quá xịn xò, phòng cực đẹp"]
    }
    
    payload = {
        "branch_code": booking_info["branch_code"],
        "booking_id": booking_info["booking_id"],
        "room_id": booking_info["room_id"],
        "customer": {
            "user_id": booking_info["user_id"],
            "name": booking_info["customer_name"],
            "email": booking_info["customer_email"],
            "phone": booking_info["customer_phonenumber"],
            "avatar_url": None
        },
        "booking_info": {
            "booking_code": booking_info["booking_code"],
            "room_type_name": "Standard Room", # Dummy since it doesn't do strict validation for this yet
            "room_number": "101",
            "check_in_date": booking_info["check_in_date"],
            "check_out_date": booking_info["check_out_date"],
            "total_nights": booking_info["total_nights"],
            "traveler_type": booking_info["traveler_type"]
        },
        "rating": {
            "overall": overall,
            "cleanliness": random.randint(max(3, overall-1), 5),
            "service": random.randint(max(3, overall-1), 5),
            "location": random.randint(max(3, overall-1), 5)
        },
        "comment": random.choice(comments[overall]),
        "attached_images": []
    }
    
    async with sem:
        try:
            async with session.post(url, json=payload) as response:
                if response.status in (200, 201):
                    return True
                else:
                    return False
        except Exception:
            return False

async def main():
    # Sử dụng semaphore lớn hơn do tạo số lượng rất khủng, nhưng cần cân bằng với khả năng của máy và FastAPI
    # Sẽ chia chunks nhỏ hơn trong runtime để khỏi bị socket exhaustion
    sem = asyncio.Semaphore(150)
    
    timeout = aiohttp.ClientTimeout(total=None, connect=60, sock_read=60)
    connector = aiohttp.TCPConnector(limit=150)
    
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        print("1. Đang lấy danh sách các chi nhánh và phòng...")
        branches = await fetch_branches(session)
        if not branches:
            print("❌ Không tìm thấy chi nhánh nào.")
            return
        
        available_rooms = []
        for branch in branches:
            b_code = branch.get("branch_code")
            b_rooms = await fetch_branch_rooms_for_branch(session, b_code)
            available_rooms.extend(b_rooms)
            
        if not available_rooms:
            print("❌ Không tìm thấy phòng hợp lệ.")
            return
            
        print(f"✅ Bắt đầu tạo dữ liệu...")
        
        # 1. Tạo 10,000 Users
        num_users = 10000
        print(f"\n[1/3] Đang tạo {num_users} users qua API (/users/register)...")
        tasks_users = [create_user(session, sem, i) for i in range(num_users)]
        
        created_user_ids = []
        # Chạy chunk cỡ 1000 để hạn chế nổ Ram / Connection drop
        for i in range(0, len(tasks_users), 1000):
            batch = tasks_users[i:i+1000]
            results = await asyncio.gather(*batch)
            valid_ids = [uid for uid in results if uid]
            created_user_ids.extend(valid_ids)
            print(f"   Đã tạo {len(created_user_ids)}/{num_users} users...")
            
        print(f"✅ Hoàn thành tạo {len(created_user_ids)} users.")

        # 2. Tạo 200,000 Bookings (Trạng thái Completed, ngày quá khứ)
        num_bookings = 200000
        print(f"\n[2/3] Đang tạo {num_bookings} bookings dạng Completed qua API Admin (/Admin/bookings/)...")
        
        # Do 200000 là số lượng cực lớn, tạo task dần và chạy theo chunk
        # Thay vì build list 200,000 tasks list gây tốn bộ nhớ:
        successful_bookings_info = []
        
        chunk_size = 5000 # mỗi step chạy 5000
        for current_count in range(0, num_bookings, chunk_size):
            actual_chunk = min(chunk_size, num_bookings - current_count)
            tasks_bookings = [create_booking(session, sem, current_count + j, available_rooms, created_user_ids) for j in range(actual_chunk)]
            results = await asyncio.gather(*tasks_bookings)
            
            valid_bookings = [r for r in results if r is not None]
            successful_bookings_info.extend(valid_bookings)
            print(f"   Đã xử lý {current_count + actual_chunk}/{num_bookings} bookings (Lưu vào list: {len(successful_bookings_info)} thành công)...")

        print(f"✅ Hoàn thành tạo {len(successful_bookings_info)} bookings.")

        # 3. Tạo 50,000 Reviews 
        # Chọn ngẫu nhiên 50000 successful bookings
        num_reviews = min(50000, len(successful_bookings_info))
        if num_reviews > 0:
            print(f"\n[3/3] Đang tạo {num_reviews} reviews với rating từ 3-5 sao (/reviews/)...")
            review_candidates = random.sample(successful_bookings_info, num_reviews)
            
            successful_reviews = 0
            chunk_size = 5000
            for current_count in range(0, num_reviews, chunk_size):
                actual_chunk = min(chunk_size, num_reviews - current_count)
                batch_candidates = review_candidates[current_count : current_count + actual_chunk]
                
                tasks_reviews = [create_review(session, sem, booking) for booking in batch_candidates]
                results = await asyncio.gather(*tasks_reviews)
                
                success_count = sum(1 for r in results if r)
                successful_reviews += success_count
                
                print(f"   Đã xử lý {current_count + actual_chunk}/{num_reviews} reviews (Thành công: {successful_reviews})...")
            
            print(f"✅ Hoàn thành tạo {successful_reviews} reviews.")
        else:
            print("❌ Không có booking nào thành công để đánh giá.")

        print(f"\n🎉 Automation hoàn tất! Đã sinh {len(created_user_ids)} users, {len(successful_bookings_info)} bookings, và {successful_reviews if 'successful_reviews' in locals() else 0} reviews.")

if __name__ == "__main__":
    asyncio.run(main())
