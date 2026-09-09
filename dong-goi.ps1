# Đóng gói Tool Mastering thành thư mục chạy được, máy khách không cần cài gì.
#
#   powershell -ExecutionPolicy Bypass -File dong-goi.ps1
#   powershell -ExecutionPolicy Bypass -File dong-goi.ps1 -Cpu       (bản CPU, nhẹ hơn 3 GB)
#   powershell -ExecutionPolicy Bypass -File dong-goi.ps1 -Nen       (nén luôn thành .zip)
#
# Ra: dist\Mastering\  — chép cả thư mục sang máy khách, nháy đúp Mastering.exe.
#
# Thư viện được CHÉP từ venv đang dùng để phát triển, không tải lại từ mạng.
# Lý do: bản đang chạy trên máy này là bản đã đo, đã thử; tải mới về là mở cửa
# cho một tổ hợp phiên bản khác chưa ai kiểm.

param(
    [switch]$Cpu,          # bỏ toàn bộ DLL CUDA: gói còn ~1 GB, chạy chậm hơn 4-5 lần
    [switch]$Nen,          # nén thành .zip sau khi dựng
    [string]$Venv = "C:\Users\Lenovo\Sumo\PPO_Train\Script",
    [string]$FFmpeg = "E:\ai\ffmpeg\ffmpeg-7.1.1-full_build\bin"
)

$ErrorActionPreference = "Stop"
$GOC = Split-Path -Parent $MyInvocation.MyCommand.Path
$DIST = Join-Path $GOC "dist\Mastering"
$TAM = Join-Path $env:TEMP "mastering-dongoi"
$PY_VER = "3.11.9"        # phải cùng dòng 3.11 với venv, nếu không .pyd không nạp được

function Buoc($n, $chu) { Write-Host "`n[$n] $chu" -ForegroundColor Cyan }
function Mb($duong) {
    if (-not (Test-Path $duong)) { return 0 }
    [math]::Round((Get-ChildItem $duong -Recurse -File -EA SilentlyContinue |
                   Measure-Object Length -Sum).Sum / 1MB)
}

# ---------------------------------------------------------------- 0. kiểm tra

Buoc 0 "Kiểm tra nguồn"
$SP = Join-Path $Venv "Lib\site-packages"
if (-not (Test-Path $SP)) { throw "Không thấy site-packages ở $SP" }
if (-not (Test-Path (Join-Path $FFmpeg "ffmpeg.exe"))) { throw "Không thấy ffmpeg.exe ở $FFmpeg" }

# Bản dựng phải khớp phiên bản Python của venv. Chép gói của 3.11 vào Python
# 3.12 thì mọi file .pyd đều không nạp được, mà lỗi báo ra rất mù mờ.
$ver_venv = & (Join-Path $Venv "Scripts\python.exe") -c "import sys; print(str(sys.version_info[0]) + '.' + str(sys.version_info[1]))"
if ($ver_venv.Trim() -ne "3.11") { throw "venv là Python $ver_venv, script này dựng cho 3.11" }
Write-Host "    venv Python $ver_venv, site-packages $(Mb $SP) MB"

if (Test-Path $DIST) { Remove-Item $DIST -Recurse -Force }
New-Item -ItemType Directory -Force -Path $DIST, $TAM | Out-Null

# ---------------------------------------------------------------- 1. Python

Buoc 1 "Tải Python $PY_VER bản nhúng"
$pyzip = Join-Path $TAM "python-embed.zip"
$PYDIR = Join-Path $DIST "runtime\python"
if (-not (Test-Path $pyzip)) {
    # curl.exe có sẵn từ Windows 10 1803, và nó ghi thẳng ra đĩa thay vì ôm cả
    # file vào RAM như Invoke-WebRequest.
    & curl.exe -L -s -o $pyzip "https://www.python.org/ftp/python/$PY_VER/python-$PY_VER-embed-amd64.zip"
    if ($LASTEXITCODE -ne 0) { throw "tải Python thất bại" }
}
Expand-Archive $pyzip -DestinationPath $PYDIR -Force

