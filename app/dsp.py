# -*- coding: utf-8 -*-
"""Khối xử lý tín hiệu cơ bản.

Không có "model AI" nào ở đây, và đó là chuyện bình thường: mastering vốn là
chuỗi xử lý tín hiệu số cổ điển — lọc tần số, nén dải động, bão hoà, hạn đỉnh.
Phần "thông minh" nằm ở chỗ CHỌN tham số cho chuỗi đó, chứ không nằm ở model.

Mọi hàm nhận và trả mảng float32 hình (kenh, mau).
"""
import numpy as np
from scipy import signal

from . import config


# ---------------------------------------------------------------- bộ lọc

def _chan(f0: float, sr: int) -> float:
    """Chặn tần số cắt dưới Nyquist, nếu không thiết kế lọc là văng lỗi."""
    return float(np.clip(f0, 20.0, sr * 0.49))


def loc_thong_cao(x, sr, f0, bac=2):
    sos = signal.butter(bac, _chan(f0, sr), btype="highpass", fs=sr, output="sos")
    return signal.sosfilt(sos, x, axis=-1).astype(np.float32)


def loc_thong_thap(x, sr, f0, bac=2):
    sos = signal.butter(bac, _chan(f0, sr), btype="lowpass", fs=sr, output="sos")
    return signal.sosfilt(sos, x, axis=-1).astype(np.float32)


def _biquad(loai, f0, sr, gain_db=0.0, Q=0.707):
    """Công thức biquad chuẩn của Audio EQ Cookbook (Robert Bristow-Johnson)."""
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * _chan(f0, sr) / sr
    c, s = np.cos(w0), np.sin(w0)
    alpha = s / (2 * Q)

    if loai == "peak":
        b = [1 + alpha * A, -2 * c, 1 - alpha * A]
        a = [1 + alpha / A, -2 * c, 1 - alpha / A]
    elif loai == "lowshelf":
        t = 2 * np.sqrt(A) * alpha
        b = [A * ((A + 1) - (A - 1) * c + t), 2 * A * ((A - 1) - (A + 1) * c),
             A * ((A + 1) - (A - 1) * c - t)]
        a = [(A + 1) + (A - 1) * c + t, -2 * ((A - 1) + (A + 1) * c),
             (A + 1) + (A - 1) * c - t]
    elif loai == "highshelf":
        t = 2 * np.sqrt(A) * alpha
        b = [A * ((A + 1) + (A - 1) * c + t), -2 * A * ((A - 1) + (A + 1) * c),
             A * ((A + 1) + (A - 1) * c - t)]
        a = [(A + 1) - (A - 1) * c + t, 2 * ((A - 1) - (A + 1) * c),
             (A + 1) - (A - 1) * c - t]
    else:
        raise ValueError(loai)

    b = np.asarray(b, dtype=np.float64) / a[0]
    a = np.asarray(a, dtype=np.float64) / a[0]
    return signal.tf2sos(b, a)


def eq(x, sr, loai, f0, gain_db, Q=0.707):
    if abs(gain_db) < 0.01:
        return x
    sos = _biquad(loai, f0, sr, gain_db, Q)
    return signal.sosfilt(sos, x, axis=-1).astype(np.float32)


# ---------------------------------------------------------------- dải động

def _duong_bao(x, sr, nhanh_ms, cham_ms):
    """Đường bao biên độ, lấy ở nhịp điều khiển (một điểm cho mỗi NHIP mẫu).

    Lên nhanh xuống chậm: đó là cách tai nghe to nhỏ, và cũng là cách mọi máy
    nén hoạt động — bắt đỉnh thì phải nhạy, nhả ra thì phải từ tốn, nếu không
    tiếng bị phập phồng.
    """
    n = x.shape[-1]
    b = config.NHIP
    so_khoi = int(np.ceil(n / b))
    dem = so_khoi * b - n
    z = np.pad(np.abs(x).max(axis=0), (0, dem))
    khoi = z.reshape(so_khoi, b).max(axis=1)

    sr_dk = sr / b
    a_len = np.exp(-1.0 / max(1e-6, (nhanh_ms / 1000.0) * sr_dk))
    a_xuong = np.exp(-1.0 / max(1e-6, (cham_ms / 1000.0) * sr_dk))

    bao = np.empty(so_khoi, dtype=np.float32)
    y = 0.0
    for i in range(so_khoi):
        v = khoi[i]
        he_so = a_len if v > y else a_xuong
        y = he_so * y + (1 - he_so) * v
        bao[i] = y
    return bao, dem


