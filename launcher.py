# -*- coding: utf-8 -*-
"""Bật ứng dụng: chạy máy chủ rồi mở một cửa sổ ứng dụng thật.

Cửa sổ dựng bằng chế độ `--app` của Edge/Chrome nên không có thanh địa chỉ,
không tab, có mục riêng trên thanh tác vụ — nhìn ra là một phần mềm chứ không
phải một trang web. Máy nào không có trình duyệt nhân Chromium thì lui về
trình duyệt mặc định, vẫn dùng được đầy đủ, chỉ khác cái vỏ.
"""
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

GOC = Path(__file__).resolve().parent
if str(GOC) not in sys.path:
    sys.path.insert(0, str(GOC))

from app import config     # noqa: E402  (phải nằm sau khi chỉnh sys.path)

TEN = "Mastering"


def _cong_ranh(cong: int) -> int:
    """Tìm cổng trống bắt đầu từ `cong`. Mở hai lần app thì lần sau tự nhảy cổng."""
    for c in range(cong, cong + 20):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", c)) != 0:
                return c
    return cong


def _cho_may_chu(cong: int, han_giay: float = 40.0) -> bool:
    het = time.time() + han_giay
    while time.time() < het:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", cong)) == 0:
                return True
        time.sleep(0.2)
    return False


def _mo_cua_so(dia_chi: str):
    ung_vien = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    ho_so = str(config.DATA / "cua_so")     # hồ sơ riêng, khỏi đụng tab của người dùng
    for exe in ung_vien:
        if os.path.exists(exe):
            # Hồ sơ riêng còn một tác dụng nữa: tiến trình này KHÔNG bàn giao
            # cho cửa sổ Edge đang mở sẵn của người dùng, nên nó sống đúng bằng
            # tuổi thọ cửa sổ app — nhờ vậy mới chờ được nó đóng.
            return subprocess.Popen([
                exe, f"--app={dia_chi}", f"--user-data-dir={ho_so}",
                "--no-first-run", "--no-default-browser-check",
                "--window-size=1280,860",
            ])
    webbrowser.open(dia_chi)
    return None


def main():
    import uvicorn
    from app.api import app

    cong = _cong_ranh(config.PORT)
    dia_chi = f"http://127.0.0.1:{cong}/"

    def chay():
        uvicorn.run(app, host="127.0.0.1", port=cong, log_level="warning")

    threading.Thread(target=chay, daemon=True).start()

    print(f"{TEN} — {dia_chi}")
    if not _cho_may_chu(cong):
        print("Máy chủ không lên được. Xem thông báo lỗi phía trên.")
        return
    cua_so = _mo_cua_so(dia_chi)

    # Đóng cửa sổ là tắt hẳn. Không có chỗ này thì máy chủ sống ngầm mãi: lần
    # sau bấm Run.bat, cổng cũ đang bận nên app nhảy sang cổng khác, và người
    # dùng tích dần một đống tiến trình python không ai biết.
    try:
        if cua_so is not None:
            bat_dau = time.time()
            cua_so.wait()
            # Thoát trong vài giây đầu thì KHÔNG phải người dùng đóng app.
            #
            # Chuyện thật gặp phải: bật lại app ngay sau khi vừa tắt, tiến
            # trình Edge cũ còn đang dọn hồ sơ, nên tiến trình mới giao việc
            # cho nó rồi tự thoát ngay lập tức. Cửa sổ vẫn hiện ra bình thường
            # nhưng cái ta chờ đã chết — và máy chủ tắt theo trong khi người
            # dùng đang nhìn vào giao diện.
            if time.time() - bat_dau < 5:
                print("Không theo dõi được cửa sổ (Edge giao lại cho tiến trình"
                      " sẵn có). Đóng cửa sổ lệnh này để tắt hẳn.")
                while True:
                    time.sleep(1)
        else:
            # Lui về trình duyệt mặc định thì không theo dõi được cửa sổ nào cả,
            # đành giữ tiến trình sống cho tới khi người dùng đóng cửa sổ lệnh.
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