# Bản nhúng mặc định KHÔNG nạp site-packages. Bỏ dấu # ở dòng `import site`
# trong file ._pth, nếu không thì mọi thư viện chép vào đều vô hình.
$pth = Get-ChildItem $PYDIR -Filter "python*._pth" | Select-Object -First 1
$noi_dung = Get-Content $pth.FullName
$noi_dung = $noi_dung -replace '^#\s*import site', 'import site'
if ($noi_dung -notcontains "Lib\site-packages") { $noi_dung += "Lib\site-packages" }
Set-Content $pth.FullName $noi_dung -Encoding ASCII
Write-Host "    $(Mb $PYDIR) MB"

# ---------------------------------------------------------------- 2. thư viện

Buoc 2 "Chép thư viện từ venv"
$dich_sp = Join-Path $PYDIR "Lib\site-packages"
New-Item -ItemType Directory -Force -Path $dich_sp | Out-Null

# Danh sách này được SINH RA từ đồ thị phụ thuộc, không phải viết bằng tay.
# Xem scratchpad/cay_phu_thuoc.py: bắt đầu từ các gói mã nguồn import trực
# tiếp, rồi đọc Requires-Dist của từng gói để đi xuống hết mọi nhánh.
#
# Vì sao không viết tay: đã thử, và mất ba lượt đóng lại cả bộ 4 GB vì thiếu
# torchgen, rồi _soundfile, rồi torio và tqdm. Mỗi lượt là mấy phút chờ, mà
# lỗi chỉ lộ ra sau khi đóng xong.
#
# Các gói nvidia-* và triton nằm trong đồ thị nhưng KHÔNG có trong venv, và
# không cần: bản torch cho Windows gói sẵn mọi DLL của CUDA vào torch\lib.
$GOI = @(
    "_cffi_backend", "_soundfile", "_soundfile_data", "_yaml", "annotated_types", "antlr4",
    "anyio", "cffi", "click", "cloudpickle", "colorama", "dateutil",
    "demucs", "dora", "einops", "fastapi", "filelock", "formulaic",
    "fsspec", "functorch", "h11", "idna", "importlib_metadata", "interface_meta",
    "jinja2", "julius", "lameenc", "llvmlite", "markupsafe", "matchering",
    "mpmath", "multipart", "narwhals", "networkx", "numba", "numpy",
    "omegaconf", "openunmix", "packaging", "pandas", "patsy", "pycparser",
    "pydantic", "pydantic_core", "pyloudnorm", "python_multipart", "resampy", "retrying",
    "scipy", "six", "sniffio", "soundfile", "starlette", "statsmodels",
    "submitit", "sympy", "torch", "torchaudio", "torchgen", "torio",
    "tqdm", "treetable", "typing_extensions", "typing_inspection", "tzdata", "uvicorn",
    "wrapt", "yaml", "zipp"
)
$thieu = @()
foreach ($g in $GOI) {
    $tu = Join-Path $SP $g
    if (Test-Path $tu) {
        if ((Get-Item $tu) -is [System.IO.DirectoryInfo]) {
            robocopy $tu (Join-Path $dich_sp $g) /E /NFL /NDL /NJH /NJS /MT:16 | Out-Null
            if ($LASTEXITCODE -ge 8) { throw "chép $g thất bại" }
        } else {
            Copy-Item $tu $dich_sp -Force
        }
        continue
    }
    # Không phải gói nào cũng là một THƯ MỤC.
    #   `retrying`, `six`, `soundfile`  -> một file .py
    #   `_cffi_backend`                 -> một file .pyd đã biên dịch
    # Tìm không thấy thư mục rồi bỏ qua là máy khách chết ở dòng import, mà
    # mãi mới lần ra vì sao.
    $roi = @(Get-ChildItem $SP -File -EA SilentlyContinue |
             Where-Object { $_.Name -eq "$g.py" -or $_.Name -like "$g.cp*.pyd" -or
                            $_.Name -like "$g-*.pyd" -or $_.Name -eq "$g.pyd" })
    if ($roi.Count) {
        $roi | ForEach-Object { Copy-Item $_.FullName $dich_sp -Force }
    } else {
        $thieu += $g
    }
}
if ($thieu.Count) {
    Write-Host "    KHÔNG tìm thấy trong venv: $($thieu -join ', ')" -ForegroundColor Yellow
}