def _trai_gain(gain_khoi, n, dem):
    """Trải hệ số khuếch đại từ nhịp điều khiển về từng mẫu, nội suy tuyến tính."""
    b = config.NHIP
    x_khoi = np.arange(len(gain_khoi)) * b + b / 2.0
    x_mau = np.arange(len(gain_khoi) * b)
    g = np.interp(x_mau, x_khoi, gain_khoi).astype(np.float32)
    return g[:n]


def nen(x, sr, nguong_db, ti_le, nhanh_ms=10.0, cham_ms=120.0, goc_db=6.0, bu_db=0.0):
    """Máy nén dải động có góc mềm.

    ti_le=4 nghĩa là vượt ngưỡng 4 dB thì chỉ cho ra 1 dB.
    """
    bao, dem = _duong_bao(x, sr, nhanh_ms, cham_ms)
    muc = 20 * np.log10(np.maximum(bao, 1e-9))
    vuot = muc - nguong_db

    ra = np.zeros_like(vuot)
    trong_goc = np.abs(vuot) <= goc_db / 2
    tren_goc = vuot > goc_db / 2
    # Góc mềm: chuyển dần từ "không nén" sang "nén đủ" trong khoảng goc_db,
    # thay vì bật tắt đột ngột ở đúng ngưỡng — nghe tự nhiên hơn hẳn.
    ra[trong_goc] = ((1 / ti_le - 1) * (vuot[trong_goc] + goc_db / 2) ** 2) / (2 * goc_db)
    ra[tren_goc] = (vuot[tren_goc] / ti_le) - vuot[tren_goc]

    g = 10 ** ((ra + bu_db) / 20.0)
    return (x * _trai_gain(g, x.shape[-1], dem)).astype(np.float32)


def khu_xit(x, sr, do_manh=0.5, f_thap=5500.0, f_cao=9500.0):
    """Khử tiếng xì của các âm S, SH, T.

    Cách làm: tách riêng dải 5,5-9,5 kHz, nén CHỈ dải đó rồi ghép lại. Nén cả
    bài thì mỗi lần hát chữ S là cả giọng bị tụt xuống — lỗi kinh điển.
    """
    if do_manh <= 0.01:
        return x
    sos = signal.butter(2, [_chan(f_thap, sr), _chan(f_cao, sr)],
                        btype="bandpass", fs=sr, output="sos")
    dai = signal.sosfilt(sos, x, axis=-1).astype(np.float32)
    con_lai = x - dai
    nguong = -30.0 + 12.0 * (1 - do_manh)
    dai_nen = nen(dai, sr, nguong_db=nguong, ti_le=4 + 6 * do_manh,
                  nhanh_ms=1.0, cham_ms=40.0, goc_db=4.0)
    return (con_lai + dai_nen).astype(np.float32)


# ---------------------------------------------------------------- màu tiếng

def bao_hoa(x, do_manh=0.3):
    """Bão hoà kiểu băng từ: thêm hoạ âm, nghe ấm và dày hơn.

    Đây là chỗ tạo cảm giác "to hơn mà không cần tăng âm lượng": hoạ âm mới
    sinh nằm ở dải tai nhạy, nên giọng nổi lên khỏi bản phối.
    """
    if do_manh <= 0.01:
        return x
    # Hệ số 2,5 chứ không phải 6: đo trên nhạc thật thì phần lớn cái giá về dải
    # động phải trả ngay ở liều đầu tiên, đẩy mạnh thêm chỉ tốn thêm mà không
    # đổi được gì nghe ra.
    k = 1.0 + 2.5 * do_manh
    # Chia lại cho tanh(k) để mức ra không phình theo độ mạnh.
    return (np.tanh(x * k) / np.tanh(k)).astype(np.float32)


