# Mastering

Làm dày giọng hát và nâng chất lượng âm thanh của một bản nhạc đã trộn xong.

Chạy: bấm đúp `Run.bat`.

---

## Một hiểu lầm phải gỡ trước

"Mastering" và "làm dày giọng hát" là **hai việc khác nhau**, và đây là lý do
phổ biến nhất khiến một tool tự làm cho ra kết quả nghe chán.

| | Xử lý cái gì | Có làm dày giọng được không |
|---|---|---|
| **Mastering** | bản đã trộn xong, hai kênh trái phải | **Không.** Giọng đã hoà vào nhạc, không tách ra mà chỉnh riêng được nữa |
| **Vocal mixing** | riêng track giọng | Đây mới là chỗ làm dày giọng |

MasteringBOX, LANDR, eMastered đều là mastering. Chúng làm bản nhạc to hơn, cân
bằng hơn, "ra chất đĩa" hơn — nhưng không cái nào làm dày riêng giọng hát được,
vì về mặt vật lý chúng không có track giọng riêng để mà chỉnh.

Thêm một điều: **mastering gần như không có "model AI"** theo nghĩa thường
nghĩ. Nó là chuỗi xử lý tín hiệu số cổ điển — lọc tần số, nén dải động, bão hoà,
hạn đỉnh. Phần gọi là "AI" ở các dịch vụ trả tiền chỉ là bước phân tích bản nhạc
rồi chọn tham số cho chuỗi đó.

Tool này giải quyết bằng cách **tách stem trước**, để lấy lại track giọng riêng
rồi mới xử lý:

```
bản nhạc ──► Demucs tách stem ──┬──► giọng ──► dây chuyền làm dày ──┐
                                │                                   ├──► trộn lại ──► master ──► file ra
                                └──► nhạc nền ──────────────────────┘
```

## Hai chế độ

| Chế độ | Làm gì |
|---|---|
| **Vocal + Master** | Tách stem, xử lý riêng giọng, trộn lại, rồi master. Chậm hơn, nhưng đây mới là chỗ giọng dày lên. |
| **Master only** | Chỉ master bản phối như nó vốn có. Nhanh, và không đụng được vào giọng. |

## Dây chuyền cho giọng

Thứ tự các khối không tuỳ tiện — mỗi khối đứng ở đó vì một lý do:

| Khối | Vì sao đứng ở đây |
|---|---|
| Cắt trầm 85 Hz | Bỏ tiếng gió và ù, để máy nén khỏi bám vào thứ không nghe được |
| Khử xì (de-esser) | Đứng **trước** EQ sáng, vì EQ sáng làm tiếng xì to lên |
| EQ | Dọn dải đục 300 Hz, thêm dải nét 3,2 kHz, mở dải thoáng 11 kHz |
| Nén hai tầng | Tầng chậm san mức giữa các câu, tầng nhanh bắt đỉnh phụ âm |
| Bão hoà (**Warmth**) | Màu tiếng ấm hơn. **Mặc định TẮT** — xem "Vì sao Warmth mặc định tắt" |
| **Nhân đôi** (**Thickness**) | **Nguồn của cảm giác "dày"** — xem dưới |
| Vang (**Space**) | Đặt giọng vào một không gian, làm sau cùng |

**Nhân đôi giọng** hoạt động thế nào: tạo hai bản sao của giọng, mỗi bản lệch
cao độ vài cent và lệch thời gian ~20 ms, rồi đẩy sang hai bên trái phải. Mốc
20 ms là ngưỡng Haas — tai gộp chúng thành **một** giọng rộng hơn chứ không nghe
thành tiếng vọng. Quá 40 ms là bắt đầu nghe ra hai giọng.

Đo trên một bài đã phát hành thật: bề rộng track giọng đi từ **0,302 lên
0,395**, mà chỉ tốn **0,3 dB** dải động của cả bản nhạc. Đây là khối đáng đồng
tiền nhất trong cả dây chuyền.

## Vì sao Warmth mặc định tắt

Bão hoà là khối duy nhất trong dây chuyền mà tôi đo được cái giá nhưng **không
đo được cái lợi**. Trên chính bài đã phát hành ở trên, tách riêng từng khối và
đo dải động của cả bản nhạc sau khi master:

