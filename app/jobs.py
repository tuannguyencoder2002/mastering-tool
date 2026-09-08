# -*- coding: utf-8 -*-
"""Hàng đợi việc chạy nền.

Vì sao cần: căn một bài mất vài chục giây tới vài phút. Chạy thẳng trong
request thì trình duyệt treo và hết giờ chờ. Ta trả mã việc ngay, rồi giao
diện hỏi tiến độ mỗi giây.
"""
import threading
import traceback
import uuid
from typing import Any, Callable, Dict

_viec: Dict[str, dict] = {}
_khoa = threading.Lock()

# Chỉ chạy MỘT việc một lúc: cả Demucs lẫn wav2vec2 đều ăn VRAM, chạy song song
# trên card 4 GB là tràn bộ nhớ ngay.
_cho_chay = threading.Semaphore(1)


def tao() -> str:
    ma = uuid.uuid4().hex[:12]
    with _khoa:
        _viec[ma] = {"id": ma, "trang_thai": "queued", "tien_do": 0.0,
                     "thong_bao": "Queued", "ket_qua": None, "loi": None}
    return ma


def _dat(ma: str, **kw):
    with _khoa:
        if ma in _viec:
            _viec[ma].update(kw)


def xem(ma: str):
    with _khoa:
        v = _viec.get(ma)
        return dict(v) if v else None


def chay(ma: str, ham: Callable[[Callable[[float, str], None]], Any]):
    """Chạy `ham` trong luồng riêng. `ham` nhận một hàm báo tiến độ."""

    def bao(p: float, m: str):
        _dat(ma, tien_do=max(0.0, min(1.0, float(p))), thong_bao=m)

    def than():
        with _cho_chay:
            _dat(ma, trang_thai="running", thong_bao="Starting")
            try:
                kq = ham(bao)
                _dat(ma, trang_thai="done", tien_do=1.0, thong_bao="Done", ket_qua=kq)
            except Exception as e:
                _dat(ma, trang_thai="error", loi=f"{e.__class__.__name__}: {e}",
                     thong_bao="Failed")
                traceback.print_exc()

    threading.Thread(target=than, daemon=True).start()