def _doi_cao_do(x, sr, cent):
    """Đổi cao độ vài phần trăm nửa cung bằng cách lấy mẫu lại rồi cắt/đệm.

    Cách này làm đổi cả tốc độ, nhưng lệch vài cent thì độ lệch thời gian nhỏ
    tới mức tai không nghe ra — mà đó chính là thứ tạo hiệu ứng nhân đôi.
    """
    ti_le = 2 ** (cent / 1200.0)
    tu, mau = 1000, int(round(1000 * ti_le))
    y = signal.resample_poly(x, tu, mau, axis=-1).astype(np.float32)
    n = x.shape[-1]
    if y.shape[-1] >= n:
        return y[:, :n]
    return np.pad(y, ((0, 0), (0, n - y.shape[-1])))


def nhan_doi(x, sr, do_manh=0.5, tre_ms=(19.0, 27.0), cent=(-9.0, 11.0)):
    """Nhân đôi giọng: hai bản sao lệch cao độ và lệch thời gian, đẩy sang hai bên.

    ĐÂY mới là thứ "làm dày giọng hát". Không bộ mastering nào làm được việc
    này, vì mastering chỉ nhìn thấy bản phối đã trộn — muốn dày giọng thì phải
    có track giọng riêng.

    Lệch thời gian ~20 ms là ngưỡng Haas: tai gộp thành MỘT giọng rộng hơn chứ
    không nghe thành tiếng vọng. Quá 40 ms là bắt đầu nghe ra hai giọng.
    """
    if do_manh <= 0.01:
        return x
    if x.shape[0] == 1:
        x = np.repeat(x, 2, axis=0)

    ra = x.copy()
    muc = 0.55 * do_manh
    giua = x.mean(axis=0, keepdims=True)
    for i, (t_ms, c) in enumerate(zip(tre_ms, cent)):
        ban = _doi_cao_do(giua, sr, c)
        d = int(t_ms * sr / 1000.0)
        ban = np.pad(ban, ((0, 0), (d, 0)))[:, :x.shape[-1]]
        # Bản sao hơi tối hơn giọng chính, để nó nằm phía sau chứ không tranh chỗ.
        ban = loc_thong_thap(ban, sr, 7000.0)
        ban = loc_thong_cao(ban, sr, 150.0)
        ra[i % 2] += ban[0] * muc
    return ra.astype(np.float32)


def be_rong(x, muc=1.0):
    """Nới hoặc thu bề rộng sân khấu stereo.

    Cách làm là tách tín hiệu thành phần GIỮA (thứ giống nhau ở hai loa) và
    phần BÊN (thứ khác nhau), rồi đổi tỉ lệ giữa hai phần. muc=1 là giữ nguyên,
    lớn hơn 1 là rộng ra, nhỏ hơn 1 là co lại về mono.

    Vì sao chặn ở 1,6: nới quá tay thì phần bên lấn át, và khi ai đó nghe trên
    loa điện thoại (một loa, tức là cộng hai kênh lại) phần bên triệt tiêu nhau
    — bản nhạc đột nhiên rỗng ruột. Lỗi này chỉ lộ ra ở đúng thiết bị mà phần
    lớn người nghe đang dùng.
    """
    if x.shape[0] < 2 or abs(muc - 1.0) < 0.01:
        return x
    muc = float(np.clip(muc, 0.0, 1.6))
    giua = (x[0] + x[1]) * 0.5
    ben = (x[0] - x[1]) * 0.5 * muc
    return np.stack([giua + ben, giua - ben]).astype(np.float32)


