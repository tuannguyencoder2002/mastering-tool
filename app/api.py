# -*- coding: utf-8 -*-
"""Máy chủ HTTP: nhận file, chạy dây chuyền, trả bản đã xử lý."""
import shutil
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from . import config, jobs, chain, khoa, tinh
from . import audio as A

app = FastAPI(title="Mastering")

# Lớp khoá chỉ xuất hiện khi có biến môi trường MASTERING_PASS — tức là khi
# app được mở ra ngoài mạng. Chạy ở máy mình thì không đổi gì.
_mat_khau = khoa.gan_neu_can(app)

_ket: dict = {}


@app.post("/api/master")
async def api_master(
    audio: UploadFile = File(...),
    reference: UploadFile = File(None),
    mode: str = Form("full"),
    thickness: float = Form(50),
    presence: float = Form(50),
    space: float = Form(25),
    deess: float = Form(50),
    warmth: float = Form(0),
    bass: float = Form(0),
    air: float = Form(0),
    width: float = Form(100),
    vocal_gain: float = Form(0),
    lufs: float = Form(-14),
):
    ma = jobs.tao()
    dich = config.UPLOAD / f"{ma}_{Path(audio.filename or 'audio').name}"
    with open(dich, "wb") as f:
        shutil.copyfileobj(audio.file, f)

    f_mau = None
    if reference is not None and reference.filename:
        f_mau = config.REF / f"{ma}_{Path(reference.filename).name}"
        with open(f_mau, "wb") as f:
            shutil.copyfileobj(reference.file, f)

    tuy_chon = {"mode": mode, "thickness": thickness, "presence": presence,
                "space": space, "deess": deess, "warmth": warmth,
                "vocal_gain": vocal_gain, "bass": bass, "air": air,
                "width": width,
                "lufs": lufs, "reference": f_mau}

    def viec(bao):
        kq = chain.xu_ly(dich, tuy_chon, bao=bao)
        _ket[ma] = {"goc": dich, **kq}
        return {
            "before": {"lufs": round(kq["truoc"]["lufs"], 2),
                       "peak": round(kq["truoc"]["peak"], 2),
                       "dr": round(kq["truoc"]["dr"], 1),
                       "tp": round(kq["truoc"]["tp"], 2)},
            "after": {"lufs": round(kq["sau"]["lufs"], 2),
                      "peak": round(kq["sau"]["peak"], 2),
                      "dr": round(kq["sau"]["dr"], 1),
                      "tp": round(kq["sau"]["tp"], 2)},
            "duration": A.thoi_luong(str(dich)),
            "has_vocal": kq["vocal"] is not None,
        }

    jobs.chay(ma, viec)
    return {"id": ma}


@app.get("/api/job/{ma}")
def api_job(ma: str):
    v = jobs.xem(ma)
    if not v:
        raise HTTPException(404, "Unknown job.")
    return v


@app.get("/api/audio/{ma}")
def api_audio(ma: str, kind: str = "mastered"):
    """Phát để so A/B ngay trong giao diện — nghe mới biết hay hay dở."""
    d = _ket.get(ma)
    if not d:
        raise HTTPException(404, "No result for this job.")
    bang = {"original": d["goc"], "mastered": d["wav"], "vocal": d["vocal"]}
    f = bang.get(kind)
    if not f or not Path(f).exists():
        raise HTTPException(404, f"No audio: {kind}")
    return FileResponse(str(f))


@app.get("/api/download/{ma}")
def api_download(ma: str, fmt: str = "wav"):
    d = _ket.get(ma)
    if not d:
        raise HTTPException(404, "No result for this job.")
    f = d["mp3"] if fmt == "mp3" else d["wav"]
    return FileResponse(str(f), filename=f"mastered.{fmt}",
                        media_type="application/octet-stream")


@app.get("/api/health")
def api_health():
    import torch
    return {"ok": True, "gpu": torch.cuda.is_available(),
            "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"}


# Giao diện là HTML/CSS/JS tĩnh, không có bước dựng. Gắn SAU cùng để các đường
# /api/* không bị lớp file tĩnh nuốt mất.
_web = config.GOC / "web"
if _web.exists():
    app.mount("/", tinh.FileTinh(directory=str(_web), html=True), name="web")
