"""
app.py
Full-Stack Backend for "Cả 1 tổ phê" (Cà phê Tổ 1).
Built with Starlette + Uvicorn + SSE-Starlette + QRCode + SQLite.
"""

import asyncio
import io
import json
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, Set
from urllib.parse import quote

import qrcode
from PIL import Image, ImageDraw
from sse_starlette.sse import EventSourceResponse
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

import database as db
from prepare_assets import prepare_brand_assets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
PUBLIC_URL_FILE = os.path.join(BASE_DIR, "public_url.txt")
MASTER_PIN = os.environ.get("CAFEGO_MASTER_PIN", "21346573")
STAFF_PIN = os.environ.get("CAFEGO_STAFF_PIN", "6767")


class EventBroadcaster:
    """Manages connected SSE clients for real-time updates to customers and barista dashboard."""

    def __init__(self) -> None:
        self.subscribers: Set[asyncio.Queue] = set()

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self.subscribers.discard(q)

    async def broadcast(self, event_type: str, payload: Dict[str, Any]) -> None:
        if not self.subscribers:
            return
        message = {"event": event_type, "data": json.dumps(payload, ensure_ascii=False)}
        for q in list(self.subscribers):
            try:
                q.put_nowait(message)
            except Exception:
                self.subscribers.discard(q)


broadcaster = EventBroadcaster()


def get_detected_public_url(request: Request) -> str:
    """Returns the active public URL (from public_url.txt or request headers)."""
    env_url = os.environ.get("PUBLIC_BASE_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")

    if os.path.exists(PUBLIC_URL_FILE):
        try:
            with open(PUBLIC_URL_FILE, "r", encoding="utf-8") as f:
                saved = f.read().strip()
                if saved.startswith("http"):
                    return saved.rstrip("/")
        except Exception:
            pass

    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}".rstrip("/")


# --- HTML Page Routes ---


