# -*- coding: utf-8 -*-
"""Tự chọn mức cho từng thanh kéo, dựa trên số đo của chính bài đó.

Nguyên tắc của cả file này: KHÔNG có ngưỡng nào chọn bằng cảm nhận. Mọi mốc
đều là trung vị đo được trên năm bản mix của khách, và mọi hiệu chỉnh đều
  - chỉ bù MỘT NỬA khoảng lệch, và
  - bị chặn biên.
Hai chuyện đó là cố ý. Khách nói "chỉnh quá tay là dễ hỏng nhạc", mà một luật
tự động chỉnh tới nơi tới chốn thì gặp bài lạ là nó phá. Bù nửa và chặn biên
làm cái xấu nhất có thể xảy ra vẫn là một chỉnh sửa nhẹ.

Chia hai đợt vì lý do kỹ thuật, không phải vì thẩm mỹ:
  - nhóm MASTER đo thẳng trên bản phối, mất chừng hai giây
  - nhóm VOCAL phải có track giọng tách riêng mới đo được, mà tách stem mất
    20-30 giây, nên nó đi kèm lúc xử lý chứ không lúc nhập file
"""
from typing import Optional

import numpy as np

from . import config, dsp
from . import audio as A


# Hồ sơ chuẩn, đặt tên được.
#
# Hiện chỉ có MỘT hồ sơ, đo từ năm bản mix rap/hip-hop của khách. Đó là giới
# hạn thật và phải nói thẳng: tool đang được căn cho dòng nhạc đó. Bài thuộc
# dòng khác vẫn chạy được vì mọi hiệu chỉnh đều bù nửa và chặn biên, nhưng nó
# chỉnh chưa tối ưu chứ không phải chỉnh đúng.
#
# Vì sao chưa có bộ phân loại thể loại: phân loại xong thì áp mốc nào? Muốn có
# hồ sơ cho ballad hay EDM thì phải có chừng năm bài đã master của dòng đó để
# đo, chứ bản thân việc đoán tên thể loại không sinh ra con số nào cả. Dựng
# sẵn chỗ này để hôm nào có dữ liệu thì chỉ thêm một khoá, không phải sửa
# kiến trúc.
HO_SO = {}

# Trung vị đo trên năm bản mix của khách. Xem scratchpad/do_chuan.py.
# Con số trong ngoặc là độ lệch chuẩn giữa năm bài — dùng để biết lệch bao
# nhiêu thì mới đáng chỉnh.
HO_SO["rap"] = {
    "tram": 18.62,        # dải 50-120 Hz so với 300-3000 Hz  (lệch chuẩn 2,18)
    "cao": -15.70,        # dải 8-16 kHz so với 300-3000 Hz   (2,56)
    "rong_mix": 0.355,    # bề rộng bản phối                  (0,104)
    "muc_giong": 0.34,    # giọng so với nhạc nền, LUFS       (2,16)
    "rong_giong": 0.219,  # bề rộng track giọng               (0,030)
    "net": -12.02,        # dải 3-5 kHz của giọng             (1,96)
    "xi": -14.17,         # dải 5,5-9,5 kHz của giọng         (2,71)
}

HO_SO_MAC_DINH = "rap"
CHUAN = HO_SO[HO_SO_MAC_DINH]


