import asyncio
import aiohttp
import random
import string
import uuid
from datetime import date, datetime, timedelta
import time

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

async def create_users_bulk_api(session, sem, user_payloads):
    url = f"{BASE_URL}/users/register/bulk"
    async with sem:
        try:
            async with session.post(url, json=user_payloads) as response:
                if response.status in (200, 201):
                    data = await response.json()
                    return [u.get("user_id") for u in data]
                else:
                    text = await response.text()
                    print(f"❌ Bulk user registration failed: {response.status} - {text}")
                    return []
        except Exception as e:
            print(f"❌ Bulk user register error: {e}")
            return []

async def create_bookings_bulk(session, sem, booking_payloads):
    url = f"{BASE_URL}/Admin/bookings/bulk"
    async with sem:
        try:
            async with session.post(url, json=booking_payloads) as response:
                if response.status in (200, 201):
                    data = await response.json()
                    return data
                else:
                    text = await response.text()
                    print(f"❌ Bulk booking insert failed: {response.status} - {text}")
                    return None
        except Exception as e:
            print(f"❌ Bulk booking insert error: {e}")
            return None

async def create_reviews_bulk(session, sem, review_payloads):
    url = f"{BASE_URL}/reviews/bulk"
    async with sem:
        try:
            async with session.post(url, json=review_payloads) as response:
                if response.status in (200, 201):
                    return True
                else:
                    text = await response.text()
                    print(f"❌ Bulk review insert failed: {response.status} - {text}")
                    return False
        except Exception as e:
            print(f"❌ Bulk review insert error: {e}")
            return False

