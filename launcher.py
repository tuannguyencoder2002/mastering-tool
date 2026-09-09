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


def _sua_console():
    """Sửa đầu ra TRƯỚC khi in bất cứ thứ gì. Hai chuyện khác nhau phải lo:

    1. Chạy có cửa sổ lệnh: console Windows mặc định là cp1252, in một chữ có
       dấu là UnicodeEncodeError làm SẬP CẢ TIẾN TRÌNH — và máy chủ chết theo.
       Đã gặp thật: app mở lên, hiện cửa sổ, rồi tắt ngóm không rõ lý do.
    2. Chạy bằng pythonw.exe (khi mở từ file .exe): KHÔNG có console, sys.stdout
       là None. Mọi thông báo biến mất, nên khi trục trặc thì không còn manh mối
       nào để lần -> ghi một bản ra data\khoi-dong.log.
    """
    for ten in ("stdout", "stderr"):
        luong = getattr(sys, ten, None)
        if luong is None:
            continue
        try:
            luong.reconfigure(encoding="utf-8", errors="replace",
                              line_buffering=True)
        except (AttributeError, ValueError):
            pass

    if sys.stdout is None or sys.stderr is None:
        try:
            (GOC / "data").mkdir(parents=True, exist_ok=True)
            log = open(GOC / "data" / "khoi-dong.log", "w",
                       encoding="utf-8", errors="replace")
            if sys.stdout is None:
                sys.stdout = log
            if sys.stderr is None:
                sys.stderr = log
        except OSError:
            pass


_sua_console()

from app import config     # noqa: E402  (phải nằm sau khi chỉnh sys.path)

TEN = "Mastering"


BAO_HIEU = "dia-chi.txt"


def _bao_len(dia_chi: str, mo_duoc: bool):
    """Báo cho vỏ .exe biết app đã lên, để nó cất màn hình chờ đi.

    Vỏ .exe không đoán được cổng (app tự nhảy cổng khi cổng cũ bận), nên nó chờ
    đúng một tín hiệu: file này xuất hiện. Không có tín hiệu mà tiến trình con
    còn sống thì nó cứ hiện "đang khởi động".
    """
    try:
        (config.DATA).mkdir(parents=True, exist_ok=True)
        (config.DATA / BAO_HIEU).write_text(
            ("" if mo_duoc else "MANUAL ") + dia_chi, encoding="utf-8")
    except OSError:
        pass


def _don_bao_hieu():
    try:
        (config.DATA / BAO_HIEU).unlink()
    except OSError:
        pass


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


def _tim_trinh_duyet():
    """Mọi chỗ Edge/Chrome có thể nằm, KHÔNG viết cứng ổ C.

    Bản trước chỉ dò bốn đường dẫn cố định dưới C:\Program Files. Chrome cài
    cho một người dùng thì nằm trong %LOCALAPPDATA%, và máy dựng Windows ở ổ
    khác thì cả bốn đường dẫn kia đều trượt — app lui về trình duyệt mặc định,
    hoặc không mở được gì cả.
    """
    thu_muc = [os.environ.get("PROGRAMFILES(X86)"),
               os.environ.get("PROGRAMFILES"),
               os.environ.get("LOCALAPPDATA")]
    duoi = [r"Microsoft\Edge\Application\msedge.exe",
            r"Google\Chrome\Application\chrome.exe",
            r"BraveSoftware\Brave-Browser\Application\brave.exe"]
    ra = []
    for tm in thu_muc:
        if not tm:
            continue
        for d in duoi:
            ra.append(os.path.join(tm, d))
    return ra


def _mo_cua_so(dia_chi: str):
    ung_vien = _tim_trinh_duyet()
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
    # Không có trình duyệt nhân Chromium: mở bằng trình duyệt mặc định. Trả về
    # False nếu cả cái đó cũng không mở được, để chỗ gọi còn báo cho người dùng
    # địa chỉ mà tự mở tay — im lặng ở đây là khách nhìn vào màn hình trống.
    try:
        return None if webbrowser.open(dia_chi) else False
    except Exception:
        return False


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
        raise SystemExit(1)
    cua_so = _mo_cua_so(dia_chi)
    _bao_len(dia_chi, cua_so is not False)

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
    # Bọc kín: mọi lỗi phải rơi vào stderr, vì vỏ .exe hứng stderr và bày ra hộp
    # thoại. Để lọt một lỗi ở đây là app chết câm — nháy đúp không thấy gì.
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stderr.flush()
        raise SystemExit(1)
    finally:
        _don_bao_hieu()
