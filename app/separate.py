# -*- coding: utf-8 -*-
"""Tách giọng hát khỏi nhạc nền bằng Demucs.

Vì sao bắt buộc phải tách: model nhận âm vị được huấn luyện trên tiếng nói
sạch. Đưa cả bản phối vào thì trống và bass lấn phổ, xác suất âm vị nhoè ra,
và mốc thời gian lệch — đây là nguyên nhân số một làm hỏng căn lời.

Máy 4 GB VRAM: Demucs chạy theo lát cắt nhỏ (DEMUCS_SEGMENT) nên không tràn.
Ta còn cắt thêm một tầng ngoài để báo được tiến độ và để RAM không phình theo
độ dài bài.
"""
import hashlib
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import torch

from . import config
from . import audio as A

_model = None

# Lát ngoài dài 60 s, chồng lấn 3 s rồi trộn chéo. Chồng lấn để mối nối không
# nghe thấy; 3 s là thừa sức vì Demucs chỉ nhìn quanh vài trăm mili giây.
LAT_NGOAI = 60.0
CHONG_LAN = 3.0


def _hon_hop(dev: str):
    """Chế độ tính hỗn hợp: phép nào an toàn thì chạy nửa độ chính xác.

    Đo trên card RTX 3050: NHANH GẤP 2,27 LẦN (3,54s -> 1,56s cho đoạn 30
    giây), sai lệch so với bản đầy đủ là -62 dB dưới tín hiệu — dưới ngưỡng
    tai nghe ra.

    Vì sao là autocast chứ không phải model.half(): htdemucs làm biến đổi
    Fourier, mà số phức nửa độ chính xác trong PyTorch còn ở dạng thử nghiệm —
    ép .half() là văng "expected scalar type Float but found Half". autocast
    thì để riêng những phép ấy ở fp32.

    ĐÃ THỬ VÀ LOẠI: giảm chồng lấn giữa các lát (overlap 0.25 -> 0.10) cũng
    nhanh tương đương, nhưng sai lệch tới -24 dB, tức NGHE RA ĐƯỢC. Nhanh mà
    đổi cả chất tiếng thì không phải tối ưu, là đánh đổi.
    """
    import contextlib
    if dev != "cuda" or not config.NUA_DO_CHINH_XAC:
        return contextlib.nullcontext()
    return torch.autocast("cuda", dtype=torch.float16)


def thiet_bi() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def _tai_model():
    global _model
    if _model is None:
        from demucs.pretrained import get_model
        _model = get_model("htdemucs")
        _model.eval()
    return _model


def _ma_bam(duong_dan: Path) -> str:
    """Mã băm theo nội dung file, để tách rồi thì lần sau dùng lại."""
    h = hashlib.sha1()
    with open(duong_dan, "rb") as f:
        while True:
            khoi = f.read(1 << 20)
            if not khoi:
                break
            h.update(khoi)
    return h.hexdigest()[:16]


def tach_giong(
    duong_dan: Path,
    bao_tien_do: Optional[Callable[[float, str], None]] = None,
    giu_nhac_nen: bool = True,
) -> dict:
    """Trả về {'vocals': Path, 'no_vocals': Path|None, 'sr': 44100}.

    Kết quả nằm trong data/work/<mã băm>/ nên chạy lại cùng file là lấy ngay.
    """
    ma = _ma_bam(duong_dan)
    thu_muc = config.WORK / ma
    thu_muc.mkdir(parents=True, exist_ok=True)
    f_vocal = thu_muc / "vocals.wav"
    f_nhac = thu_muc / "no_vocals.wav"

    xong = f_vocal.exists() and (f_nhac.exists() or not giu_nhac_nen)
    if xong:
        if bao_tien_do:
            bao_tien_do(1.0, "Separation cached")
        return {"vocals": f_vocal, "no_vocals": f_nhac if f_nhac.exists() else None,
                "sr": config.SR}

    from demucs.apply import apply_model

    model = _tai_model()
    dev = thiet_bi()
    model.to(dev)

    x = A.doc(str(duong_dan), config.SR, mono=False)   # (2, N)
    tong = x.shape[1]
    buoc = int(LAT_NGOAI * config.SR)
    chong = int(CHONG_LAN * config.SR)

    voc = np.zeros_like(x)
    nen = np.zeros_like(x) if giu_nhac_nen else None
    trong_so = np.zeros(tong, dtype=np.float32)

    # Danh sách chỉ số các stem: htdemucs cho ra drums/bass/other/vocals.
    ten_stem = model.sources
    i_voc = ten_stem.index("vocals")

    dau = 0
    while dau < tong:
        cuoi = min(dau + buoc, tong)
        # Mở rộng hai bên để có phần chồng lấn
        a = max(0, dau - chong)
        b = min(tong, cuoi + chong)
        lat = torch.from_numpy(x[:, a:b]).to(dev)

        # Chuẩn hoá theo lát: Demucs nhạy với mức vào, lệch mức thì tách kém.
        tb = lat.mean(0, keepdim=True).mean()
        do_lech = lat.std() + 1e-8
        lat = (lat - tb) / do_lech

        with torch.no_grad(), _hon_hop(dev):
            ra = apply_model(
                model, lat[None], shifts=0, split=True, overlap=0.25,
                device=dev, segment=config.DEMUCS_SEGMENT, progress=False,
            )[0]
        ra = ra * do_lech + tb

        v = ra[i_voc].cpu().numpy()
        n = (ra.sum(0) - ra[i_voc]).cpu().numpy() if giu_nhac_nen else None

        # Cửa sổ trộn chéo: lên dần ở mép trái, xuống dần ở mép phải.
        L = b - a
        w = np.ones(L, dtype=np.float32)
        if a > 0:
            k = min(chong, L)
            w[:k] = np.linspace(0.0, 1.0, k, dtype=np.float32)
        if b < tong:
            k = min(chong, L)
            w[-k:] = np.linspace(1.0, 0.0, k, dtype=np.float32)

        voc[:, a:b] += v * w
        if giu_nhac_nen:
            nen[:, a:b] += n * w
        trong_so[a:b] += w

        dau = cuoi
        if bao_tien_do:
            bao_tien_do(min(0.999, cuoi / tong), "Separating vocals")

    trong_so[trong_so < 1e-6] = 1.0
    voc /= trong_so
    A.ghi(str(f_vocal), voc, config.SR)
    if giu_nhac_nen:
        nen /= trong_so
        A.ghi(str(f_nhac), nen, config.SR)

    if dev == "cuda":
        torch.cuda.empty_cache()
    if bao_tien_do:
        bao_tien_do(1.0, "Separation done")
    return {"vocals": f_vocal, "no_vocals": f_nhac if giu_nhac_nen else None,
            "sr": config.SR}
