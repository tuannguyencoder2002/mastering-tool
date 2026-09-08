# -*- coding: utf-8 -*-
"""Lớp khoá bằng mật khẩu, chỉ bật khi mở app ra ngoài mạng.

Chạy ở máy mình thì KHÔNG có khoá — thêm một bước gõ mật khẩu vào việc mở app
hằng ngày là phiền vô ích, và máy mình thì đã có khoá màn hình rồi.

Nhưng khi mở đường hầm cho khách vào thì bắt buộc phải có: app này nhận file
tải lên, chạy GPU, và trả về file. Không khoá thì bất kỳ ai dò ra địa chỉ đều
dùng được máy bạn, và xem được cả bài của khách khác vừa gửi lên.

Bật bằng biến môi trường MASTERING_PASS. Không đặt biến đó thì lớp này biến
mất hoàn toàn, không tốn một dòng xử lý nào cho mỗi request.
"""
import hmac
import os
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class Khoa(BaseHTTPMiddleware):
    """Xác thực Basic. Trình duyệt tự hiện hộp đăng nhập, không cần trang riêng."""

    def __init__(self, app, mat_khau: str, ten: str = "khach"):
        super().__init__(app)
        self.dung = f"{ten}:{mat_khau}"

    async def dispatch(self, request, call_next):
        gui = request.headers.get("authorization", "")
        if gui.lower().startswith("basic "):
            import base64
            try:
                giai = base64.b64decode(gui[6:]).decode("utf-8")
            except Exception:
                giai = ""
            # So sánh kiểu hằng thời gian: so bằng `==` thì thời gian trả lời
            # thay đổi theo số ký tự khớp, và về lý thuyết dò được mật khẩu
            # từng ký tự một.
            if hmac.compare_digest(giai, self.dung):
                return await call_next(request)

        return Response(
            "Cần mật khẩu.", status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Mastering"'},
        )


def gan_neu_can(app) -> str:
    """Gắn lớp khoá nếu có biến môi trường. Trả về mật khẩu đang dùng, hoặc ''."""
    mk = os.environ.get("MASTERING_PASS", "").strip()
    if not mk:
        return ""
    app.add_middleware(Khoa, mat_khau=mk)
    return mk


def sinh_mat_khau() -> str:
    """Mật khẩu ngẫu nhiên, đủ ngắn để đọc qua điện thoại cho khách."""
    return secrets.token_urlsafe(9)
