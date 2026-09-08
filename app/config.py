# -*- coding: utf-8 -*-
"""Cấu hình dùng chung."""
import os
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
DATA = GOC / "data"
UPLOAD = DATA / "upload"
WORK = DATA / "work"        # stem tách ra, cache theo mã băm file
OUT = DATA / "out"
CACHE = DATA / "cache"
REF = DATA / "reference"    # bài mẫu để so phổ khi master

for _p in (UPLOAD, WORK, OUT, CACHE, REF):
    _p.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("TORCH_HOME", str(CACHE))

SR = 44100                  # cả dây chuyền chạy ở 44.1 kHz
DEMUCS_SEGMENT = float(os.environ.get("DEMUCS_SEGMENT", "7.8"))

# Nhịp điều khiển của máy nén/máy hạn: tính hệ số khuếch đại mỗi 32 mẫu thay vì
# từng mẫu. 32 mẫu là 0,73 ms — nhanh hơn mọi hằng số thời gian ta dùng, tai
# không phân biệt được, mà tránh được vòng lặp 10 triệu bước trong Python.
NHIP = 32

PORT = int(os.environ.get("PORT", "8771"))