| Khối | Dải động còn lại | Bề rộng giọng |
|---|---|---|
| chỉ EQ + nén | 8,4 dB | 0,323 |
| + **bão hoà** | **5,8 dB** (mất 2,6) | 0,326 (gần như không đổi) |
| + nhân đôi | 8,1 dB (mất 0,3) | **0,388** |
| + vang | 7,9 dB (mất 0,5) | 0,328 |

Quét lại liều lượng thì liều **nhẹ nhất** đã tốn 1,3 dB, và đẩy mạnh lên chỉ tốn
thêm chứ phổ không giàu thêm.

Cái bão hoà cho là "ấm", "dày" theo cảm nhận — thứ chỉ tai người thẩm định được,
không đo bằng số được. Nên nó có nút riêng và mặc định để 0: bạn tự bật khi nghe
thấy cần, chứ tool không âm thầm lấy đi dải động của bạn để đổi lấy một thứ nó
không chứng minh được.

## Preset

Bốn nút đặt sẵn: **Natural / Balanced / Warm / Open**. Bấm một cái là mọi thanh
kéo nhảy về bộ giá trị tương ứng — rồi bạn vẫn kéo tay tiếp được.

Cố ý không giấu tham số nào đi. Bấm preset xong bạn **nhìn thấy** nó vừa đặt
những gì, nên dùng vài lần là hiểu thanh nào làm gì. Các dịch vụ trả tiền đi
hướng ngược lại: giấu hết, chỉ cho chọn "style" — dễ cho lần đầu, nhưng người
dùng không bao giờ học được gì và mãi mãi phụ thuộc.

## Ba nút cho cả bản nhạc

| Nút | Làm gì | Đo được |
|---|---|---|
| **Bass** | ±4 dB ở dải trầm | +4 dB → năng lượng trầm tăng 14% |
| **Air** | ±4 dB ở dải cao | +4 dB → năng lượng cao tăng 33% |
| **Width** | nới/thu bề rộng stereo | 100 → 150 làm bề rộng đi từ 0,359 lên 0,527 |

Cảnh báo về **Width**: quá 130 là phần bên bắt đầu lấn. Khi ai đó nghe trên
**loa điện thoại** — một loa, tức là cộng hai kênh lại — phần bên triệt tiêu
nhau và bản nhạc đột nhiên rỗng ruột. Lỗi này chỉ lộ ra ở đúng thiết bị mà phần
lớn người nghe đang dùng, nên rất dễ giao hàng rồi mới biết.

## Chạy cả album theo thư mục

    data/Test/Input/     bỏ các bài vào đây
    data/Test/Output/    bản đã master hiện ra ở đây
    data/Test/settings.txt   sửa tuỳ chọn ở đây

Bấm `Run-Batch.bat`. Muốn khớp phổ theo một bài mẫu thì đặt tên file mẫu bắt
đầu bằng `_reference` — nó được dùng làm mẫu chứ không bị master.

**Chế độ album (`album = true`) không phải là "chạy từng bài rồi ghép lại".**

Một album thường cố ý có bài to bài nhỏ — bản ballad phải nhỏ hơn bài mở màn,
đó là dụng ý. Chuẩn hoá từng bài riêng lẻ về −14 LUFS là san phẳng hết chênh
lệch ấy: nghe hết album thấy đều đều một mức, mất hẳn nhịp lên xuống.

Nhưng làm đúng khó hơn nó nhìn, và tôi đã vấp đúng chỗ đó. Lần đầu viết, tôi
chỉ dịch cả album đi một lượng chung. Đo ra: chênh lệch gốc 8,00 dB, ra còn
**3,03 dB**. Nguyên nhân là mọi máy nén trong dây chuyền đều có ngưỡng cố định,
nên bài vào nhỏ hơn thì bị nén ít hơn mà vẫn được bù đủ — khoảng cách tự co lại.

Cách đúng phải làm ba việc:

1. Đo độ to gốc từng bài, ghi nhớ chênh lệch.
2. **Nâng mọi bài lên ngang bài to nhất** rồi mới xử lý, để bài nào cũng đi qua
   máy nén ở cùng một mức và chịu đúng một cách đối xử như nhau.
3. Trả lại chênh lệch gốc, rồi dịch cả album sao cho bài to nhất chạm mức đích.

Sau khi sửa: chênh lệch gốc 8,00 dB → bản ra **7,96 dB**, và cả ba bài mất đúng
1,6 dB dải động như nhau. Tool tự in ra hai con số này mỗi lần chạy, và cảnh
báo nếu lệch quá 1 dB.