# Thư mục `<gói>.libs` nằm NGANG HÀNG với gói, không nằm trong nó.
#
# numpy và scipy để OpenBLAS ở `numpy.libs\` và `scipy.libs\` cạnh bên. Chép
# mỗi thư mục gói là thiếu, và lỗi báo ra đánh lạc hướng hoàn toàn: numpy nói
# "bạn không nên import numpy từ thư mục mã nguồn của nó", trong khi nguyên
# nhân thật là thiếu một file DLL.
foreach ($g in $GOI) {
    $libs = Join-Path $SP "$g.libs"
    if (Test-Path $libs) {
        robocopy $libs (Join-Path $dich_sp "$g.libs") /E /NFL /NDL /NJH /NJS /MT:8 | Out-Null
    }
}

Write-Host "    $(Mb $dich_sp) MB trước khi cắt"

# Runtime C++ của Microsoft.
#
# Python bản nhúng chỉ kèm vcruntime140. Nhưng torch (shm.dll) và numpy đều
# cần THÊM msvcp140.dll, mà bản nhúng không có. Máy dev chạy được chỉ vì trong
# máy đã cài sẵn gói VC++ Redistributable — máy khách sạch thì không, và lỗi
# báo ra là "WinError 126 ... hoặc một trong các phụ thuộc của nó", không hề
# nói thiếu file gì.
#
# Mấy DLL này được phép mang kèm theo ứng dụng (app-local deployment).
$VC = @("msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
        "vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll",
        "msvcp140_codecvt_ids.dll")
$da_chep = 0
foreach ($d in $VC) {
    $tu = Join-Path $env:WINDIR "System32\$d"
    if (Test-Path $tu) { Copy-Item $tu $PYDIR -Force; $da_chep++ }
}
Write-Host "    kèm $da_chep DLL runtime C++ của Microsoft"

# ---------------------------------------------------------------- 3. cắt gọn

Buoc 3 "Cắt phần không cần khi chạy"
$truoc = Mb $dich_sp

# File .lib là thư viện liên kết, chỉ dùng lúc BIÊN DỊCH tiện ích mở rộng C++.
# Máy khách không biên dịch gì cả. Riêng dnnl.lib đã 623 MB.
Get-ChildItem $dich_sp -Recurse -File -Include *.lib, *.a -EA SilentlyContinue |
    Remove-Item -Force -EA SilentlyContinue

# CHỈ cắt thứ không phải mã Python: header C++, file cấu hình biên dịch, và
# mấy tiện ích dòng lệnh của torch.
#
# ĐỪNG cắt các gói con của torch dù trông có vẻ thừa. Đã thử cắt `torch.onnx`,
# `torch.ao`, `torch._inductor`, `torch.distributed` — gãy ngay ở
# `torch.utils.data.dataloader`, vì nó import `torch.distributed` ở dòng đầu.
# Cả cụm đó cộng lại chỉ chừng 50 MB, không đáng để đổi lấy rủi ro.
$BO = @("torch\include", "torch\test", "torch\share", "torch\bin")
foreach ($b in $BO) {
    $d = Join-Path $dich_sp $b
    if (Test-Path $d) { Remove-Item $d -Recurse -Force -EA SilentlyContinue }
}

