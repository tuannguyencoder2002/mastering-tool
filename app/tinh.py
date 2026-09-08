# -*- coding: utf-8 -*-
"""Phục vụ file tĩnh, có khai báo bộ nhớ đệm đàng hoàng.

VÌ SAO KHÔNG DÙNG THẲNG StaticFiles:

Bản gốc chỉ gửi `etag` và `last-modified`, không gửi `Cache-Control`. Thiếu
`Cache-Control` thì trình duyệt được phép TỰ SUY ĐOÁN thời gian giữ đệm — quy
tắc thông dụng là 10% khoảng thời gian kể từ lần sửa cuối. File sửa cách đây
một ngày thì nó giữ đệm hơn hai tiếng mà không hỏi lại máy chủ lần nào.

Hậu quả gặp thật: sửa xong giao diện, mở app lên vẫn thấy bản cũ y nguyên, và
không có dấu hiệu gì cho biết vì sao. Nguy hơn nữa là khi khách đang dùng qua
đường hầm — họ báo lỗi đã sửa rồi, mà mình không hiểu tại sao.

Cách chữa: bắt trình duyệt HỎI LẠI mỗi lần. Nhờ có etag nên hỏi lại rất rẻ —
file không đổi thì máy chủ trả 304 rỗng, không truyền lại nội dung.

Riêng phông chữ thì cho giữ đệm lâu: nó không bao giờ đổi, mà lại nặng nhất.
"""
from starlette.staticfiles import StaticFiles

# Phông và ảnh: giữ một năm. Đổi phông thì đổi luôn tên file.
LAU = {".woff2", ".woff", ".ttf", ".png", ".jpg", ".svg", ".ico"}


class FileTinh(StaticFiles):
    async def get_response(self, path, scope):
        tra = await super().get_response(path, scope)
        duoi = ("." + path.rsplit(".", 1)[-1].lower()) if "." in path else ""
        if duoi in LAU:
            tra.headers["cache-control"] = "public, max-age=31536000, immutable"
        else:
            # no-cache KHÔNG có nghĩa là "đừng lưu" — nó nghĩa là "lưu đi,
            # nhưng lần nào cũng phải hỏi lại xem còn mới không".
            tra.headers["cache-control"] = "no-cache, must-revalidate"
        return tra