def vang(x, sr, do_manh=0.25, do_dai=1.6, tre_ms=25.0):
    """Vang kiểu tấm, dựng bằng bốn bộ lặp song song và hai bộ tán pha.

    Kiến trúc Schroeder: bộ lặp tạo đuôi vang, bộ tán pha làm đuôi đó nhoè ra
    cho khỏi nghe thành từng tiếng vọng rời rạc.
    """
    if do_manh <= 0.01:
        return x

    # Hồi tiếp trễ D mẫu:  y[n] = u[n] + g * y[n-D]
    #
    # KHÔNG dùng lfilter với mẫu số dài D+1. Nhìn thì gọn, nhưng lfilter chạy
    # O(số mẫu × bậc bộ lọc): D ở đây là 1900 mẫu, bài 3 phút là 8,4 triệu mẫu
    # -> 16 tỉ phép cho MỘT bộ lặp, mà có tới bốn bộ. Đo thật: 35,7 giây chỉ
    # riêng khối vang, gấp mười lần tất cả các khối khác cộng lại.
    #
    # Cách này chia thành từng khối D mẫu. Mẫu thứ n chỉ phụ thuộc mẫu n-D,
    # nên trong một khối D mẫu không có mẫu nào phụ thuộc mẫu nào — cộng cả
    # khối một lần bằng numpy. Còn 8,4 triệu / 1900 = 4400 vòng thay vì 16 tỉ.
    def _hoi_tiep(u, D, g):
        y = u.copy()
        n = y.shape[-1]
        for a in range(D, n, D):
            b = min(a + D, n)
            y[:, a:b] += g * y[:, a - D:b - D]
        return y

    def lap(tin, tre_s, suy):
        D = max(1, int(tre_s * sr))
        return _hoi_tiep(tin.astype(np.float64), D, suy)

    def tan_pha(tin, tre_s, g=0.7):
        D = max(1, int(tre_s * sr))
        # Phần truyền thẳng:  u[n] = -g*x[n] + x[n-D]
        u = -g * tin
        u[:, D:] += tin[:, :-D]
        return _hoi_tiep(u, D, g)

    # Các độ trễ lệch nhau và không chia hết cho nhau, để hai bộ lặp không cộng
    # hưởng cùng một tần số — trùng cộng hưởng thì nghe ra tiếng kim loại.
    tre_lap = [0.0297, 0.0371, 0.0411, 0.0437]
    kho = np.pad(x, ((0, 0), (int(tre_ms * sr / 1000), 0)))[:, :x.shape[-1]]
    kho = loc_thong_cao(kho, sr, 250.0)      # bỏ trầm, kẻo vang thành đục
    kho = loc_thong_thap(kho, sr, 8000.0)

    tong = np.zeros(kho.shape, dtype=np.float64)
    for t in tre_lap:
        suy = 10 ** (-3.0 * t / max(0.1, do_dai))
        tong += lap(kho, t, suy)
    tong /= len(tre_lap)
    tong = tan_pha(tan_pha(tong, 0.0050), 0.0017)
    return (x + tong.astype(np.float32) * do_manh * 0.6).astype(np.float32)


# ---------------------------------------------------------------- độ lớn

def han_dinh(x, sr, tran_db=-1.0, nhin_truoc_ms=5.0, nha_ms=60.0):
    """Máy hạn đỉnh có nhìn trước: chặn đỉnh vượt trần mà không méo tiếng.

    Nhìn trước = làm trễ tín hiệu đúng bằng thời gian cần để hạ khuếch đại
    TRƯỚC khi đỉnh tới. Không nhìn trước thì đỉnh đầu tiên luôn lọt qua.
    """
    tran = 10 ** (tran_db / 20.0)
    nhin = int(nhin_truoc_ms * sr / 1000.0)
    kho = np.pad(x, ((0, 0), (nhin, 0)))

    dinh = np.abs(kho).max(axis=0)
    b = config.NHIP
    so_khoi = int(np.ceil(len(dinh) / b))
    dem = so_khoi * b - len(dinh)
    khoi = np.pad(dinh, (0, dem)).reshape(so_khoi, b).max(axis=1)

    can = np.minimum(1.0, tran / np.maximum(khoi, 1e-9)).astype(np.float32)
    # Lấy mức thấp nhất trong cửa sổ nhìn trước, để bắt đầu hạ trước khi đỉnh tới.
    w = max(1, int(np.ceil(nhin / b)))
    if w > 1:
        dem_w = (w - 1)
        cua = np.lib.stride_tricks.sliding_window_view(
            np.pad(can, (0, dem_w), constant_values=1.0), w)
        can = cua.min(axis=-1).astype(np.float32)

    a = np.exp(-1.0 / max(1e-6, (nha_ms / 1000.0) * (sr / b)))
    g = np.empty_like(can)
    y = 1.0
    for i in range(len(can)):
        v = can[i]
        y = v if v < y else a * y + (1 - a) * v
        g[i] = y

    ra = kho * _trai_gain(g, kho.shape[-1], dem)
    ra = ra[:, nhin:nhin + x.shape[-1]]
    return np.clip(ra, -tran, tran).astype(np.float32)


