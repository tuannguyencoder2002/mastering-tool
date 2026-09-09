# -*- coding: utf-8 -*-
"""Nhận file tải lên theo từng phần.

VÌ SAO PHẢI CHIA PHẦN:

Khi app được mở ra ngoài qua đường hầm Cloudflare, gói miễn phí **cắt mọi
request sau 100 giây**, không có cách nào nâng (chỉ gói Enterprise mới đổi
được). Một file WAV 32 MB trên đường tải lên 2 Mbps mất 132 giây -> bị cắt
giữa đường, khách nhận về lỗi 524 mà không hiểu vì sao.

Chia thành từng phần 4 MB thì mỗi phần là một request riêng, mỗi cái chỉ mất
vài giây. Không bao giờ chạm mốc 100 giây, bất kể file lớn cỡ nào và mạng
khách nhanh chậm ra sao.

Đổi lại còn được một thứ nữa: biết được đã tải xong bao nhiêu phần trăm, nên
hiện được thanh tiến độ thật thay vì để người dùng nhìn màn hình đứng im.
"""
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile

# Trần cho một file. Bài dài nhất người ta gửi tới là WAV 24-bit vài chục phút,
# nên 800 MB là thoải mái, mà vẫn chặn được người thả nhầm cả thư mục vào.
TRAN_FILE = 800 * 1024 * 1024
# Trần cho một phần. Khách hàng gửi 4 MB; đặt trần 16 MB để còn chỗ xoay xở.
TRAN_KHOI = 16 * 1024 * 1024
# Bỏ những lượt tải dở dang quá lâu, kẻo file rác nằm lại mãi trên đĩa.
HAN_DO_DANG = 2 * 3600

_dang_tai: dict = {}


def _don_rac():
    het = time.time() - HAN_DO_DANG
    for ma in [m for m, v in _dang_tai.items() if v["luc"] < het]:
        v = _dang_tai.pop(ma, None)
        if v:
            Path(v["duong"]).unlink(missing_ok=True)


def _ten_an_toan(ten: str) -> str:
    """Chỉ giữ phần tên file, bỏ mọi thành phần đường dẫn.

    Không có bước này thì tên "..\\..\\Windows\\System32\\x.dll" ghi được ra
    ngoài thư mục upload. Khi app chỉ chạy ở máy nhà thì chuyện đó vô hại,
    nhưng đúng cái app này lại được mở ra Internet cho khách vào.
    """
    ten = Path(ten or "audio").name
    return ten or "audio"


def nhan_khoi(thu_muc: Path, ma: str, chi_so: int, tong: int,
              ten: str, du_lieu: bytes) -> dict:
    """Ghi thêm một phần vào file đang tải. Trả về {'ma', 'da_nhan', 'xong'}."""
    if len(du_lieu) > TRAN_KHOI:
        raise HTTPException(413, "Chunk too large.")
    if tong < 1 or chi_so < 0 or chi_so >= tong:
        raise HTTPException(400, "Bad chunk index.")

    _don_rac()

    if not ma:
        if chi_so != 0:
            raise HTTPException(400, "First chunk must be index 0.")
        ma = uuid.uuid4().hex[:12]
        thu_muc.mkdir(parents=True, exist_ok=True)
        duong = thu_muc / f"{ma}_{_ten_an_toan(ten)}"
        _dang_tai[ma] = {"duong": str(duong), "cho": 0, "tong": tong,
                         "co": 0, "luc": time.time()}

    v = _dang_tai.get(ma)
    if not v:
        raise HTTPException(404, "Unknown upload — start over.")

    # Đòi đúng thứ tự. Cho phép gửi lẫn lộn thì phải giữ từng phần ra file
    # riêng rồi ghép, phức tạp hơn nhiều mà chẳng được gì: trình duyệt gửi
    # tuần tự, và gửi song song trên một đường lên thì cũng không nhanh hơn.
    if chi_so != v["cho"]:
        raise HTTPException(409, f"Expected chunk {v['cho']}, got {chi_so}.")

    if v["co"] + len(du_lieu) > TRAN_FILE:
        Path(v["duong"]).unlink(missing_ok=True)
        _dang_tai.pop(ma, None)
        raise HTTPException(413, "File too large.")

    with open(v["duong"], "ab") as f:
        f.write(du_lieu)
    v["co"] += len(du_lieu)
    v["cho"] += 1
    v["luc"] = time.time()

    xong = v["cho"] >= v["tong"]
    return {"ma": ma, "da_nhan": v["cho"], "tong": v["tong"], "xong": xong}


def lay_duong(ma: str) -> Path:
    """Đường dẫn file đã tải xong. Gọi khi bắt đầu chạy việc."""
    v = _dang_tai.get(ma)
    if not v:
        raise HTTPException(404, "Upload not found — upload the file again.")
    if v["cho"] < v["tong"]:
        raise HTTPException(400, "Upload not finished.")
    return Path(v["duong"])


async def lay_file(thu_muc: Path, ma: Optional[str], tep: Optional[UploadFile],
                   tien_to: str) -> Path:
    """Nhận file từ HAI đường: đã tải theo phần (`ma`), hoặc gửi thẳng (`tep`).

    Giữ cả đường gửi thẳng vì file nhỏ thì chia phần chỉ thêm vòng vo, và vì
    còn dùng để thử bằng dòng lệnh.
    """
    if ma:
        return lay_duong(ma)
    if tep is not None and tep.filename:
        import shutil
        thu_muc.mkdir(parents=True, exist_ok=True)
        dich = thu_muc / f"{tien_to}_{_ten_an_toan(tep.filename)}"
        with open(dich, "wb") as f:
            shutil.copyfileobj(tep.file, f)
        return dich
    raise HTTPException(400, "No audio file.")
