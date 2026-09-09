# -*- coding: utf-8 -*-
"""Chạy cả album theo thư mục.

    data/Test/Input/     bỏ các bài của album vào đây
    data/Test/Output/    bản đã master hiện ra ở đây

Chế độ album KHÔNG phải là "chạy từng bài rồi ghép lại". Xem ghi chú ở hàm
`chay_album` — đây là chỗ dễ làm sai nhất, và làm sai thì album nghe như một
đống bài rời chứ không như một album.
"""
import sys
import time
from pathlib import Path

GOC = Path(__file__).resolve().parent
if str(GOC) not in sys.path:
    sys.path.insert(0, str(GOC))


def _sua_console():
    """Ép console về UTF-8 trước khi in. Mặc định là cp1252, in chữ có dấu là sập."""
    for luong in (sys.stdout, sys.stderr):
        try:
            luong.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


_sua_console()

import numpy as np                                     # noqa: E402
from app import chain, config, dsp                     # noqa: E402
from app import audio as A                             # noqa: E402

VAO = config.DATA / "Test" / "Input"
RA = config.DATA / "Test" / "Output"
DUOI_NHAC = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"}

# Bài mẫu để khớp phổ, nếu có. Đặt tên bắt đầu bằng "_reference".
TIEN_TO_MAU = "_reference"


def _tien_do(p, m):
    """Thứ tự tham số phải là (tiến độ, thông báo) — đúng như `chain` gọi lại."""
    print(f"\r      {m:<28} {p * 100:5.1f}%", end="", flush=True)


def chay_album(cac_bai, tuy_chon, dich_lufs):
    """Master cả album, giữ nguyên chênh lệch độ to giữa các bài.

    VÌ SAO KHÔNG CHUẨN HOÁ TỪNG BÀI VỀ CÙNG MỘT MỨC:

    Một album thường cố ý có bài to bài nhỏ — bản ballad phải nhỏ hơn bài mở
    màn, đó là dụng ý. Chuẩn hoá từng bài riêng lẻ về -14 LUFS là san phẳng hết
    chênh lệch ấy: nghe hết album thấy đều đều một mức, mất hẳn nhịp lên xuống.

    Cách đúng, và cũng là cách các nền tảng nhạc xử lý album: lấy bài TO NHẤT
    đưa về mức đích, rồi dịch mọi bài còn lại đi CÙNG một lượng decibel. Chênh
    lệch giữa các bài giữ nguyên như tác giả đã định.

    Nên phải chạy hai lượt: lượt một master mà không chuẩn độ lớn, đo xem bài
    nào to nhất; lượt hai mới áp một hệ số chung cho tất cả.
    """
    # Đo độ to từng bài GỐC trước đã. Đây là chênh lệch phải bảo toàn.
    print(f"Đo {len(cac_bai)} bài gốc")
    goc = []
    for f in cac_bai:
        goc.append(dsp.do_lufs(A.doc(str(f), config.SR, mono=False), config.SR))
    moc = max(goc)
    print(f"  chênh lệch độ to giữa bài to nhất và nhỏ nhất: "
          f"{moc - min(goc):.2f} dB\n")

    tam = []
    print(f"Lượt 1/2 — xử lý {len(cac_bai)} bài\n")
    for i, (f, l0) in enumerate(zip(cac_bai, goc), 1):
        print(f"[{i}/{len(cac_bai)}] {f.name}")
        t0 = time.time()
        # Nâng bài này lên ngang bài to nhất TRƯỚC khi xử lý, để mọi bài đi qua
        # máy nén ở cùng một mức và chịu đúng một cách đối xử như nhau.
        # dich_lufs=None: chưa đụng vào độ lớn, để lượt hai quyết.
        kq = chain.xu_ly(f, {**tuy_chon, "lufs": None, "pre_gain": moc - l0},
                         bao=_tien_do)
        x = A.doc(str(kq["wav"]), config.SR, mono=False)
        tam.append({"file": f, "am": x, "lech": l0 - moc,
                    "lufs": dsp.do_lufs(x, config.SR), "truoc": kq["truoc"]})
        print(f"\r      {tam[-1]['lufs']:6.2f} LUFS · "
              f"{time.time() - t0:.0f}s" + " " * 30)

    to_nhat = max(t["lufs"] for t in tam)
    bu = dich_lufs - to_nhat
    print(f"\nLượt 2/2 — trả lại chênh lệch gốc rồi dịch cả album {bu:+.2f} dB\n")

    ket = []
    for t in tam:
        # `lech` là chênh lệch âm so với bài to nhất ở bản gốc — trả lại đúng
        # bằng đó, cộng với hệ số chung của cả album.
        y = (t["am"] * (10 ** ((bu + t["lech"]) / 20.0))).astype(np.float32)
        y = dsp.han_dinh(y, config.SR, tran_db=-1.0)
        f_ra = RA / f"{t['file'].stem}.wav"
        A.ghi(str(f_ra), y, config.SR)
        ket.append({
            "ten": t["file"].name,
            "lufs": dsp.do_lufs(y, config.SR),
            "dr": dsp.do_dai_dong(y, config.SR),
            "dr_truoc": t["truoc"]["dr"],
        })
    return ket, moc - min(goc)