def dinh_lien_mau_db(x, he=4) -> float:
    """Đỉnh LIÊN MẪU (true peak), tính bằng cách lấy mẫu dày lên `he` lần.

    Vì sao con số này khác đỉnh thường: file số chỉ lưu giá trị tại từng mẫu,
    nhưng sóng thật giữa hai mẫu có thể vọt cao hơn cả hai. Máy hạn đỉnh chỉ
    nhìn từng mẫu nên không thấy các đỉnh nằm giữa.

    Chuyện đó chỉ thành vấn đề khi bản nhạc bị nén sang MP3/AAC: bộ giải mã
    dựng lại sóng liên tục, các đỉnh ẩn hiện ra và vượt trần -> rè. Đây là lý
    do chuẩn phát thanh và các nền tảng nhạc đều nói về dBTP chứ không dBFS.
    """
    up = signal.resample_poly(x, he, 1, axis=-1)
    return float(20 * np.log10(max(np.abs(up).max(), 1e-9)))


def han_dinh_lien_mau(x, sr, tran_db=-1.0, he=4):
    """Hạn đỉnh có tính cả đỉnh LIÊN MẪU, bằng cách làm việc trên tín hiệu đã
    lấy mẫu dày lên `he` lần.

    Vì sao phải làm thế thay vì hạ cả bản xuống cho vừa trần:

    Máy hạn đỉnh thường chỉ nhìn từng mẫu, nên xong việc vẫn còn đỉnh ẩn nằm
    giữa hai mẫu. Cách chữa cũ của tôi là đo đỉnh liên mẫu rồi hạ cả bản nhạc
    xuống đúng bằng phần vượt. Đo trên nhạc thường thì phần vượt chỉ 0,14 dB
    nên không sao — nhưng gặp bài rap đã xén mạnh, phần vượt lên tới 1,44 dB,
    và cả bản bị hạ đi ngần ấy. Người dùng chọn đích -14 LUFS mà nhận về
    -15,44: trượt đích mà không hiểu vì sao.

    Lấy mẫu dày lên rồi mới hạn thì máy hạn NHÌN THẤY các đỉnh ẩn và chỉ hạ
    đúng những chỗ ấy, thay vì hạ cả bài. Giữ được độ lớn, mà trần vẫn đúng.

    Đắt hơn vài giây cho một bài — chỉ chạy ở khâu chốt cuối, không chạy trong
    vòng lặp dò độ lớn.
    """
    tran = 10 ** (tran_db / 20.0)
    day = signal.resample_poly(x, he, 1, axis=-1)
    day = han_dinh(day, sr * he, tran_db)
    y = signal.resample_poly(day, 1, he, axis=-1).astype(np.float32)
    # Lấy mẫu thưa trở lại có thể sinh sai số rất nhỏ ở mép; chốt lại cho chắc.
    return np.clip(y, -tran, tran)


def do_lufs(x, sr) -> float:
    import pyloudnorm as pyln
    do = pyln.Meter(sr)
    return float(do.integrated_loudness(x.T.astype(np.float64)))


def do_dinh_db(x) -> float:
    d = float(np.abs(x).max())
    return 20 * np.log10(max(d, 1e-9))


