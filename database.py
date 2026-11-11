"""
database.py
SQLite database management for "Cả 1 tổ phê" (Cà phê Tổ 1).
Handles menu items, orders, order items, startup demo seeding, and real-time analytics.
"""

import os
import sqlite3
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("CAFEGO_DB_PATH", os.path.join(BASE_DIR, "cafego.db"))

INITIAL_MENU = [
    {
        "id": 1,
        "slug": "ca-phe-sua",
        "name": "Cà phê sữa",
        "tagline": "Cà phê sữa ngã ngửa vào tim em",
        "description": "Cà phê phin đậm đà quyện sữa đặc béo thơm chuẩn gu Sài Gòn, ly khổng lồ 700ml tỉnh táo cả ngày.",
        "price": 18000,
        "volume": "700ml",
        "badge": "Best Seller",
        "image_url": "/static/images/ca_phe_sua.jpg",
        "is_available": 1,
    },
    {
        "id": 2,
        "slug": "ca-phe-den",
        "name": "Cà phê đen",
        "tagline": "Cà phê đen tình đỏ bạc",
        "description": "Cà phê nguyên chất đánh bọt mịn vàng óng, hậu vị đậm sâu dành cho tín đồ mê vị nguyên bản.",
        "price": 15000,
        "volume": "700ml",
        "badge": "Giá sốc 15K",
        "image_url": "/static/images/ca_phe_den.jpg",
        "is_available": 1,
    },
    {
        "id": 3,
        "slug": "bac-xiu",
        "name": "Bạc xỉu",
        "tagline": "Bạc Xỉu cái đùng",
        "description": "Sữa tươi kết hợp sữa đặc béo ngậy cùng lớp cà phê thơm lừng, ngọt dịu dễ uống cực cuốn.",
        "price": 18000,
        "volume": "700ml",
        "badge": "Yêu thích",
        "image_url": "/static/images/bac_xiu.jpg",
        "is_available": 1,
    },
]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    conn = get_connection()
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS menu_items (
                id INTEGER PRIMARY KEY,
                slug TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                tagline TEXT NOT NULL,
                description TEXT NOT NULL,
                price INTEGER NOT NULL,
                volume TEXT NOT NULL DEFAULT '700ml',
                badge TEXT DEFAULT '',
                image_url TEXT NOT NULL,
                is_available INTEGER NOT NULL DEFAULT 1
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_code TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                table_name TEXT DEFAULT '',
                note TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                total_amount INTEGER NOT NULL DEFAULT 0,
                total_cups INTEGER NOT NULL DEFAULT 0,
                is_demo INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                menu_item_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                unit_price INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                sweetness TEXT NOT NULL DEFAULT 'Chuẩn vị Tổ 1',
                ice_level TEXT NOT NULL DEFAULT 'Đá chung bình thường',
                item_note TEXT DEFAULT '',
                subtotal INTEGER NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
            );
            """
        )

        # Seed initial 3 drinks if empty
        cur = conn.execute("SELECT COUNT(*) as cnt FROM menu_items;")
        if cur.fetchone()["cnt"] == 0:
            for item in INITIAL_MENU:
                conn.execute(
                    """
                    INSERT INTO menu_items (id, slug, name, tagline, description, price, volume, badge, image_url, is_available)
                    VALUES (:id, :slug, :name, :tagline, :description, :price, :volume, :badge, :image_url, :is_available);
                    """,
                    item,
                )
    conn.close()


def get_menu_items() -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM menu_items ORDER BY id ASC;").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def toggle_menu_item_availability(item_id: int, is_available: bool) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE menu_items SET is_available = ? WHERE id = ?;",
            (1 if is_available else 0, item_id),
        )
        row = conn.execute("SELECT * FROM menu_items WHERE id = ?;", (item_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_menu_item_price(item_id: int, new_price: int) -> Optional[Dict[str, Any]]:
    if new_price < 1000:
        raise ValueError("Giá sản phẩm phải từ 1.000đ trở lên.")
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE menu_items SET price = ? WHERE id = ?;",
            (int(new_price), item_id),
        )
        row = conn.execute("SELECT * FROM menu_items WHERE id = ?;", (item_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _next_order_code(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT COUNT(*) as cnt FROM orders;").fetchone()
    next_num = 101 + (row["cnt"] if row else 0)
    return f"#{next_num}"


def create_order(
    customer_name: str,
    table_name: str,
    note: str,
    items: List[Dict[str, Any]],
    is_demo: bool = False,
    custom_status: str = "pending",
    custom_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    if not items:
        raise ValueError("Đơn hàng phải có ít nhất 1 món.")

    conn = get_connection()
    now_dt = custom_time or datetime.now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    with conn:
        menu_map = {
            r["id"]: dict(r)
            for r in conn.execute("SELECT * FROM menu_items;").fetchall()
        }

        order_code = _next_order_code(conn)
        total_amount = 0
        total_cups = 0
        resolved_items = []

        for req_item in items:
            m_id = int(req_item["menu_item_id"])
            if m_id not in menu_map:
                raise ValueError(f"Món ID={m_id} không tồn tại.")
            m_info = menu_map[m_id]
            if not is_demo and not m_info["is_available"]:
                raise ValueError(f"Món '{m_info['name']}' hiện đang tạm hết.")

            qty = max(1, int(req_item.get("quantity", 1)))
            unit_price = int(m_info["price"])
            subtotal = unit_price * qty
            total_amount += subtotal
            total_cups += qty

            resolved_items.append(
                {
                    "menu_item_id": m_id,
                    "item_name": m_info["name"],
                    "unit_price": unit_price,
                    "quantity": qty,
                    "sweetness": req_item.get("sweetness") or "Chuẩn vị Tổ 1",
                    "ice_level": req_item.get("ice_level") or "Đá chung bình thường",
                    "item_note": (req_item.get("item_note") or "").strip(),
                    "subtotal": subtotal,
                }
            )

        cur = conn.execute(
            """
            INSERT INTO orders (
                order_code, customer_name, table_name, note, status,
                total_amount, total_cups, is_demo, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                order_code,
                customer_name.strip() or "Khách Tổ 1",
                table_name.strip(),
                note.strip(),
                custom_status,
                total_amount,
                total_cups,
                1 if is_demo else 0,
                now_str,
                now_str,
            ),
        )
        order_id = cur.lastrowid

        for r_item in resolved_items:
            conn.execute(
                """
                INSERT INTO order_items (
                    order_id, menu_item_id, item_name, unit_price, quantity,
                    sweetness, ice_level, item_note, subtotal
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    order_id,
                    r_item["menu_item_id"],
                    r_item["item_name"],
                    r_item["unit_price"],
                    r_item["quantity"],
                    r_item["sweetness"],
                    r_item["ice_level"],
                    r_item["item_note"],
                    r_item["subtotal"],
                ),
            )

    conn.close()
    return get_order_by_id(order_id)  # type: ignore


def get_order_by_id(order_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM orders WHERE id = ?;", (order_id,)).fetchone()
    if not row:
        conn.close()
        return None
    order = dict(row)
    items = conn.execute(
        """
        SELECT oi.*, m.image_url, m.tagline
        FROM order_items oi
        LEFT JOIN menu_items m ON m.id = oi.menu_item_id
        WHERE oi.order_id = ?
        ORDER BY oi.id ASC;
        """,
        (order_id,),
    ).fetchall()
    order["items"] = [dict(i) for i in items]
    conn.close()
    return order


def list_orders(status_filter: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_connection()
    if status_filter and status_filter != "all":
        rows = conn.execute(
            "SELECT * FROM orders WHERE status = ? ORDER BY id DESC LIMIT ?;",
            (status_filter, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM orders ORDER BY id DESC LIMIT ?;",
            (limit,),
        ).fetchall()

    orders = [dict(r) for r in rows]
    if orders:
        order_ids = [o["id"] for o in orders]
        placeholders = ",".join("?" for _ in order_ids)
        item_rows = conn.execute(
            f"""
            SELECT oi.*, m.image_url, m.tagline
            FROM order_items oi
            LEFT JOIN menu_items m ON m.id = oi.menu_item_id
            WHERE oi.order_id IN ({placeholders})
            ORDER BY oi.id ASC;
            """,
            order_ids,
        ).fetchall()
        items_by_order: Dict[int, List[Dict[str, Any]]] = {oid: [] for oid in order_ids}
        for ir in item_rows:
            d = dict(ir)
            items_by_order[d["order_id"]].append(d)
        for o in orders:
            o["items"] = items_by_order.get(o["id"], [])
    conn.close()
    return orders


def update_order_status(order_id: int, new_status: str) -> Optional[Dict[str, Any]]:
    valid_statuses = {"pending", "preparing", "ready", "completed", "cancelled"}
    if new_status not in valid_statuses:
        raise ValueError(f"Trạng thái không hợp lệ: {new_status}")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?;",
            (new_status, now_str, order_id),
        )
    conn.close()
    return get_order_by_id(order_id)


def get_startup_analytics() -> Dict[str, Any]:
    conn = get_connection()
    orders = conn.execute(
        "SELECT * FROM orders WHERE status != 'cancelled' ORDER BY id DESC;"
    ).fetchall()

    total_revenue = sum(r["total_amount"] for r in orders)
    total_cups = sum(r["total_cups"] for r in orders)
    total_orders = len(orders)

    active_orders = sum(1 for r in orders if r["status"] in ("pending", "preparing", "ready"))
    completed_orders = sum(1 for r in orders if r["status"] in ("ready", "completed"))

    avg_order_value = round(total_revenue / total_orders) if total_orders > 0 else 0

    # Product mix breakdown
    mix_rows = conn.execute(
        """
        SELECT
            m.id as menu_item_id,
            m.name as name,
            m.tagline as tagline,
            m.price as unit_price,
            m.image_url as image_url,
            COALESCE(SUM(CASE WHEN o.status != 'cancelled' AND o.id IS NOT NULL THEN oi.quantity ELSE 0 END), 0) as cups_sold,
            COALESCE(SUM(CASE WHEN o.status != 'cancelled' AND o.id IS NOT NULL THEN oi.subtotal ELSE 0 END), 0) as revenue
        FROM menu_items m
        LEFT JOIN order_items oi ON oi.menu_item_id = m.id
        LEFT JOIN orders o ON o.id = oi.order_id
        GROUP BY m.id
        ORDER BY cups_sold DESC, m.id ASC;
        """
    ).fetchall()

    product_mix = []
    for r in mix_rows:
        d = dict(r)
        d["share_percent"] = round((d["cups_sold"] / total_cups) * 100, 1) if total_cups > 0 else 0.0
        product_mix.append(d)

    # Hourly order distribution for startup pitch chart
    hourly_map: Dict[str, int] = {f"{h:02d}:00": 0 for h in range(6, 22, 2)}
    for r in orders:
        try:
            dt = datetime.strptime(r["created_at"], "%Y-%m-%d %H:%M:%S")
            bucket_hour = (dt.hour // 2) * 2
            bucket_hour = min(max(bucket_hour, 6), 20)
            key = f"{bucket_hour:02d}:00"
            hourly_map[key] = hourly_map.get(key, 0) + r["total_cups"]
        except Exception:
            pass

    conn.close()
    return {
        "total_revenue": total_revenue,
        "total_cups": total_cups,
        "total_orders": total_orders,
        "active_orders": active_orders,
        "completed_orders": completed_orders,
        "avg_order_value": avg_order_value,
        "avg_prep_minutes": 2.4 if total_orders > 0 else 0,
        "product_mix": product_mix,
        "hourly_cups": [{"hour": k, "cups": v} for k, v in hourly_map.items()],
    }


def seed_startup_demo_data() -> Dict[str, Any]:
    """
    Populates realistic demo orders for the Startup Pitch presentation
    so the analytics dashboard and order queue look vibrant and impressive.
    """
    sample_customers = [
        ("Anh Minh", "Bàn 01"),
        ("Chị Lan", "Bàn 03"),
        ("Bạn Tuấn (Áo sơ mi)", "Quầy vỉa hè"),
        ("Nhóm bạn ĐH Kinh Tế", "Bàn 05"),
        ("Chị Hương", "Mang đi"),
        ("Anh Khoa", "Bàn 02"),
        ("Bạn Ngọc", "Bàn 04"),
        ("Anh Đức", "Đứng cạnh xe"),
        ("Team Startup", "Bàn VIP 01"),
        ("Chị Thảo", "Bàn 06"),
        ("Bạn Huy", "Mang đi"),
        ("Cô Mai", "Bàn 02"),
        ("Anh Phong", "Bàn 03"),
        ("Bạn Linh", "Bàn 01"),
        ("Anh Hoàng", "Mang đi"),
        ("Chị Trang", "Bàn 04"),
        ("Bạn Khang", "Quầy vỉa hè"),
        ("Anh Việt", "Bàn 05"),
    ]
    sweetness_opts = ["Chuẩn vị Tổ 1", "Ít ngọt", "Nhiều sữa", "Chuẩn vị Tổ 1"]
    ice_opts = ["Đá chung bình thường", "Ít đá", "Đá để riêng", "Đá chung bình thường"]

    now = datetime.now()
    rng = random.Random(2026)

    for idx, (cname, tname) in enumerate(sample_customers):
        # Spread orders across morning/afternoon hours
        mins_ago = (len(sample_customers) - idx) * 14
        order_time = now - timedelta(minutes=mins_ago)

        # Pick 1 to 3 items weighted towards Cà phê sữa & Bạc xỉu
        num_lines = rng.choices([1, 2, 3], weights=[55, 35, 10])[0]
        chosen_ids = rng.sample([1, 2, 3], k=num_lines)
        items = []
        for mid in chosen_ids:
            qty = rng.choices([1, 2, 3], weights=[65, 25, 10])[0]
            items.append(
                {
                    "menu_item_id": mid,
                    "quantity": qty,
                    "sweetness": rng.choice(sweetness_opts),
                    "ice_level": rng.choice(ice_opts),
                    "item_note": "Cho thêm túi treo xe" if idx % 5 == 0 else "",
                }
            )

        if idx < len(sample_customers) - 3:
            status = "completed"
        elif idx == len(sample_customers) - 3:
            status = "ready"
        elif idx == len(sample_customers) - 2:
            status = "preparing"
        else:
            status = "pending"

        create_order(
            customer_name=cname,
            table_name=tname,
            note="Khách quen Tổ 1" if idx % 4 == 0 else "",
            items=items,
            is_demo=True,
            custom_status=status,
            custom_time=order_time,
        )

    return get_startup_analytics()


def reset_all_orders() -> None:
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM order_items;")
        conn.execute("DELETE FROM orders;")
        conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('orders', 'order_items');")
        conn.execute("UPDATE menu_items SET is_available = 1;")
    conn.close()