# DLL CUDA: chỉ bỏ những cái KHÔNG AI liên kết tới.
#
# ĐÃ THỬ VÀ SAI: bỏ cusparse, cusolver, curand với lý do "dây chuyền không
# dùng phép toán đó". Nhưng torch_cuda.dll LIÊN KẾT tới cả ba, nên thiếu một
# cái là `import torch` chết ngay từ dòng đầu — mà thông báo lỗi chỉ nói
# "shm.dll hoặc một trong các phụ thuộc của nó", không hề nhắc tên file thật
# sự thiếu, nên mất khá lâu mới lần ra.
#
# Bài học: DLL bỏ được phải là DLL KHÔNG AI LIÊN KẾT TỚI, chứ không phải DLL
# chứa hàm mình không gọi. Hai chuyện khác hẳn nhau.
#
# cupti là bộ đo hiệu năng, nvToolsExt là công cụ đánh dấu cho trình phân tích
# — không nằm trong bảng nhập của torch_cuda.dll nên bỏ được.
$DLL_BO = @("cupti*.dll", "nvperf*.dll", "nvToolsExt*.dll", "nccl*.dll")
if ($Cpu) {
    # Bản CPU: bỏ hết DLL CUDA và cả torch_cuda.dll.
    $DLL_BO += @("cu*.dll", "torch_cuda*.dll", "nv*.dll", "cudnn*.dll")
}
foreach ($m in $DLL_BO) {
    Get-ChildItem (Join-Path $dich_sp "torch\lib") -Filter $m -File -EA SilentlyContinue |
        Remove-Item -Force -EA SilentlyContinue
}

# Bộ nhớ đệm bytecode chép từ máy dev sang là vô dụng — đường dẫn khác nhau.
Get-ChildItem $dich_sp -Recurse -Directory -Filter "__pycache__" -EA SilentlyContinue |
    Remove-Item -Recurse -Force -EA SilentlyContinue

$sau = Mb $dich_sp
Write-Host "    $truoc MB -> $sau MB (bớt $($truoc - $sau) MB)"

# ---------------------------------------------------------------- 4. ffmpeg

Buoc 4 "Chép ffmpeg"
$bin = Join-Path $DIST "runtime\ffmpeg\bin"
New-Item -ItemType Directory -Force -Path $bin | Out-Null
# Chỉ ffmpeg và ffprobe. ffplay là trình phát, dây chuyền không gọi tới bao giờ.
Copy-Item (Join-Path $FFmpeg "ffmpeg.exe") $bin -Force
Copy-Item (Join-Path $FFmpeg "ffprobe.exe") $bin -Force
Write-Host "    $(Mb $bin) MB"

# ---------------------------------------------------------------- 5. mã nguồn

