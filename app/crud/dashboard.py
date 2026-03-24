from app.db.cockroach import get_connection
from psycopg.rows import dict_row

def get_dashboard_stats():
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # Stats queries
            cur.execute("""
                SELECT COALESCE(SUM(amount), 0) AS total_revenue 
                FROM payments 
                WHERE LOWER(status) IN ('completed', 'paid') AND del_flg = 0;
            """)
            revenue_row = cur.fetchone()
            total_revenue = float(revenue_row["total_revenue"]) if revenue_row else 0

            cur.execute("SELECT COUNT(booking_id) AS total_bookings FROM bookings WHERE LOWER(status) != 'cancelled' AND del_flg = 0;")
            bookings_row = cur.fetchone()
            total_bookings = int(bookings_row["total_bookings"]) if bookings_row else 0

            cur.execute("SELECT COUNT(branch_code) AS total_branches FROM branches WHERE del_flg = 0;")
            branches_row = cur.fetchone()
            total_branches = int(branches_row["total_branches"]) if branches_row else 0

            cur.execute("SELECT COUNT(user_id) AS total_accounts FROM users WHERE del_flg = 0;")
            accounts_row = cur.fetchone()
            total_accounts = int(accounts_row["total_accounts"]) if accounts_row else 0

            # Formatting total revenue
            formatted_revenue = f"₫ {int(total_revenue):,}".replace(",", ".")

            stats = [
                {
                    "key": "admin.dashboard.totalRevenue",
                    "value": formatted_revenue,
                    "change": "+12.5%",
                    "up": True
                },
                {
                    "key": "admin.dashboard.totalBookings",
                    "value": f"{total_bookings:,}".replace(",", "."),
                    "change": "+8.2%",
                    "up": True
                },
                {
                    "key": "admin.dashboard.totalBranches",
                    "value": str(total_branches),
                    "change": "+1",
                    "up": True
                },
                {
                    "key": "admin.dashboard.totalAccounts",
                    "value": f"{total_accounts:,}".replace(",", "."),
                    "change": "-2.1%",
                    "up": False
                }
            ]

            # Recent bookings
            cur.execute("""
                SELECT 
                    b.booking_code AS id, 
                    b.customer_name AS guest, 
                    br.name AS branch, 
                    TO_CHAR(b.from_date, 'DD/MM/YYYY') AS checkIn, 
                    TO_CHAR(b.to_date, 'DD/MM/YYYY') AS checkOut, 
                    b.total_price AS amount, 
                    LOWER(b.status) AS status
                FROM bookings b
                LEFT JOIN branches br ON br.branch_code = b.branch_code
                WHERE b.del_flg = 0
                ORDER BY b.created_date DESC, b.created_time DESC, b.booking_id DESC
                LIMIT 5;
            """)
            recent_rows = cur.fetchall()
            
            recentBookings = []
            status_map = {
                "pending": "pending",
                "confirmed": "confirmed",
                "checked-in": "checkedIn",
                "completed": "checkedOut",
                "cancelled": "cancelled"
            }
            
            for row in recent_rows:
                db_status = row["status"] if row["status"] else "pending"
                mapped_status = status_map.get(db_status, "pending")
                amt = float(row["amount"]) if row["amount"] else 0
                formatted_amt = f"₫ {int(amt):,}".replace(",", ".")
                
                recentBookings.append({
                    "id": f"#{row['id']}",
                    "guest": row["guest"],
                    "branch": row["branch"] or "Unknown",
                    "checkIn": row["checkin"],
                    "checkOut": row["checkout"],
                    "amount": formatted_amt,
                    "status": mapped_status
                })

            # Top branches
            cur.execute("""
                SELECT 
                    br.name AS name, 
                    COALESCE(SUM(b.total_price), 0) AS revenue, 
                    COUNT(b.booking_id) AS bookings
                FROM branches br
                LEFT JOIN bookings b ON b.branch_code = br.branch_code AND LOWER(b.status) != 'cancelled' AND b.del_flg = 0
                WHERE br.del_flg = 0
                GROUP BY br.name
                ORDER BY revenue DESC
                LIMIT 5;
            """)
            top_rows = cur.fetchall()
            
            # Tính % fill bar (branch cao nhất lấy làm 100%)
            max_revenue = max((float(r["revenue"]) for r in top_rows), default=1)
            if max_revenue == 0:
                max_revenue = 1
                
            topBranches = []
            for row in top_rows:
                rev = float(row["revenue"])
                formatted_rev = f"₫ {int(rev):,}".replace(",", ".")
                if rev >= 1_000_000_000:
                    formatted_rev = f"₫ {rev / 1_000_000_000:.1f}B".replace(".", ",")
                elif rev >= 1_000_000:
                    formatted_rev = f"₫ {rev / 1_000_000:.1f}M".replace(".", ",")
                else:
                    formatted_rev = f"₫ {int(rev):,}".replace(",", ".")
                    
                topBranches.append({
                    "name": row["name"],
                    "revenue": formatted_rev,
                    "bookings": int(row["bookings"]),
                    "fill": int((rev / max_revenue) * 100)
                })

            return {
                "stats": stats,
                "recentBookings": recentBookings,
                "topBranches": topBranches
            }
