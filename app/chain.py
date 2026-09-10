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

from . import config, dsp, tu_chinh
from . import audio as A
from .separate import tach_giong


# Đích độ to khi bật chế độ tự chọn. Đây là TRUNG BÌNH ĐO ĐƯỢC từ năm bản
# master mà khách đã làm qua MasteringBox: -9,56 / -9,87 / -10,00 / -10,44 /
# -10,92 LUFS. Không phải -14 của chuẩn streaming.
#
# Vì sao không lấy -14: -14 là mức mà Spotify/YouTube hạ mọi bài về khi phát,
# nên nó đúng cho việc PHÁT. Nhưng khách nghe file trực tiếp để thẩm định, và
# ở đó mức nào to hơn thì nghe "rõ ràng" hơn. Đưa bản mix -14 cho khách đã
# quen -10 thì họ nghe thành yếu, dù về chuẩn là đúng.
DICH_TU_DONG = -10.2

# (tỉ lệ nén, độ gối) của máy nén tổng, đặt riêng cho từng chế độ.
#
# Cả hai đều DÒ ĐƯỢC chứ không chọn tay: chạy năm bản mix của khách qua dây
# chuyền thật ở nhiều tỉ lệ, rồi lấy tỉ lệ nào cho dải động sát bản MasteringBox
# nhất. Mức cũ 1,8 cho cả hai làm bản ra chặt hơn họ 0,62 dB (master-only) và
# 1,01 dB (đầy đủ), đều một chiều ở cả năm bài.
#
#   master_only  1,40 -> lệch 0,38 dB
#   full         1,20 -> lệch 0,27 dB
#
# Vì sao chế độ đầy đủ cần nén NHẸ HƠN: khối giọng nâng giọng lên so với nhạc
# nền, nên bản phối tới đây dải động rộng hơn hẳn (đo trên một bài: 9,96 ->
# 12,64 dB). Cùng một tỉ lệ nén thì nó bị bóp nhiều hơn.
NEN_TONG = {"master_only": (1.40, 8.0), "full": (1.20, 8.0)}


def _bao(f, p, m):
    if f:
        f(p, m)


# Ngưỡng nhận ra "file này đã là bản master rồi", đặt theo SỐ ĐO.
#
# Năm bản mix của khách nằm ở -12,5 tới -14,9 LUFS, dải động 7,6-10,0 dB. Năm
# bản master tương ứng nằm ở -9,6 tới -10,9 LUFS, dải động 6,0-8,5 dB. Hai nhóm
# tách nhau rõ ở mốc -11,5 LUFS, và phải đòi CẢ hai điều kiện — chỉ nhìn độ lớn
# thì một bản mix to sẵn cũng bị coi nhầm là master.
DA_MASTER_LUFS = -11.5
DA_MASTER_DR = 8.5