## Bài mẫu (reference)

Ô **Reference track** là tuỳ chọn, nhưng nó là thứ tạo khác biệt lớn nhất ở khâu
master.

Có bài mẫu → dùng **Matchering**: đo phổ tần và độ lớn của bài mẫu rồi ép bài
của mình khớp theo. Đây đúng là cách các dịch vụ trả tiền hoạt động, khác mỗi
chỗ chúng tự chọn bài mẫu giùm mình.

Không có bài mẫu → dùng bộ tham số mặc định. Vẫn ra kết quả sạch, nhưng không
"đúng gu" một thể loại cụ thể nào.

Chọn bài mẫu thế nào: lấy một bài **cùng thể loại, cùng cách phối**, chất lượng
phát hành thật. Lấy một bài rock làm mẫu cho một bản ballad là ra kết quả sai.

## Độ lớn đích

| Mức | Dùng khi nào |
|---|---|
| −16 | podcast, nội dung nhiều lời nói |
| **−14** | **chuẩn nhạc trực tuyến** — Spotify, YouTube, Apple Music |
| −11 | muốn to hơn mặt bằng, chấp nhận mất một phần dải động |
| −9 | "to và nện", club/quảng cáo |

Cảnh báo thật: đặt −9 rồi phát lên Spotify thì nền tảng **hạ xuống −14**, và cái
còn lại là một bản đã bị nén mất dải động — nghe **bẹt hơn** chính bản −14. To
hơn chỉ có ý nghĩa khi người nghe không đi qua nền tảng chuẩn hoá.

Kiểm chứng: đặt đích nào thì ra đúng mức đó, kể cả trên chất liệu khó.

| Bài | Đích | Đo được | Đỉnh liên mẫu |
|---|---|---|---|
| ballad | −14 | −13,99 | −0,99 dBTP |
| rap đã xén mạnh | −14 | −14,01 | −0,98 dBTP |
| rap đã xén mạnh | −11 | −11,08 | −0,98 dBTP |

Chỗ này từng sai và đã sửa. Máy hạn đỉnh chỉ nhìn TỪNG MẪU, nên xong việc vẫn
còn đỉnh ẩn nằm giữa hai mẫu. Cách chữa cũ là đo đỉnh liên mẫu rồi hạ cả bản
nhạc xuống đúng bằng phần vượt — trên nhạc thường phần vượt chỉ 0,14 dB nên
không sao, nhưng gặp bài rap đã xén mạnh thì phần vượt lên tới **1,44 dB**, và
cả bản bị hạ đi ngần ấy. Người dùng chọn −14 LUFS mà nhận về **−15,44**.

Cách đúng: lấy mẫu dày lên gấp bốn RỒI mới hạn đỉnh, để máy hạn nhìn thấy các
đỉnh ẩn và chỉ hạ đúng những chỗ ấy thay vì hạ cả bài. Tốn thêm chừng 12 giây
cho bài 3 phút, đổi lại trúng đích và trần vẫn đúng.

## So A/B — đọc kỹ chỗ này

Nút **Before / After / Vocal only** đổi bản đang nghe mà **giữ nguyên vị trí
kim**. Đổi bản mà nhảy về đầu bài thì không so được gì cả.

Ô **Level-matched** bật sẵn, và nên để nguyên. Lý do: khi so hai bản, **bản nào
to hơn luôn nghe hay hơn**, bất kể nó có thật sự tốt hơn không. Đây là bẫy tâm
lý âm thanh kinh điển, và là cách mọi bản demo "trước/sau" trên mạng đánh lừa
người nghe. Ô này hạ bản to xuống cho bằng bản nhỏ trước khi so.

Sóng vẽ chồng: bản gốc màu xám mờ nằm sau, bản đang nghe màu tím nằm trước —
nhìn là thấy ngay dải động bị nén đi bao nhiêu.

## Số đo thật trên máy này

Máy đo: RTX 3050 Laptop 4 GB, Windows 10.

| Việc | Bài 4 phút |
|---|---|
| Cả dây chuyền (tách stem + làm dày giọng + master) | **75 giây** |
| Riêng master (chế độ Master only) | vài giây |
| VRAM đỉnh | dưới 3 GB |

