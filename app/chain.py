# -*- coding: utf-8 -*-
"""Dây chuyền xử lý: tách stem -> làm dày giọng -> trộn lại -> master.

Vì sao phải tách stem trước khi làm gì cả: "làm dày giọng" là việc của khâu
TRỘN (mixing), không phải khâu MASTER. Bộ master chỉ nhìn thấy bản đã trộn
xong, hai kênh trái phải, giọng đã hoà vào nhạc — nó không có cách nào chỉnh
riêng giọng. Tách stem là cách duy nhất lấy lại được track giọng để xử lý.
"""
import hashlib
import shutil
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from . import config, dsp
from . import audio as A
from .separate import tach_giong


def _bao(f, p, m):
    if f:
        f(p, m)


def day_giong(v, sr, day=0.5, sang=0.5, khong_gian=0.0, khu_xit=0.5, am=0.0):
    """Dây chuyền cho riêng track giọng.

    Thứ tự các khối KHÔNG tuỳ tiện:
      cắt trầm  -> bỏ tiếng gió và ù, để máy nén khỏi bám vào thứ không nghe được
      khử xì    -> trước EQ sáng, vì EQ sáng làm tiếng xì to lên
      EQ        -> dọn dải đục, thêm dải nét
      nén       -> hai tầng: tầng chậm giữ mức đều, tầng nhanh bắt đỉnh
      bão hoà   -> màu tiếng ấm hơn; MẶC ĐỊNH TẮT, xem ghi chú dưới
      nhân đôi  -> nguồn của cảm giác "dày"
      vang      -> đặt giọng vào một không gian, làm sau cùng
    """
    v = dsp.loc_thong_cao(v, sr, 85.0)
    v = dsp.khu_xit(v, sr, do_manh=khu_xit)

    v = dsp.eq(v, sr, "peak", 300.0, -2.5 * sang, Q=1.0)      # dọn dải đục
    v = dsp.eq(v, sr, "peak", 3200.0, 2.5 * sang, Q=0.9)      # dải nét, rõ lời
    v = dsp.eq(v, sr, "highshelf", 11000.0, 3.0 * sang)       # dải thoáng

    # Tầng chậm: san mức giữa các câu hát to nhỏ khác nhau.
    v = dsp.nen(v, sr, nguong_db=-24.0, ti_le=2.5, nhanh_ms=25.0, cham_ms=250.0,
                goc_db=8.0, bu_db=2.5)
    # Tầng nhanh: bắt các đỉnh phụ âm bật ra.
    v = dsp.nen(v, sr, nguong_db=-14.0, ti_le=4.0, nhanh_ms=3.0, cham_ms=90.0,
                goc_db=5.0, bu_db=1.5)

    # Bão hoà MẶC ĐỊNH TẮT, và nó có nút riêng chứ không đi kèm độ dày.
    #
    # Đo trên một bài đã phát hành: khối này một mình lấy đi 1,3 tới 2,6 dB dải
    # động của cả bản nhạc — tuỳ liều, mà liều nhẹ nhất đã tốn 1,3 dB. Đổi lại,
    # bề rộng giọng gần như không nhúc nhích (0,323 -> 0,326), và cũng không đo
    # được thêm hoạ âm nào ra hồn.
    #
    # Cái nó cho là "ấm", "dày" theo cảm nhận — thứ chỉ tai người thẩm định
    # được. Vậy thì để người dùng tự bật, chứ không bật sẵn rồi âm thầm lấy đi
    # dải động của họ.
    v = dsp.bao_hoa(v, do_manh=0.3 * am)

    # Nhân đôi mới là khối làm dày thật: cùng phép đo trên, nó đưa bề rộng
    # giọng từ 0,323 lên 0,388 mà chỉ tốn 0,3 dB dải động.
    v = dsp.nhan_doi(v, sr, do_manh=day)
    # Vang cũng MẶC ĐỊNH TẮT, cùng một lý do với bão hoà.
    #
    # Track giọng tách ra KHÔNG khô: nó vẫn mang nguyên tiếng vang của bản phối
    # gốc, vì Demucs tách nguồn âm chứ không bóc được vang ra khỏi giọng. Thêm
    # vang ở đây là chồng vang lên vang — giọng lùi ra xa, lời nhoè đi.
    #
    # Và tôi không nghe được để biết bao nhiêu là vừa. Nên để 0, ai thấy giọng
    # sau xử lý bị khô thì tự kéo lên.
    v = dsp.vang(v, sr, do_manh=khong_gian, do_dai=1.5)
    return v


