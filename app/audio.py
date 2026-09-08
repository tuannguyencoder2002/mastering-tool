# -*- coding: utf-8 -*-
"""Đọc/ghi audio bằng ffmpeg.

Không dùng torchaudio.load: nó phụ thuộc backend (sox/soundfile/ffmpeg) và mỗi
bản torchaudio lại đổi cách chọn backend. Gọi thẳng ffmpeg thì máy nào cũng
chạy như nhau, và ffmpeg mở được mọi định dạng khách đưa vào (mp3, m4a, flac,
wav, thậm chí mp4).
"""
import subprocess
from pathlib import Path

import numpy as np


# Tìm ffmpeg một lần rồi nhớ luôn, khỏi dò lại ở mỗi lần đọc file.
_duong_ffmpeg = {}


def _tim(ten: str) -> str:
    """Ưu tiên bản ffmpeg ĐI KÈM trong gói, rồi mới tới bản cài trong máy.

    Máy khách thường không có ffmpeg trong PATH, mà cũng không nên bắt họ cài.
    Ngược lại, máy nào đã có sẵn một bản ffmpeg cũ trong PATH thì bản đi kèm
    phải thắng — bản cũ có thể thiếu codec và lỗi ra rất khó hiểu.
    """
    if ten in _duong_ffmpeg:
        return _duong_ffmpeg[ten]

    goc = Path(__file__).resolve().parent.parent
    for ung in (goc / "runtime" / "ffmpeg" / "bin" / f"{ten}.exe",
                goc / "ffmpeg" / "bin" / f"{ten}.exe"):
        if ung.exists():
            _duong_ffmpeg[ten] = str(ung)
            return _duong_ffmpeg[ten]

    _duong_ffmpeg[ten] = ten          # để hệ điều hành tự tìm trong PATH
    return ten


def _ffmpeg() -> str:
    return _tim("ffmpeg")


def doc(duong_dan: str, sr: int, mono: bool) -> np.ndarray:
    """Trả về mảng float32 hình (kenh, mau), biên độ trong khoảng [-1, 1]."""
    kenh = 1 if mono else 2
    lenh = [
        _ffmpeg(), "-v", "error", "-i", str(duong_dan),
        "-f", "f32le", "-acodec", "pcm_f32le",
        "-ac", str(kenh), "-ar", str(sr), "-",
    ]
    p = subprocess.run(lenh, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg đọc file lỗi: {p.stderr.decode('utf-8', 'replace')[:400]}")
    x = np.frombuffer(p.stdout, dtype=np.float32)
    if x.size == 0:
        raise RuntimeError("File không có dữ liệu âm thanh.")
    return x.reshape(-1, kenh).T.copy()


def ghi(duong_dan: str, x: np.ndarray, sr: int, bit: int = 24) -> None:
    """Ghi mảng (kenh, mau) ra file. Đuôi file quyết định định dạng.

    WAV mặc định ghi 24 bit chứ không phải 16.

    Vì sao: ffmpeg tự chọn 16 bit khi thấy đuôi .wav. Mà tín hiệu trong tool là
    số thực, hạ xuống 16 bit là cắt cụt — thêm méo lượng tử hoá, và bản giao
    cho khách mất một tầng chất lượng mà không ai để ý. 24 bit là mức chuẩn khi
    giao bản master; 16 bit chỉ dùng khi ép đĩa CD, và lúc đó phải có dither.
    """
    if x.ndim == 1:
        x = x[None, :]
    kenh = x.shape[0]
    raw = x.T.astype(np.float32).tobytes()
    lenh = [
        _ffmpeg(), "-v", "error", "-y",
        "-f", "f32le", "-ar", str(sr), "-ac", str(kenh), "-i", "-",
    ]
    if str(duong_dan).lower().endswith(".wav"):
        lenh += ["-c:a", {16: "pcm_s16le", 24: "pcm_s24le", 32: "pcm_f32le"}[bit]]
        if bit == 16:
            # Hạ xuống 16 bit thì PHẢI rắc nhiễu (dither), nếu không phần đuôi
            # vang nhỏ dần bị lượng tử hoá thành bậc thang nghe ra được.
            lenh += ["-af", "aresample=osf=s16:dither_method=triangular_hp"]
    lenh.append(str(duong_dan))
    p = subprocess.run(lenh, input=raw, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg ghi file lỗi: {p.stderr.decode('utf-8', 'replace')[:400]}")


def thoi_luong(duong_dan: str) -> float:
    """Số giây của file, hỏi ffprobe cho nhanh (khỏi giải mã cả bài)."""
    p = subprocess.run(
        [_tim("ffprobe"), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(duong_dan)],
        capture_output=True,
    )
    try:
        return float(p.stdout.decode().strip())
    except ValueError:
        return 0.0
