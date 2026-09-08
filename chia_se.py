# -*- coding: utf-8 -*-
"""Mở app Mastering ra ngoài Internet để khách vào thử, qua đường hầm Cloudflare.

    runtime\\tunnel\\cloudflared.exe  --url http://127.0.0.1:<cổng>

Vì sao là đường hầm chứ không phải đưa lên máy chủ thuê: tool này cần GPU và
mang theo hơn 3 GB thư viện. Thuê một máy chủ có GPU chỉ để khách bấm thử vài
bài là tốn tiền và mất cả buổi dựng. Đường hầm thì app vẫn chạy trên máy này,
Cloudflare chỉ làm chỗ trung chuyển, và tắt cửa sổ là hết.

Mặc định KHÔNG khoá: địa chỉ do Cloudflare sinh ngẫu nhiên, gửi riêng cho một
khách trong một buổi thử thì thêm bước gõ mật khẩu chỉ làm phiền họ.

Cần khoá thì thêm tham số --khoa. Nên dùng khi gửi cho nhiều người, hoặc khi
để hầm mở lâu: app nhận file tải lên và chạy GPU, ai có địa chỉ là dùng được.
"""
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

GOC = Path(__file__).resolve().parent
if str(GOC) not in sys.path:
    sys.path.insert(0, str(GOC))


def _sua_console():
    for luong in (sys.stdout, sys.stderr):
        try:
            # line_buffering: không có thì Python gom stdout lại khi ghi ra
            # pipe, và ĐỊA CHỈ CHO KHÁCH nằm kẹt trong bộ đệm — chương trình
            # vẫn chạy đúng nhưng người dùng không thấy gì để mà gửi đi.
            luong.reconfigure(encoding="utf-8", errors="replace",
                              line_buffering=True)
        except (AttributeError, ValueError):
            pass


_sua_console()

CLOUDFLARED = GOC / "runtime" / "tunnel" / "cloudflared.exe"


def _cong_ranh(cong: int) -> int:
    for c in range(cong, cong + 20):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", c)) != 0:
                return c
    return cong


def _cho_may_chu(cong: int, han: float = 60.0) -> bool:
    het = time.time() + han
    while time.time() < het:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", cong)) == 0:
                return True
        time.sleep(0.3)
    return False


def main():
    if not CLOUDFLARED.exists():
        print("Thiếu cloudflared.exe. Tải về rồi đặt vào:")
        print(f"  {CLOUDFLARED}")
        print("  https://github.com/cloudflare/cloudflared/releases/latest"
              "/download/cloudflared-windows-amd64.exe")
        return

    from app import khoa

    # Mật khẩu sinh mới mỗi lần mở, chứ không cố định trong file: đường hầm chỉ
    # sống vài tiếng, hết buổi thử là mật khẩu cũ thành vô dụng — đúng ý muốn.
    co_khoa = "--khoa" in sys.argv
    mat_khau = ""
    if co_khoa:
        mat_khau = os.environ.get("MASTERING_PASS") or khoa.sinh_mat_khau()
        os.environ["MASTERING_PASS"] = mat_khau
    else:
        os.environ.pop("MASTERING_PASS", None)

    from app import config
    from app.api import app as ung_dung
    import uvicorn

    cong = _cong_ranh(config.PORT)

    def chay():
        uvicorn.run(ung_dung, host="127.0.0.1", port=cong, log_level="warning")

    threading.Thread(target=chay, daemon=True).start()
    print(f"Máy chủ đang lên ở cổng {cong}...")
    if not _cho_may_chu(cong):
        print("Máy chủ không lên được.")
        return

    print("Đang mở đường hầm...\n")
    p = subprocess.Popen(
        [str(CLOUDFLARED), "tunnel", "--url", f"http://127.0.0.1:{cong}",
         "--no-autoupdate"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )

    # Cloudflare in địa chỉ ra giữa một đống dòng nhật ký. Bắt đúng dòng ấy rồi
    # in lại cho gọn, thay vì bắt người dùng tự dò trong log.
    dia_chi = None
    mau = re.compile(r"https://[-a-z0-9]+\.trycloudflare\.com")
    for dong in p.stdout:
        m = mau.search(dong)
        if m and not dia_chi:
            dia_chi = m.group(0)
            print("=" * 60)
            print("  GỬI CHO KHÁCH HAI DÒNG NÀY:")
            print()
            print(f"    {dia_chi}")
            print()
            if co_khoa:
                print(f"    Tài khoản  khach")
                print(f"    Mật khẩu   {mat_khau}")
                print()
            print("=" * 60)
            print()
            print("  Đóng cửa sổ này là đường hầm đóng theo, khách không vào")
            print("  được nữa. Máy phải bật và app phải chạy suốt buổi thử.")
            print()
            # Mở luôn cửa sổ dùng tại chỗ. Chia sẻ cho khách không có nghĩa là
            # mình mất bản của mình — mà chạy hai máy chủ song song chỉ để có
            # cả hai thì tốn thêm một lượt nạp model vào GPU.
            try:
                import launcher
                launcher._mo_cua_so(f"http://127.0.0.1:{cong}/")
                print("  Cửa sổ trên máy này cũng đã mở.")
                print()
            except Exception as e:
                print(f"  (không mở được cửa sổ tại chỗ: {e})")
        elif dia_chi and ("ERR" in dong or "error" in dong.lower()):
            print(f"  [hầm] {dong.strip()}")

    p.wait()


if __name__ == "__main__":
    main()