def dich_tu_chon(x, sr) -> dict:
    """Đo bài rồi quyết định nhắm tới đâu và phải đẩy bao nhiêu.

    Đây là chỗ "tool tự lựa mức độ cho từng bài". Hai quyết định:

    1. LƯỢNG ĐẨY. Không cố định — bằng đích trừ mức đo được. Trên năm bản mix
       của khách, MasteringBox đẩy từ +2,09 tới +5,31 dB để cùng về một đích;
       chênh nhau 3,2 dB. Cộng một lượng cố định là sai ngay từ nguyên tắc.

    2. CÓ ĐẨY HAY KHÔNG. File đưa vào mà đã là bản master rồi thì giữ nguyên độ
       lớn của nó, chỉ cân phổ và chốt trần đỉnh. Trước đây Auto kéo mọi thứ về
       -10,2 bất kể: đưa một bản master -8 LUFS vào là bị hạ 2,2 dB, mà người
       dùng không hề yêu cầu chuyện đó. Giao diện có cảnh báo, nhưng cảnh báo
       không ngăn được việc đã làm rồi.

    Còn tỉ lệ nén và đường cong phổ thì CỐ ĐỊNH, và đó là chủ ý:
      - Đường cong: đo được MasteringBox gần như không kéo từng bài về dáng
        riêng (lệch chuẩn giữa năm bài 2,50 -> 2,33 dB sau xử lý).
      - Tỉ lệ nén: dải động vào và dải động họ trả ra tương quan +0,952, nhưng
        dùng hồi quy tốt nhất từ đó vẫn còn sai số 0,24 dB, trong khi tỉ lệ cố
        định hiện tại đã đạt 0,27 dB. Đổi 0,03 dB lấy một cơ chế tự chỉnh là
        thêm chỗ hỏng chứ không thêm chất lượng.
    """
    do = dsp.do_lufs(x, sr)
    dr = dsp.do_dai_dong(x, sr)
    da_master = do > DA_MASTER_LUFS and dr < DA_MASTER_DR
    dich = round(do, 2) if da_master else DICH_TU_DONG
    return {
        "lufs_vao": round(do, 2),
        "dich": dich,
        "day": round(dich - do, 2),
        "dr_vao": round(dr, 2),
        "da_master": da_master,
    }


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
           tram=0.0, cao=0.0, rong=1.0, do_manh_pho=1.0, duong_pho=None,
           tran_db=-1.0, nen_ti_le=1.8, nen_goc=8.0):
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
    # Cân phổ theo ĐƯỜNG CONG ĐO ĐƯỢC, thay cho ba lát EQ trước đây.
    #
    # Ba lát cũ là +1 dB ở 110 Hz, -1 dB ở 400 Hz, +1,5 dB ở 9 kHz — tôi chọn
    # bằng cảm nhận. Đo năm cặp trước/sau của khách rồi mới thấy hai chỗ sai:
    #   400 Hz : họ NÂNG +0,83 dB, mình HẠ -0,99 -> lệch 1,82 dB, sai cả dấu,
    #            ngay giữa dải dễ nghe nhất
    #   4-16 k : họ nâng +1,4 tới +2,3 dB, mình chỉ +0,02 tới +1,46
    # Ghi chú cũ bảo cắt 400 Hz để "dọn dải đục", nhưng số đo nói dải đục nằm
    # ở 125-160 Hz, và ở đó MasteringBox để yên.
    y = dsp.can_pho(x, sr, do_manh=do_manh_pho, duong=duong_pho)
    # Núm của người dùng cộng thêm LÊN TRÊN đường cong nền, không thay nó.
    if tram:
        y = dsp.eq(y, sr, "lowshelf", 110.0, tram)
    if cao:
        y = dsp.eq(y, sr, "highshelf", 9000.0, cao)
    y = dsp.be_rong(y, rong)
    # Nén tổng: khối "gắn kết" cho các nhạc cụ dính vào nhau.
    #
    # Ghi chú cũ ở đây viết "rất nhẹ". Sai. Đo trên năm bài: khối này một mình
    # lấy đi 2,39 dB dải động, trong khi cả khâu chuẩn độ lớn (gồm hạn đỉnh)
    # chỉ lấy 0,19 dB. Tôi từng đổ cho bộ hạn đỉnh và trần -1 dBTP; số đo bác
    # bỏ điều đó.
    # ti_le = 1 nghĩa là KHÔNG nén. Bỏ hẳn lời gọi thay vì để nó chạy không:
    # tỉ lệ 1 vẫn cộng bu_db, và vẫn tốn một lượt duyệt cả bài.
    if nen_ti_le > 1.001:
        y = dsp.nen(y, sr, nguong_db=-18.0, ti_le=nen_ti_le, nhanh_ms=30.0,
                    cham_ms=200.0, goc_db=nen_goc, bu_db=1.0)
    _bao(bao, 0.7, "Loudness")
    if dich_lufs is None:
        return dsp.han_dinh(y, sr, tran_db=tran_db)
    return dsp.chuan_do_lon(y, sr, dich_lufs=dich_lufs, tran_db=tran_db)


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
    tu_chon = bool(tuy_chon.get("auto", False))
    tay = set(tuy_chon.get("tay") or ())      # thanh người dùng đã tự kéo
    # Cân phổ mạnh tay bao nhiêu. 1.0 = đúng đường cong đo được. Có nút riêng
    # để ai muốn nhẹ hơn thì hạ, chứ không khoá cứng.
    do_manh_pho = float(tuy_chon.get("tone", 100)) / 100.0
    # Trần đỉnh liên mẫu. -1 dBTP là mức an toàn của chuẩn phát hành; nới lên
    # gần 0 cho thêm headroom để bộ hạn đỉnh đỡ phải bóp, đổi lại rủi ro méo
    # trên vài bộ giải mã. Xem README, mục trần đỉnh.
    tran = float(tuy_chon.get("ceiling", -1.0))
    # Tham số nén tổng, đặt riêng cho từng chế độ vì tín hiệu vào khác nhau:
    # chế độ đầy đủ đã qua khối giọng nên dải động trước khi vào đây rộng hơn.
    nen = tuy_chon.get("nen") or NEN_TONG[
        "full" if che_do == "full" else "master_only"]

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

    # Tự chọn đích: đo bài rồi lấy đích đã đo từ các bản master của khách.
    tu_dong = None
    tu_chinh_giong = None
    # `lufs=None` là lệnh CỐ Ý của chế độ album: đừng chuẩn hoá độ lớn ở đây,
    # để lượt hai xử lý cả album cùng lúc. Lệnh đó phải thắng Auto, không thì
    # bật Auto là album bị chuẩn hoá từng bài và mất hết chênh lệch độ to mà
    # tác giả cố ý tạo ra.
    # "lufs" nằm trong danh sách kéo tay nghĩa là người dùng đã tự đặt mức độ
    # to; Auto vẫn tự chỉnh mọi thứ khác nhưng không đụng vào đích nữa.
    if tu_chon and "lufs" not in tay and tuy_chon.get("lufs", -14) is not None:
        tu_dong = dich_tu_chon(goc, sr)
        dich = tu_dong["dich"]
        if tu_dong["da_master"]:
            # File đã là bản master: đụng vào càng ít càng tốt. Bỏ luôn cân phổ
            # và nén tổng, chỉ chốt trần đỉnh.
            #
            # Đường cong cân phổ được dò ra để bù sai lệch của dây chuyền khi
            # đầu vào là bản MIX. Áp nó lên một bản đã master là chồng thêm một
            # độ nghiêng thứ hai. Còn nén tổng lên bản đã nén là nén hai lần —
            # đo được nó lấy thêm 0,8 dB dải động mà không đổi lại được gì.
            do_manh_pho = 0.0
            nen = (1.0, nen[1])

    ten = _ma_bam(duong_dan)
    thu_muc = config.OUT / ten
    thu_muc.mkdir(parents=True, exist_ok=True)

    if che_do == "full":
        _bao(bao, 0.05, "Separating stems")
        stem = tach_giong(duong_dan, bao_tien_do=lambda p, m: _bao(bao, 0.05 + 0.45 * p, m),
                          giu_nhac_nen=True)
        v = (A.doc(str(stem["vocals"]), sr, mono=False) * he_so_truoc).astype(np.float32)
        n = (A.doc(str(stem["no_vocals"]), sr, mono=False) * he_so_truoc).astype(np.float32)

        # Đợt tự chỉnh thứ hai. Tới đây mới làm được, vì trước khi tách stem thì
        # không có cách nào biết giọng đang dày hay mỏng, to hay chìm.
        #
        # Thanh nào người dùng đã tự kéo thì KHÔNG đè lên. Đè lên là xoá chỉnh
        # tay của họ ngay trước mắt, và lần sau không ai dám động vào thanh nào
        # nữa.
        if tu_chon:
            _bao(bao, 0.52, "Reading the vocal")
            g = tu_chinh.phan_tich_giong(v, n)
            tu_chinh_giong = {"do": g["do"], "thanh": {}}
            for k, gt in g["thanh"].items():
                if k in tay:
                    continue
                tu_chinh_giong["thanh"][k] = gt
                if k == "thickness":
                    day = gt / 100.0
                elif k == "presence":
                    sang = gt / 100.0
                elif k == "space":
                    khong_gian = gt / 100.0
                elif k == "deess":
                    khu = gt / 100.0
                elif k == "vocal_gain":
                    muc_giong = gt

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
                    tram=tram, cao=cao, rong=rong, do_manh_pho=do_manh_pho,
                    duong_pho=dsp.DO_NGHIENG_GIONG, tran_db=tran,
                    nen_ti_le=nen[0], nen_goc=nen[1])
    else:
        _bao(bao, 0.3, "Mastering")
        ra = master((goc * he_so_truoc).astype(np.float32),
                    sr, dich_lufs=dich, bai_mau=bai_mau,
                    bao=lambda p, m2: _bao(bao, 0.3 + 0.6 * p, m2),
                    tram=tram, cao=cao, rong=rong, do_manh_pho=do_manh_pho,
                    tran_db=tran, nen_ti_le=nen[0], nen_goc=nen[1])

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
        "truoc": truoc, "sau": sau, "tu_dong": tu_dong,
        "tu_chinh_giong": tu_chinh_giong,
    }