def master(x, sr, dich_lufs=-14.0, bai_mau: Optional[Path] = None, bao=None,
           tram=0.0, cao=0.0, rong=1.0):
    """Khâu cuối: cân phổ tổng, gắn kết bản phối, đưa về độ lớn đích.

    Có bài mẫu thì dùng matchering — nó đo phổ tần và độ lớn của bài mẫu rồi
    ép bài của ta khớp theo. Đây đúng là cách các dịch vụ trả tiền hoạt động,
    khác mỗi chỗ chúng tự chọn bài mẫu giùm mình.

    `dich_lufs=None` nghĩa là KHÔNG chuẩn độ lớn, chỉ chặn đỉnh. Chế độ album
    cần thế: từng bài phải giữ nguyên độ to tương đối với nhau, chuẩn hoá từng
    bài riêng lẻ là san phẳng hết chênh lệch mà tác giả cố ý tạo ra.
    """
    if bai_mau is not None and Path(bai_mau).exists():
        _bao(bao, 0.1, "Matching reference")
        try:
            return _master_theo_mau(x, sr, Path(bai_mau), dich_lufs, tram, cao, rong)
        except Exception as e:
            _bao(bao, 0.5, f"Reference failed, using preset ({e.__class__.__name__})")

    _bao(bao, 0.3, "Mastering")
    # Cân phổ nhẹ tay: dải trầm chắc lại, dải cao mở ra một chút.
    # Hai tham số `tram`/`cao` cộng thêm vào đây, để người dùng chỉnh gu.
    y = dsp.eq(x, sr, "lowshelf", 110.0, 1.0 + tram)
    y = dsp.eq(y, sr, "peak", 400.0, -1.0, Q=0.9)
    y = dsp.eq(y, sr, "highshelf", 9000.0, 1.5 + cao)
    y = dsp.be_rong(y, rong)
    # Nén tổng rất nhẹ, chỉ để các nhạc cụ "dính" vào nhau.
    y = dsp.nen(y, sr, nguong_db=-18.0, ti_le=1.8, nhanh_ms=30.0, cham_ms=200.0,
                goc_db=8.0, bu_db=1.0)
    _bao(bao, 0.7, "Loudness")
    if dich_lufs is None:
        return dsp.han_dinh(y, sr, tran_db=-1.0)
    return dsp.chuan_do_lon(y, sr, dich_lufs=dich_lufs, tran_db=-1.0)


def _master_theo_mau(x, sr, bai_mau: Path, dich_lufs, tram=0.0, cao=0.0, rong=1.0):
    """Chạy matchering qua file tạm — thư viện chỉ nhận đường dẫn file."""
    import matchering as mg
    import tempfile

    mg.log(warning_handler=None, info_handler=None, debug_handler=None)
    with tempfile.TemporaryDirectory() as tmp:
        f_vao = Path(tmp) / "vao.wav"
        f_ra = Path(tmp) / "ra.wav"
        A.ghi(str(f_vao), x, sr)
        mg.process(
            target=str(f_vao),
            reference=str(bai_mau),
            results=[mg.pcm24(str(f_ra))],
        )
        y = A.doc(str(f_ra), sr, mono=False)
    # Chỉnh gu sau khi đã khớp bài mẫu, không phải trước: khớp trước rồi chỉnh
    # là người dùng vẫn còn quyền nói "hơi thiếu trầm", chỉnh trước rồi khớp
    # thì matchering ép về đúng bài mẫu và mọi chỉnh tay bị xoá sạch.
    y = dsp.eq(y, sr, "lowshelf", 110.0, tram)
    y = dsp.eq(y, sr, "highshelf", 9000.0, cao)
    y = dsp.be_rong(y, rong)
    # matchering đã khớp độ lớn theo bài mẫu; ta chỉ chốt lại trần đỉnh.
    if dich_lufs is None:
        return dsp.han_dinh(y, sr, tran_db=-1.0)
    return dsp.chuan_do_lon(y, sr, dich_lufs=dich_lufs, tran_db=-1.0)


def _ma_bam(p: Path) -> str:
    h = hashlib.sha1()
    with open(p, "rb") as f:
        while True:
            k = f.read(1 << 20)
            if not k:
                break
            h.update(k)
    return h.hexdigest()[:16]