def chay_rieng(cac_bai, tuy_chon, dich_lufs):
    """Master từng bài độc lập, mỗi bài về đúng mức đích."""
    ket = []
    for i, f in enumerate(cac_bai, 1):
        print(f"[{i}/{len(cac_bai)}] {f.name}")
        t0 = time.time()
        kq = chain.xu_ly(f, {**tuy_chon, "lufs": dich_lufs}, bao=_tien_do)
        f_ra = RA / f"{f.stem}.wav"
        A.ghi(str(f_ra), A.doc(str(kq["wav"]), config.SR, mono=False), config.SR)
        ket.append({"ten": f.name, "lufs": kq["sau"]["lufs"],
                    "dr": kq["sau"]["dr"], "dr_truoc": kq["truoc"]["dr"]})
        print(f"\r      xong · {time.time() - t0:.0f}s" + " " * 40)
    # Trả về cùng hình dạng với chay_album để chỗ gọi khỏi phải phân biệt.
    # Không có chênh lệch album để báo cáo, nên là None.
    return ket, None


def main():
    VAO.mkdir(parents=True, exist_ok=True)
    RA.mkdir(parents=True, exist_ok=True)

    tat_ca = [f for f in sorted(VAO.iterdir())
              if f.is_file() and f.suffix.lower() in DUOI_NHAC]
    mau = [f for f in tat_ca if f.stem.lower().startswith(TIEN_TO_MAU)]
    cac_bai = [f for f in tat_ca if f not in mau]

    if not cac_bai:
        print("Không có bài nào để chạy.\n")
        print(f"Bỏ file nhạc vào  {VAO}")
        print(f"Muốn khớp phổ theo một bài mẫu thì đặt tên bắt đầu bằng"
              f" '{TIEN_TO_MAU}', ví dụ _reference.wav")
        return

    # Đọc tuỳ chọn từ file cạnh thư mục, để đổi mà không phải sửa mã.
    cau_hinh = VAO.parent / "settings.txt"
    tuy_chon = {"mode": "full", "thickness": 50, "presence": 50, "space": 25,
                "deess": 50, "warmth": 0, "vocal_gain": 0,
                "bass": 0, "air": 0, "width": 100, "tone": 100}
    # -10,2 là đích ĐO ĐƯỢC từ năm bản master tham chiếu của khách, không phải
    # -14 của chuẩn nhạc trực tuyến. Xem README, mục đường cong tham chiếu.
    dich_lufs = -10.2
    che_do_album = True

    if cau_hinh.exists():
        for dong in cau_hinh.read_text(encoding="utf-8-sig").splitlines():
            dong = dong.split("#")[0].strip()
            if "=" not in dong:
                continue
            k, v = (p.strip() for p in dong.split("=", 1))
            if k == "lufs":
                dich_lufs = float(v)
            elif k == "album":
                che_do_album = v.lower() in ("1", "true", "yes", "on")
            elif k == "mode":
                tuy_chon["mode"] = v
            elif k in tuy_chon:
                tuy_chon[k] = float(v)

    if mau:
        tuy_chon["reference"] = mau[0]
        print(f"Bài mẫu để khớp phổ: {mau[0].name}")

    print(f"{len(cac_bai)} bài · đích {dich_lufs:g} LUFS · "
          f"{'chế độ album' if che_do_album else 'từng bài độc lập'} · "
          f"{tuy_chon['mode']}\n")

    t0 = time.time()
    ket, chenh_goc = (chay_album if che_do_album else chay_rieng)(
        cac_bai, tuy_chon, dich_lufs)

    print(f"\n{'BÀI':<34} {'LUFS':>7} {'DẢI ĐỘNG':>10} {'MẤT':>7}")
    for k in ket:
        print(f"{k['ten'][:33]:<34} {k['lufs']:7.2f} {k['dr']:9.1f} dB"
              f" {k['dr_truoc'] - k['dr']:6.1f}")

    print(f"\nXong {len(ket)} bài trong {time.time() - t0:.0f} giây."
          f"  Kết quả ở {RA}")
    if che_do_album and chenh_goc is not None:
        chenh = max(k["lufs"] for k in ket) - min(k["lufs"] for k in ket)
        print(f"Chênh lệch độ to trong album: bản gốc {chenh_goc:.2f} dB"
              f" -> bản ra {chenh:.2f} dB (lệch {abs(chenh - chenh_goc):.2f} dB).")
        if abs(chenh - chenh_goc) > 1.0:
            print("  Lệch hơn 1 dB nghĩa là dây chuyền đã san bớt chênh lệch"
                  " tác giả cố ý tạo ra — kiểm tra lại tuỳ chọn nén.")


if __name__ == "__main__":
    main()