def _dai(x, sr, lo, hi) -> float:
    """Mức trung bình trong một dải tần, dB, chỉ tính nửa to hơn của bài.

    Bỏ nửa nhỏ đi vì đoạn lặng và đoạn intro mỏng kéo lệch mọi phép đo phổ;
    cái ta cần là dáng phổ lúc bài đang chạy thật.
    """
    mono = x.mean(axis=0)
    n = 1 << 14
    cua = np.hanning(n)
    khung = list(range(0, max(1, len(mono) - n), n))
    if not khung:
        return -120.0
    nang = np.array([np.sqrt(np.mean(mono[i:i + n] ** 2)) for i in khung])
    chon = [i for i, e in zip(khung, nang) if e >= np.percentile(nang, 50)]
    tich = np.zeros(n // 2 + 1)
    for i in chon:
        tich += np.abs(np.fft.rfft(mono[i:i + n] * cua)) ** 2
    tich /= max(len(chon), 1)
    f = np.fft.rfftfreq(n, 1 / sr)
    m = (f >= lo) & (f < hi)
    return float(10 * np.log10(tich[m].mean() + 1e-20)) if m.any() else -120.0


def _rong(x) -> float:
    if x.shape[0] < 2:
        return 0.0
    g = (x[0] + x[1]) / 2
    b = (x[0] - x[1]) / 2
    return float(np.sqrt(np.mean(b ** 2)) / (np.sqrt(np.mean(g ** 2)) + 1e-12))


def _chan(v, lo, hi, buoc=0.5):
    return float(np.clip(round(v / buoc) * buoc, lo, hi))


# Khoảng mà luật còn đáng tin. Ngoài khoảng này thì không phải "bài lệch" nữa
# mà là "phép đo không còn nghĩa gì" — hai chuyện khác hẳn nhau, và chặn biên
# chỉ chữa được chuyện thứ nhất.
#
# Năm bài dùng để căn có mức giọng so với nhạc nền nằm trong -3,5 … +2,4 dB.
# Lấy biên rộng gấp bốn lần khoảng đó: ra ngoài -12 … +12 thì gần như chắc
# chắn không phải một bản phối có cả giọng lẫn nhạc.
GIONG_MIN, GIONG_MAX = -12.0, 12.0

# Track giọng nhỏ hơn cả bản phối chừng này thì coi như bài không có lời —
# cái Demucs tách ra chỉ là tiếng rò rỉ từ nhạc cụ.
NGUONG_KHONG_LOI = 25.0

# Bề rộng dưới mức này thì file coi như mono.
NGUONG_MONO = 0.02

# Ngắn hơn chừng này thì không đủ cửa sổ để đo phổ cho ra hồn.
GIAY_TOI_THIEU = 20.0


def _bu_nua(do_duoc, moc, chet, gioi_han):
    """Bù một nửa khoảng lệch, bỏ qua nếu lệch chưa đáng kể, rồi chặn biên."""
    lech = do_duoc - moc
    if abs(lech) < chet:
        return 0.0
    return _chan(-lech / 2.0, -gioi_han, gioi_han)


# ------------------------------------------------------------ đợt 1: bản phối

def phan_tich_mix(duong_dan) -> dict:
    """Đo bản phối, trả về số đo và mức đề nghị cho nhóm MASTER.

    Trả về `bo_qua` kèm lý do khi phép đo không đáng tin. Lúc đó KHÔNG đề nghị
    gì cả, thanh kéo giữ nguyên mặc định. Đưa ra một con số bịa rồi chặn biên
    cho nó trông hợp lý là tệ hơn nhiều so với nói thẳng "bài này tôi không đo
    được".
    """
    sr = config.SR
    x = A.doc(str(duong_dan), sr, mono=False)

    giay = x.shape[-1] / sr
    dinh = float(np.max(np.abs(x))) if x.size else 0.0
    if giay < GIAY_TOI_THIEU:
        return {"do": {"giay": round(giay, 1)}, "thanh": {},
                "bo_qua": f"track is only {giay:.0f}s — too short to measure"}
    if dinh < 1e-4:
        return {"do": {}, "thanh": {}, "bo_qua": "track is silent"}

    giua = _dai(x, sr, 300, 3000)
    tram = _dai(x, sr, 50, 120) - giua
    cao = _dai(x, sr, 8000, 16000) - giua
    rong = _rong(x)
    lufs = dsp.do_lufs(x, sr)
    dr = dsp.do_dai_dong(x, sr)
    tp = dsp.dinh_lien_mau_db(x)

    # Bề rộng: MasteringBox đo được gần như KHÔNG đụng tới (thay đổi +0,01 trên
    # năm bài), nên mặc định để yên. Chỉ nhúc nhích khi bản phối lệch hẳn ra
    # ngoài khoảng quan sát được (0,187 … 0,395).
    # File mono thì bề rộng bằng 0, và nới rộng một thứ không có hai kênh thì
    # chẳng ra gì. Để yên.
    if rong < NGUONG_MONO:
        w = 100.0
    elif rong < 0.15:
        w = 112.0
    elif rong > 0.45:
        w = 92.0
    else:
        w = 100.0

    return {
        "do": {
            "lufs": round(lufs, 2), "dr": round(dr, 2), "tp": round(tp, 2),
            "tram": round(tram, 2), "cao": round(cao, 2), "rong": round(rong, 3),
        },
        "thanh": {
            # Vùng chết 1 dB: dưới mức đó thì chênh lệch nằm trong sai số đo và
            # trong dao động bình thường giữa các bài, chỉnh vào là nhiễu.
            "bass": _bu_nua(tram, CHUAN["tram"], 1.0, 2.0),
            "air": _bu_nua(cao, CHUAN["cao"], 1.0, 2.0),
            "width": w,
        },
    }


# ------------------------------------------------------------ đợt 2: giọng

def phan_tich_giong(v, n) -> dict:
    """Đo track giọng và nhạc nền đã tách, trả về mức đề nghị cho nhóm VOCAL.

    Cũng trả `bo_qua` như hàm trên, và ở đây cửa gác còn quan trọng hơn: bài
    không có lời thì Demucs vẫn trả về một track "giọng", chỉ là nó chứa tiếng
    rò rỉ từ nhạc cụ. Đo trên đó ra số rác, mà số rác đi qua chặn biên thì
    thành số trông rất hợp lý — kéo Level lên kịch trần để khuếch đại tiếng rò.
    """
    sr = config.SR
    lv, ln = dsp.do_lufs(v, sr), dsp.do_lufs(n, sr)
    if not (np.isfinite(lv) and np.isfinite(ln)):
        return {"do": {}, "thanh": {}, "bo_qua": "could not measure the stems"}
    muc = lv - ln
    if muc < -NGUONG_KHONG_LOI:
        return {"do": {"muc_giong": round(muc, 2)}, "thanh": {},
                "bo_qua": "no vocal found — instrumental track?"}
    if muc < GIONG_MIN or muc > GIONG_MAX:
        return {"do": {"muc_giong": round(muc, 2)}, "thanh": {},
                "bo_qua": "vocal balance is far outside the usual range"}

    rong_g = _rong(v)
    giua = _dai(v, sr, 300, 3000)
    net = _dai(v, sr, 3000, 5000) - giua
    xi = _dai(v, sr, 5500, 9500) - giua

    # Thang 0-100 nên hệ số quy đổi lấy sao cho một độ lệch chuẩn đẩy thanh đi
    # chừng 15 điểm — đủ thấy, chưa tới mức đổi hẳn tính chất bài.
    day = 50.0 + (CHUAN["rong_giong"] - rong_g) * 400.0
    sang = 50.0 + (CHUAN["net"] - net) * 8.0
    khu = 50.0 + (xi - CHUAN["xi"]) * 8.0

    return {
        "do": {
            "muc_giong": round(muc, 2), "rong_giong": round(rong_g, 3),
            "net": round(net, 2), "xi": round(xi, 2),
        },
        "thanh": {
            "vocal_gain": _bu_nua(muc, CHUAN["muc_giong"], 0.8, 3.0),
            # Giọng mono: khối nhân đôi vẫn tạo được bề rộng từ một kênh, nhưng
            # con số bề rộng đo được là 0 nên luật sẽ đẩy thanh lên kịch. Để
            # mặc định và nhường quyết định cho người dùng.
            **({} if rong_g < NGUONG_MONO
               else {"thickness": _chan(day, 20, 80, 1)}),
            "presence": _chan(sang, 20, 80, 1),
            "deess": _chan(khu, 20, 85, 1),
            # Vang để 0: track giọng tách ra đã mang nguyên tiếng vang của bản
            # phối gốc, thêm nữa là chồng vang lên vang.
            "space": 0.0,
        },
    }