async def main():
    start_time = time.time()
    # Sử dụng semaphore lớn hơn do tạo số lượng rất khủng
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
        
        # 1. Tạo 50,000 Users
        num_users = 50000
        print(f"\n[1/3] Đang tạo {num_users} users qua API Bulk (/users/register/bulk)...")
        
        created_user_ids = []
        api_user_batch_size = 500
        user_concurrency = 20
        
        for i in range(0, num_users, api_user_batch_size * user_concurrency):
            batch_tasks = []
            for j in range(user_concurrency):
                start_idx = i + (j * api_user_batch_size)
                if start_idx >= num_users:
                    break
                
                count = int(min(api_user_batch_size, num_users - start_idx))
                payloads = []
                for k in range(count):
                    idx = start_idx + k
                    payloads.append({
                        "name": f"Auto Customer {idx}",
                        "email": f"autouser_{idx}_{generate_random_string(4)}@example.com",
                        "phone": generate_random_phone(),
                        "role": "Customer",
                        "password": "password123"
                    })
                batch_tasks.append(create_users_bulk_api(session, sem, payloads))
            
            if batch_tasks:
                results = await asyncio.gather(*batch_tasks)
                for u_list in results:
                    created_user_ids.extend(u_list)
                print(f"   Đã tạo {len(created_user_ids)}/{num_users} users...")

        print(f"✅ Hoàn thành tạo {len(created_user_ids)} users.")

        # 2. Tạo 200,000 Bookings
        num_bookings = 200000
        print(f"\n[2/3] Đang tạo {num_bookings} bookings qua API Bulk (/Admin/bookings/bulk)...")
        
        successful_bookings_info = []
        api_booking_batch_size = 1000
        booking_concurrency = 15
        
        for i in range(0, num_bookings, api_booking_batch_size * booking_concurrency):
            batch_tasks = []
            for j in range(booking_concurrency):
                start_idx = i + (j * api_booking_batch_size)
                if start_idx >= num_bookings:
                    break
                
                count = int(min(api_booking_batch_size, num_bookings - start_idx))
                payloads = []
                for k in range(count):
                    idx = start_idx + k
                    room = random.choice(available_rooms)
                    user_id = random.choice(created_user_ids)
                    
                    start_offset = random.randint(1, 120)
                    duration = random.randint(1, 4)
                    from_date_obj = date.today() - timedelta(days=start_offset + duration)
                    to_date_obj = from_date_obj + timedelta(days=duration)
                    
                    payloads.append({
                        "user_id": user_id,
                        "branch_code": room.get("branch_code"),
                        "branch_room_id": room.get("branch_room_id"),
                        "room_id": room.get("room_id"),
                        "voucher_code": "WELCOME2026" if random.choice([True, False]) else None,
                        "customer_name": f"Auto Customer {idx}",
                        "customer_email": f"customer_{idx}@test.com",
                        "customer_phonenumber": generate_random_phone(),
                        "note": "Bulk historical booking",
                        "from_date": from_date_obj.isoformat(),
                        "to_date": to_date_obj.isoformat(),
                        "total_price": float(room.get("price", 0)) * duration,
                        "status": "Completed",
                        "payment_status": "paid"
                    })
                batch_tasks.append(create_bookings_bulk(session, sem, payloads))
            
            if batch_tasks:
                results = await asyncio.gather(*batch_tasks)
                for res_list in results:
                    if res_list and isinstance(res_list, list):
                        for b in res_list:
                            try:
                                f_date = datetime.fromisoformat(b.get("from_date"))
                                t_date = datetime.fromisoformat(b.get("to_date"))
                                total_nights = (t_date - f_date).days
                            except:
                                total_nights = 1

                            successful_bookings_info.append({
                                "booking_id": b.get("booking_id"),
                                "booking_code": b.get("booking_code"),
                                "branch_code": b.get("branch_code"),
                                "room_id": b.get("room_id"),
                                "user_id": b.get("user_id"),
                                "customer_name": b.get("customer_name"),
                                "customer_email": b.get("customer_email"),
                                "customer_phonenumber": b.get("customer_phonenumber"),
                                "check_in_date": b.get("from_date"),
                                "check_out_date": b.get("to_date"),
                                "total_nights": total_nights,
                                "traveler_type": random.choice(["Gia đình", "Cặp đôi", "Công tác", "Cá nhân"])
                            })
            print(f"   Đã xử lý khoảng {min(i + api_booking_batch_size * booking_concurrency, num_bookings)}/{num_bookings} bookings (Thành công: {len(successful_bookings_info)})...")

        print(f"✅ Hoàn thành tạo {len(successful_bookings_info)} bookings.")

        # 3. Tạo 50,000 Reviews 
        num_reviews = min(50000, len(successful_bookings_info))
        if num_reviews > 0:
            print(f"\n[3/3] Đang tạo {num_reviews} reviews qua API Bulk (/reviews/bulk)...")
            review_candidates = random.sample(successful_bookings_info, num_reviews)
            
            successful_reviews = 0
            api_review_batch_size = 1000
            review_concurrency = 15
            
            for i in range(0, num_reviews, api_review_batch_size * review_concurrency):
                batch_tasks = []
                for j in range(review_concurrency):
                    start_idx = i + (j * api_review_batch_size)
                    if start_idx >= num_reviews:
                        break
                    
                    count = int(min(api_review_batch_size, num_reviews - start_idx))
                    payloads = []
                    for k in range(count):
                        booking = review_candidates[start_idx + k]
                        overall = random.randint(3, 5)
                        comments = {
                            3: ["Khách sạn tạm ổn, hơi ồn", "Phòng cũng được nhưng dịch vụ chưa tốt", "Phòng sạch sẽ cơ bản, không có gì nổi bật"],
                            4: ["Khách sạn tốt, giá hợp lý", "Nhân viên thân thiện, vị trí đẹp", "Chất lượng khá so với tầm giá"],
                            5: ["Tuyệt vời, sẽ quay lại lần sau", "Trải nghiệm vượt sức mong đợi", "Combo dịch vụ quá xịn xò, phòng cực đẹp"]
                        }
                        
                        payloads.append({
                            "branch_code": booking["branch_code"],
                            "booking_id": str(booking["booking_id"]),
                            "room_id": str(booking["room_id"]),
                            "customer": {
                                "user_id": str(booking["user_id"]),
                                "name": booking["customer_name"],
                                "email": booking["customer_email"],
                                "phone": booking["customer_phonenumber"],
                                "avatar_url": None
                            },
                            "booking_info": {
                                "booking_code": booking["booking_code"],
                                "room_type_name": booking.get("room_type_name", "Standard Room"),
                                "room_number": booking.get("room_number", "101"),
                                "check_in_date": booking["check_in_date"],
                                "check_out_date": booking["check_out_date"],
                                "total_nights": booking["total_nights"],
                                "traveler_type": booking["traveler_type"]
                            },
                            "rating": {
                                "overall": overall,
                                "cleanliness": random.randint(max(3, overall-1), 5),
                                "service": random.randint(max(3, overall-1), 5),
                                "location": random.randint(max(3, overall-1), 5)
                            },
                            "comment": random.choice(comments[overall]),
                            "attached_images": []
                        })
                    batch_tasks.append(create_reviews_bulk(session, sem, payloads))
                
                if batch_tasks:
                    await asyncio.gather(*batch_tasks)
                    successful_reviews = min(num_reviews, i + api_review_batch_size * review_concurrency)
                    print(f"   Đã xử lý khoảng {successful_reviews}/{num_reviews} reviews...")
            
            print(f"✅ Hoàn thành tạo reviews.")
        
        print(f"\n🎉 Automation hoàn tất! Đã sinh {len(created_user_ids)} users, {len(successful_bookings_info)} bookings, và {num_reviews} reviews.")
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)
        print(f"⏱️ Tổng thời gian chạy: {minutes} phút {seconds} giây ({elapsed_time:.2f} s)")

if __name__ == "__main__":
    asyncio.run(main())