Và trên một bài đã phát hành thật (28 giây, đưa vào ở −14,85 LUFS / 9,4 dB dải
động), đích −14 LUFS:

| Cách chạy | Độ lớn ra | Dải động còn lại |
|---|---|---|
| Vocal + Master, Warmth 0 | −14,0 | **7,8 dB** |
| Vocal + Master, Warmth 50 | −14,0 | 6,5 dB |
| Master only | −14,0 | 7,7 dB |

Đọc bảng này thế nào: cả khâu làm dày giọng gần như **không** tốn thêm dải động
so với chỉ master (7,8 so với 7,7). Phần mất đi 1,6 dB là cái giá của việc kéo
độ lớn lên, không phải của việc xử lý giọng.

Phần EQ, nén, bão hoà, hạn đỉnh, matchering **chạy hoàn toàn trên CPU** — chỉ
mỗi Demucs muốn GPU cho nhanh, mà không có cũng chạy.

## Tốc độ: đã tối ưu ở đâu, và không tối ưu ở đâu

Đo trên RTX 3050 Laptop 4 GB. Bài 3:11, chế độ đầy đủ, tách stem thật:
**40 giây** (trước khi tối ưu là ~60 giây quy về cùng độ dài).

Thời gian đi đâu:

| Khối | Thời gian | Chạy ở |
|---|---|---|
| Tách stem (Demucs) | ~5s | **GPU** |
| Cắt trầm · khử xì · EQ · nén ×2 · nhân đôi | 2,9s | CPU |
| Chuẩn độ lớn + hạn đỉnh liên mẫu | ~7s | CPU |
| Vang (nếu bật) | 4s | CPU |

**Hai chỗ đã tối ưu, có số đo:**

*Chế độ tính hỗn hợp cho Demucs* — nhanh gấp **2,27 lần** (3,54s → 1,56s trên
đoạn 30 giây), sai lệch **−62 dB** dưới tín hiệu, dưới ngưỡng tai nghe ra.
Dùng `torch.autocast` chứ không phải `model.half()`: htdemucs làm biến đổi
Fourier, mà số phức nửa độ chính xác trong PyTorch còn thử nghiệm nên ép
`.half()` là văng lỗi ngay. Cần bản trùng khớp từng bit thì đặt `DEMUCS_FP32=1`.

*Khối vang* — nhanh gấp **17 lần** (1,96s → 0,11s), kết quả **trùng khớp tuyệt
đối** (lệch 0,000). Bộ lặp hồi tiếp trước viết bằng `lfilter` với mẫu số dài
1900, mà `lfilter` chạy theo *số mẫu × bậc bộ lọc* — 16 tỉ phép cho một bộ,
mà có bốn bộ. Viết lại thành hồi tiếp theo từng khối 1900 mẫu: trong một khối
không mẫu nào phụ thuộc mẫu nào nên cộng cả khối một lần bằng numpy.

**Đã thử và LOẠI:** giảm chồng lấn giữa các lát Demucs (0,25 → 0,10) cũng
nhanh tương đương, nhưng sai lệch tới **−24 dB**, tức **nghe ra được**. Nhanh
mà đổi cả chất tiếng thì không phải tối ưu, là đánh đổi.

**Vì sao không đưa phần xử lý tín hiệu lên GPU:** đo ra thì chỗ chậm nhất còn
lại là hàm lấy mẫu dày gấp bốn của scipy (1,29s mỗi lượt) — đã là mã C. Các
vòng lặp Python chỉ tốn 0,2s. Còn máy nén và máy hạn đỉnh thì bản chất là tuần
tự (mẫu sau phụ thuộc mẫu trước), là dạng bài GPU làm rất kém.

## Giới hạn cần biết trước

- **Tách stem không hoàn hảo.** Demucs để lại một chút nhạc nền trong track
  giọng và ngược lại. Bản phối càng dày, càng nén mạnh thì tách càng kém, và mọi
  thứ xử lý sau đó thừa hưởng cái kém đó. Nghe thử **Vocal only** để tự đánh giá.
- **Không tự động hoàn toàn được.** Không có bộ tham số nào đúng cho mọi bài.
  Phải nghe, kéo lại, nghe lại. Năm thanh kéo là để làm việc đó.
- Kéo **Thickness** lên hết cỡ với một giọng vốn đã dày là ra tiếng nhoè, mất
  nét. Bắt đầu từ 50 rồi tăng dần.