async def index_page(request: Request) -> Response:
    return FileResponse(
        os.path.join(STATIC_DIR, "index.html"),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


async def admin_page(request: Request) -> Response:
    return FileResponse(
        os.path.join(STATIC_DIR, "admin.html"),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


# --- API Endpoints ---


async def api_get_config(request: Request) -> JSONResponse:
    return JSONResponse(
        {
            "brand_name": "Cả 1 tổ phê",
            "sub_brand": "Cà phê Tổ 1",
            "slogan": "Năng lượng cho ngày mới — Sáng nay bạn chọn Ngụm vị nào?",
            "cup_size": "1 LY “TO ĐÙNG” 700ML",
            "public_url": get_detected_public_url(request),
        }
    )


async def api_verify_pin(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        body = {}
    pin = str(body.get("pin", "")).strip()
    if pin == MASTER_PIN:
        return JSONResponse(
            {
                "ok": True,
                "role": "admin",
                "role_label": "Chủ quán (Admin Chính)",
                "message": "Đăng nhập quyền Admin Chính thành công!",
            }
        )
    if pin == STAFF_PIN:
        return JSONResponse(
            {
                "ok": True,
                "role": "staff",
                "role_label": "Nhân viên Quầy",
                "message": "Đăng nhập quyền Nhân viên thành công!",
            }
        )
    return JSONResponse({"ok": False, "error": "Mã PIN không chính xác!"}, status_code=401)


async def api_get_menu(request: Request) -> JSONResponse:
    items = db.get_menu_items()
    return JSONResponse({"items": items})


async def api_toggle_menu_item(request: Request) -> JSONResponse:
    item_id = int(request.path_params["item_id"])
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    is_available = bool(body.get("is_available", True))
    updated = db.toggle_menu_item_availability(item_id, is_available)
    if not updated:
        return JSONResponse({"error": "Không tìm thấy món"}, status_code=404)

    await broadcaster.broadcast("menu_updated", {"item": updated})
    return JSONResponse({"item": updated})


async def api_update_menu_price(request: Request) -> JSONResponse:
    item_id = int(request.path_params["item_id"])
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    pin = str(body.get("pin", "")).strip()
    if pin != MASTER_PIN:
        return JSONResponse({"error": "Chỉ Admin Chính mới có quyền chỉnh giá sản phẩm!"}, status_code=403)

    try:
        new_price = int(body.get("price", 0))
        updated = db.update_menu_item_price(item_id, new_price)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    if not updated:
        return JSONResponse({"error": "Không tìm thấy món"}, status_code=404)

    await broadcaster.broadcast("menu_updated", {"item": updated})
    return JSONResponse({"item": updated})


async def api_create_order(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Dữ liệu không hợp lệ."}, status_code=400)

    customer_name = str(body.get("customer_name", "")).strip()
    table_name = str(body.get("table_name", "")).strip()
    note = str(body.get("note", "")).strip()
    items = body.get("items", [])

    if not customer_name and not table_name:
        return JSONResponse(
            {"error": "Vui lòng nhập Tên gọi hoặc Số bàn để tụi mình gọi tên nhé!"},
            status_code=400,
        )

    try:
        order = db.create_order(
            customer_name=customer_name or "Khách Tổ 1",
            table_name=table_name,
            note=note,
            items=items,
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    await broadcaster.broadcast("order_created", {"order": order})
    return JSONResponse({"order": order}, status_code=201)


async def api_list_orders(request: Request) -> JSONResponse:
    status_filter = request.query_params.get("status", "all")
    orders = db.list_orders(status_filter=status_filter)
    return JSONResponse({"orders": orders})


async def api_get_order(request: Request) -> JSONResponse:
    order_id = int(request.path_params["order_id"])
    order = db.get_order_by_id(order_id)
    if not order:
        return JSONResponse({"error": "Không tìm thấy đơn hàng."}, status_code=404)
    return JSONResponse({"order": order})


async def api_update_order_status(request: Request) -> JSONResponse:
    order_id = int(request.path_params["order_id"])
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    new_status = str(body.get("status", "")).strip()
    try:
        updated = db.update_order_status(order_id, new_status)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    if not updated:
        return JSONResponse({"error": "Không tìm thấy đơn hàng."}, status_code=404)

    await broadcaster.broadcast("order_updated", {"order": updated})
    return JSONResponse({"order": updated})


async def api_get_stats(request: Request) -> JSONResponse:
    stats = db.get_startup_analytics()
    return JSONResponse({"stats": stats})


async def api_seed_demo(request: Request) -> JSONResponse:
    stats = db.seed_startup_demo_data()
    await broadcaster.broadcast("demo_seeded", {"stats": stats})
    return JSONResponse({"ok": True, "stats": stats})


async def api_reset_orders(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        body = {}
    pin = str(body.get("pin", "")).strip()
    if pin != MASTER_PIN:
        return JSONResponse({"error": "Chỉ Admin Chính mới có quyền xoá sạch đơn!"}, status_code=403)

    db.reset_all_orders()
    stats = db.get_startup_analytics()
    await broadcaster.broadcast("orders_reset", {"stats": stats})
    return JSONResponse({"ok": True, "stats": stats})


async def api_generate_qr(request: Request) -> Response:
    """Generates a styled brand QR code PNG pointing to the order page."""
    table = request.query_params.get("table", "").strip()
    custom_url = request.query_params.get("url", "").strip()
    base_url = custom_url.rstrip("/") if custom_url else get_detected_public_url(request)

    target_url = f"{base_url}/?table={quote(table)}" if table else f"{base_url}/"

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(target_url)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="#1D120E", back_color="#FFFDF6").convert("RGBA")

    # Embed small brand logo in the center if available
    logo_path = os.path.join(STATIC_DIR, "images", "logo.png")
    if os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            qr_w, qr_h = qr_img.size
            logo_size = int(qr_w * 0.22)
            logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

            # White rounded pad behind logo
            pad = 8
            bg_size = logo_size + pad * 2
            badge_bg = Image.new("RGBA", (bg_size, bg_size), (255, 253, 246, 255))
            draw = ImageDraw.Draw(badge_bg)
            draw.rounded_rectangle(
                [(0, 0), (bg_size - 1, bg_size - 1)],
                radius=12,
                fill=(255, 253, 246, 255),
                outline=(200, 42, 30, 255),
                width=3,
            )
            pos_bg = ((qr_w - bg_size) // 2, (qr_h - bg_size) // 2)
            pos_logo = ((qr_w - logo_size) // 2, (qr_h - logo_size) // 2)
            qr_img.paste(badge_bg, pos_bg, badge_bg)
            qr_img.paste(logo, pos_logo, logo)
        except Exception:
            pass

    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    buf.seek(0)
    return Response(content=buf.getvalue(), media_type="image/png")


async def api_sse_stream(request: Request) -> EventSourceResponse:
    queue = await broadcaster.subscribe()

    async def event_generator():
        try:
            yield {"event": "connected", "data": json.dumps({"status": "ok"})}
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield msg
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "keepalive"}
        finally:
            broadcaster.unsubscribe(queue)

    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@asynccontextmanager
async def lifespan(app: Starlette):
    os.makedirs(os.path.join(STATIC_DIR, "images"), exist_ok=True)
    if not os.path.exists(os.path.join(STATIC_DIR, "images", "poster.jpg")):
        try:
            prepare_brand_assets()
        except Exception as e:
            print(f"Warning preparing assets: {e}")
    db.init_db()
    stats = db.get_startup_analytics()
    if stats["total_orders"] == 0:
        db.seed_startup_demo_data()
    yield


routes = [
    Route("/", endpoint=index_page, methods=["GET"]),
    Route("/admin", endpoint=admin_page, methods=["GET"]),
    Route("/api/config", endpoint=api_get_config, methods=["GET"]),
    Route("/api/admin/verify-pin", endpoint=api_verify_pin, methods=["POST"]),
    Route("/api/menu", endpoint=api_get_menu, methods=["GET"]),
    Route("/api/menu/{item_id:int}/toggle", endpoint=api_toggle_menu_item, methods=["POST"]),
    Route("/api/menu/{item_id:int}/price", endpoint=api_update_menu_price, methods=["POST"]),
    Route("/api/orders", endpoint=api_list_orders, methods=["GET"]),
    Route("/api/orders", endpoint=api_create_order, methods=["POST"]),
    Route("/api/orders/{order_id:int}", endpoint=api_get_order, methods=["GET"]),
    Route("/api/orders/{order_id:int}/status", endpoint=api_update_order_status, methods=["POST"]),
    Route("/api/stats", endpoint=api_get_stats, methods=["GET"]),
    Route("/api/demo/seed", endpoint=api_seed_demo, methods=["POST"]),
    Route("/api/demo/reset", endpoint=api_reset_orders, methods=["POST"]),
    Route("/api/qr", endpoint=api_generate_qr, methods=["GET"]),
    Route("/api/stream", endpoint=api_sse_stream, methods=["GET"]),
    Mount("/static", app=StaticFiles(directory=STATIC_DIR), name="static"),
]

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

app = Starlette(
    debug=True,
    routes=routes,
    middleware=middleware,
    lifespan=lifespan,
)

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