Buoc 5 "Chép mã nguồn và giao diện"
foreach ($t in @("app", "web", "dongoi")) {
    robocopy (Join-Path $GOC $t) (Join-Path $DIST $t) /E /NFL /NDL /NJH /NJS `
        /XD __pycache__ /XF *.pyc | Out-Null
}
foreach ($f in @("launcher.py", "batch.py", "README.md")) {
    Copy-Item (Join-Path $GOC $f) $DIST -Force
}
# dongoi\ chỉ cần khi DỰNG gói, máy khách không dùng tới.
Remove-Item (Join-Path $DIST "dongoi") -Recurse -Force -EA SilentlyContinue

# ---------------------------------------------------------------- 6. model

Buoc 6 "Chép trọng số model"
$md = Join-Path $DIST "data\cache"
New-Item -ItemType Directory -Force -Path $md | Out-Null
$hub = Join-Path $GOC "data\cache\hub"
if (Test-Path $hub) {
    robocopy $hub (Join-Path $md "hub") /E /NFL /NDL /NJH /NJS /MT:8 | Out-Null
    Write-Host "    $(Mb (Join-Path $md 'hub')) MB — máy khách khỏi phải tải, chạy được offline"
} else {
    Write-Host "    KHÔNG thấy model ở $hub — máy khách sẽ phải tải 80 MB ở lần chạy đầu" -ForegroundColor Yellow
}
New-Item -ItemType Directory -Force -Path (Join-Path $DIST "data\Test\Input"),
                                          (Join-Path $DIST "data\Test\Output") | Out-Null
foreach ($f in @("data\Test\DOC-TRUOC.txt", "data\Test\settings.txt")) {
    if (Test-Path (Join-Path $GOC $f)) { Copy-Item (Join-Path $GOC $f) (Join-Path $DIST $f) -Force }
}

# ---------------------------------------------------------------- 7. .exe

Buoc 7 "Dựng Mastering.exe"
$csc = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (Test-Path $csc) {
    $tham = @("/nologo", "/target:winexe", "/optimize+",
              "/out:$(Join-Path $DIST 'Mastering.exe')",
              "/reference:System.Windows.Forms.dll", "/reference:System.dll",
              # System.Drawing: màn hình chờ của .exe dùng Font/Color/Point.
              "/reference:System.Drawing.dll",
              (Join-Path $GOC "dongoi\LauncherExe.cs"))
    & $csc @tham | Out-Null
    if (-not (Test-Path (Join-Path $DIST "Mastering.exe"))) { throw "csc không tạo được .exe" }
    Write-Host "    xong"
} else {
    Write-Host "    KHÔNG có csc.exe — máy khách chạy bằng Chay.bat" -ForegroundColor Yellow
}

# Vẫn kèm .bat: khi có trục trặc, chạy bằng .bat mới thấy được thông báo lỗi,
# còn .exe gọi pythonw.exe nên không có cửa sổ lệnh nào để đọc.
@"
@echo off
chcp 65001 >nul
cd /d "%~dp0"
runtime\python\python.exe launcher.py
if errorlevel 1 pause
"@ | Set-Content (Join-Path $DIST "Chay.bat") -Encoding ASCII

@"
@echo off
chcp 65001 >nul
cd /d "%~dp0"
runtime\python\python.exe batch.py
echo.
pause
"@ | Set-Content (Join-Path $DIST "Chay-thu-muc.bat") -Encoding ASCII

# Tờ đọc-trước. Sinh ra từ đây chứ không viết tay vào dist: bản viết tay
# bị mất sạch mỗi lần đóng gói lại, và đã mất một lần rồi.
@'
MASTERING
Tach stem de lam day giong hat, roi master ban nhac.

CACH CHAY
  Nhay dup  Mastering.exe

  Mo len se thay mot khung nho ghi "Starting...". Lan dau cho toi mot phut:
  no dang nap model va thu vien CUDA. Khung do TU BIEN MAT khi cua so ung
  dung hien ra - dung nhay dup them lan nua.

  Khong can cai gi them. Python, thu vien va model deu nam san trong thu muc
  nay. Khong can mang.

  Neu co truc trac, khung do se doi mau va bay thong bao loi ra ngay tren no
  - boi den, chep, gui lai cho toi. Ban day du nam trong  data\khoi-dong.log

CHEP SANG MAY KHAC
  Chep NGUYEN CA THU MUC nay. Chep rieng file .exe thi khong chay duoc.

CAN GI
  Windows 10 tro len, 64-bit.
  Card NVIDIA thi nhanh hon nhieu, khong co van chay duoc.

CHAY CA ALBUM
  Bo cac bai vao  data\Test\Input\
  Sua tuy chon trong  data\Test\settings.txt
  Roi bam  Chay-thu-muc.bat

LUU Y QUAN TRONG
  Dua vao BAN MIX chua master. Bai da master roi ma master lai lan nua thi
  chi te di - tool se tu canh bao khi phat hien.
'@ | Set-Content (Join-Path $DIST "DOC-TRUOC.txt") -Encoding ASCII

# ---------------------------------------------------------------- 8. tổng kết

Buoc 8 "Xong"
$tong = Mb $DIST
Write-Host "    $DIST"
Write-Host "    $tong MB ($([math]::Round($tong / 1024, 2)) GB)"

if ($Nen) {
    Buoc 9 "Nén"
    $zip = Join-Path $GOC "dist\Mastering.zip"
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Compress-Archive -Path $DIST -DestinationPath $zip -CompressionLevel Optimal
    Write-Host "    $zip — $(Mb $zip) MB"
}