def do_dai_dong(x, sr) -> float:
    """Dải động còn lại, tính bằng dB: chênh giữa các đoạn to và các đoạn vừa.

    Đây là con số cho biết mình có nén quá tay không. Độ lớn tăng lên bao nhiêu
    không nói được gì nếu không nhìn kèm dải động mất đi bao nhiêu — nhạc bị
    nén bẹt thì to hơn thật, nhưng nghe mệt và mất hết chỗ nhấn nhá.

    Lấy phân vị 95 so với phân vị 25 của mức hiệu dụng từng 100 ms, chỉ tính
    các đoạn CÓ TIẾNG.

    Ngưỡng "có tiếng" phải lấy tương đối theo chính bản nhạc (thấp hơn đoạn to
    nhất 35 dB), không lấy một con số tuyệt đối. Đo thật trên một track giọng
    tách ra mới thấy vì sao: giữa các câu hát là khoảng lặng, lấy ngưỡng tuyệt
    đối thì các khoảng đó vẫn lọt vào, phân vị dưới tụt xuống, và con số báo
    "giọng còn nhiều dải động" trong khi lúc đang hát nó đã bị nén kỹ rồi.
    """
    b = max(1, int(sr * 0.1))
    n = x.shape[-1] // b
    if n < 4:
        return 0.0
    dinh = np.abs(x).max(axis=0)[:n * b].reshape(n, b)
    e = np.sqrt((dinh ** 2).mean(axis=1))
    if e.size < 4:
        return 0.0
    nguong = max(np.percentile(e, 95) * (10 ** (-35 / 20.0)), 1e-5)
    e = e[e > nguong]
    if e.size < 4:
        return 0.0
    return float(20 * np.log10(np.percentile(e, 95) / max(np.percentile(e, 25), 1e-9)))


def chuan_do_lon(x, sr, dich_lufs=-14.0, tran_db=-1.0):
    """Đưa độ lớn về mức đích rồi chặn đỉnh.

    -14 LUFS là mức các nền tảng nhạc trực tuyến quy về. To hơn mức đó thì khi
    phát trên Spotify/YouTube nó bị hạ xuống, chỉ còn lại phần dải động đã bị
    nén mất — nghe bẹt hơn chính bản chưa nén.
    """
    hien = do_lufs(x, sr)
    if not np.isfinite(hien):
        return han_dinh(x, sr, tran_db)

    tran = 10 ** (tran_db / 20.0)
    y = (x * (10 ** ((dich_lufs - hien) / 20.0))).astype(np.float32)
    y = han_dinh(y, sr, tran_db)

    # Đo lại rồi bù, tối đa ba vòng. Vì sao phải lặp: chính máy hạn đỉnh vừa
    # lấy đi một phần độ lớn, nên nhân đúng hệ số ở trên xong vẫn còn hụt —
    # đích càng to thì hụt càng nhiều.
    #
    # Từ vòng thứ hai có thêm khâu xén mềm. Đây là cách duy nhất đẩy độ lớn
    # trung bình lên khi đỉnh đã chạm trần: bào bớt đỉnh nhọn để phần thân
    # sóng được nâng lên. Mọi bộ "loudness maximizer" đều làm đúng việc này,
    # và cũng chính vì vậy mà ép quá to thì bản nhạc bẹt đi.
    for _ in range(4):
        sau = do_lufs(y, sr)
        if not np.isfinite(sau):
            break
        thieu = dich_lufs - sau
        if abs(thieu) <= 0.2:
            break

        z = (y * (10 ** (thieu / 20.0))).astype(np.float32)
        if thieu > 0.5:
            xen = (np.tanh(z / tran * 1.5) * tran / np.tanh(1.5)).astype(np.float32)
            # Pha xén theo đúng phần còn thiếu: thiếu nhiều thì xén mạnh, thiếu
            # ít thì gần như không xén. Xén thẳng tay rồi hạ lại là méo tiếng
            # mà chẳng được thêm decibel nào.
            pha = min(1.0, thieu / 3.0)
            z = (z * (1 - pha) + xen * pha).astype(np.float32)
        y = han_dinh(z, sr, tran_db)

    # Khâu chốt: hạn đỉnh trên tín hiệu lấy mẫu dày, để bắt cả đỉnh liên mẫu.
    #
    # Rồi đo lại độ lớn và bù thêm tối đa hai vòng. Cần vòng bù vì khâu chốt
    # này cũng lấy đi một ít độ lớn — nhưng ít hơn hẳn cách cũ, nên hai vòng
    # là đủ hội tụ.
    y = han_dinh_lien_mau(y, sr, tran_db)
    for _ in range(2):
        sau = do_lufs(y, sr)
        if not np.isfinite(sau) or abs(dich_lufs - sau) <= 0.3:
            break
        y = han_dinh_lien_mau(
            (y * (10 ** ((dich_lufs - sau) / 20.0))).astype(np.float32),
            sr, tran_db)
    return y