- Bài đã master sẵn mà master lại lần nữa thì chỉ tệ đi. Đưa vào bản mix.

## So với các dịch vụ trả tiền

Tra cứu tháng 9/2026 trên MasteringBOX, LANDR, eMastered.

| | Họ | Tool này |
|---|---|---|
| Master tự động | ✓ | ✓ |
| Đích độ lớn | ✓ | ✓ |
| Preset / style | ✓ | ✓ (4 preset, có nhìn thấy tham số) |
| EQ chỉnh tay | chỉ bản trả phí | ✓ |
| Bề rộng stereo | eMastered có | ✓ |
| Bài mẫu tham chiếu | LANDR (tối đa 3) | ✓ |
| Album, giữ chênh lệch độ to | MasteringBOX có | ✓ |
| **Tách stem, xử lý riêng giọng** | **không ai có** | **✓** |
| So A/B cân mức | ✗ | ✓ |
| Hiện dải động mất đi | ✗ | ✓ |
| Chạy offline, không giới hạn | ✗ | ✓ |
| Xuất DDP cho ép đĩa | MasteringBOX có | ✗ |
| Trang nghệ sĩ, chia sẻ | MasteringBOX có | ✗ |

Hai thứ thiếu đều là tính năng nền tảng web, không phải xử lý âm thanh — làm
được nhưng chỉ đáng làm nếu khách thật sự cần.

Một điểm đáng biết về lõi: **Matchering**, thư viện tool này dùng cho phần khớp
bài mẫu, xếp **thứ 3 trên 12** trong bài kiểm tra mù của Benn Jordan (472 lượt
chấm) — chỉ sau hai kỹ sư master là người thật, và trên mọi dịch vụ AI thương
mại trong bài đó. Nói cách khác, phần lõi không phải hàng thay thế tạm.

## Cỡ màn hình

Đã thử thật bằng trình duyệt ở bốn cỡ: laptop 1366×768, laptop 1536×864,
màn rời 24" 1920×1080, màn rời 27" 2560×1440. Không cỡ nào bị tràn ngang.

| Bề ngang | Cột trái | Khối kết quả |
|---|---|---|
| < 1080 | xếp dọc, cuộn cả trang | tràn hết bề ngang |
| 1366 | 320px | 960px |
| 1536 | 340px | 1080px |
| 1920 | 384px | 1380px |
| 2560 | 420px | 1560px |

Hai cột giãn **khác nhau**, và đó là chủ ý:

- Cột trái nới vừa phải. Nó chứa các ô nhập bề ngang cố định; nới quá thì chữ
  với ô nhập trôi xa nhau, mắt phải nhảy qua lại.
- Khối kết quả **phải có trần**. Không chặn thì trên màn 27" một dòng chữ dàn
  ngang hơn hai nghìn điểm ảnh: đọc hết dòng rồi phải quét ngược cả màn hình
  để tìm đầu dòng sau. Chặn lại rồi căn giữa.

Nút chạy dính đáy cột trái. Màn laptop cao 768 điểm ảnh không đủ chỗ cho cả
cột điều khiển nên cột đó phải cuộn; không dính đáy thì mỗi lần chỉnh một thanh
kéo lại phải cuộn xuống mới bấm được.

## Cấu trúc mã nguồn

```
app/config.py     hằng số dùng chung, đường dẫn, cổng
app/audio.py      đọc/ghi audio bằng ffmpeg
app/separate.py   tách stem bằng Demucs, có cache theo mã băm file
app/dsp.py        các khối xử lý tín hiệu  ← lõi của tool
app/chain.py      ghép các khối thành dây chuyền, và khâu master
app/jobs.py       hàng đợi việc chạy nền
app/api.py        máy chủ HTTP
web/              giao diện: HTML/CSS/JS thuần, không có bước dựng
launcher.py       bật máy chủ rồi mở cửa sổ ứng dụng
batch.py          chạy cả album theo thư mục Test/Input -> Test/Output
```

## Cài trên máy mới

Xem đầu file `requirements.txt`. Có một cái bẫy: bản `demucs==4.0.1` trên PyPI
ghi chặn `torchaudio<2.1`, cài kiểu thường là pip hạ torchaudio xuống và torch
gãy theo — phải cài `--no-deps` rồi tự cài các gói phụ.