def xu_ly(duong_dan: Path, tuy_chon: dict, bao: Optional[Callable] = None) -> dict:
    """Chạy cả dây chuyền. Trả về đường dẫn file ra và số đo trước/sau."""
    sr = config.SR
    che_do = tuy_chon.get("mode", "full")          # 'full' hoặc 'master_only'
    day = float(tuy_chon.get("thickness", 50)) / 100.0
    sang = float(tuy_chon.get("presence", 50)) / 100.0
    khong_gian = float(tuy_chon.get("space", 0)) / 100.0
    khu = float(tuy_chon.get("deess", 50)) / 100.0
    am = float(tuy_chon.get("warmth", 0)) / 100.0
    muc_giong = float(tuy_chon.get("vocal_gain", 0))       # dB
    tram = float(tuy_chon.get("bass", 0))                  # dB cộng thêm ở dải trầm
    cao = float(tuy_chon.get("air", 0))                    # dB cộng thêm ở dải cao
    rong = float(tuy_chon.get("width", 100)) / 100.0
    dich = tuy_chon.get("lufs", -14)
    dich = None if dich is None else float(dich)
    bai_mau = tuy_chon.get("reference")

    # Nâng/hạ mức TRƯỚC khi vào dây chuyền. Chế độ album cần cái này: mọi máy
    # nén ở đây đều có ngưỡng cố định, nên bài vào nhỏ hơn thì bị nén ít hơn mà
    # vẫn được bù đủ -> khoảng cách độ to giữa các bài tự co lại. Đưa tất cả về
    # cùng một mức trước khi xử lý thì mọi bài chịu đúng một cách đối xử như
    # nhau, rồi trả lại chênh lệch cũ sau.
    bu_truoc = float(tuy_chon.get("pre_gain", 0.0))
    he_so_truoc = 10 ** (bu_truoc / 20.0)

    goc = A.doc(str(duong_dan), sr, mono=False)
    truoc = {"lufs": dsp.do_lufs(goc, sr), "peak": dsp.do_dinh_db(goc),
             "dr": dsp.do_dai_dong(goc, sr), "tp": dsp.dinh_lien_mau_db(goc)}

    ten = _ma_bam(duong_dan)
    thu_muc = config.OUT / ten
    thu_muc.mkdir(parents=True, exist_ok=True)

    if che_do == "full":
        _bao(bao, 0.05, "Separating stems")
        stem = tach_giong(duong_dan, bao_tien_do=lambda p, m: _bao(bao, 0.05 + 0.45 * p, m),
                          giu_nhac_nen=True)
        v = (A.doc(str(stem["vocals"]), sr, mono=False) * he_so_truoc).astype(np.float32)
        n = (A.doc(str(stem["no_vocals"]), sr, mono=False) * he_so_truoc).astype(np.float32)

        _bao(bao, 0.55, "Thickening vocal")
        v = day_giong(v, sr, day=day, sang=sang, khong_gian=khong_gian,
                      khu_xit=khu, am=am)
        v = v * (10 ** (muc_giong / 20.0))

        # Cắt cho hai stem bằng nhau: khối nhân đôi/vang có thể làm lệch vài mẫu.
        m = min(v.shape[-1], n.shape[-1])
        tron = (v[:, :m] + n[:, :m]).astype(np.float32)

        A.ghi(str(thu_muc / "vocal_processed.wav"), v[:, :m], sr)
        _bao(bao, 0.75, "Mastering")
        ra = master(tron, sr, dich_lufs=dich, bai_mau=bai_mau,
                    bao=lambda p, m2: _bao(bao, 0.75 + 0.2 * p, m2),
                    tram=tram, cao=cao, rong=rong)
    else:
        _bao(bao, 0.3, "Mastering")
        ra = master((goc * he_so_truoc).astype(np.float32),
                    sr, dich_lufs=dich, bai_mau=bai_mau,
                    bao=lambda p, m2: _bao(bao, 0.3 + 0.6 * p, m2),
                    tram=tram, cao=cao, rong=rong)

    f_wav = thu_muc / "mastered.wav"
    f_mp3 = thu_muc / "mastered.mp3"
    A.ghi(str(f_wav), ra, sr)
    A.ghi(str(f_mp3), ra, sr)

    sau = {"lufs": dsp.do_lufs(ra, sr), "peak": dsp.do_dinh_db(ra),
           "dr": dsp.do_dai_dong(ra, sr), "tp": dsp.dinh_lien_mau_db(ra)}
    _bao(bao, 1.0, "Done")
    return {
        "wav": f_wav, "mp3": f_mp3,
        "vocal": (thu_muc / "vocal_processed.wav") if che_do == "full" else None,
        "truoc": truoc, "sau": sau,
    }
