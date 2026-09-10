/* Chuỗi xử lý dựng bằng Web Audio, chạy ngay trong trình duyệt.
 *
 * VÌ SAO CÓ FILE NÀY: máy chủ xử lý thì mỗi lần kéo một thanh là phải chạy lại
 * cả dây chuyền — tách stem, làm dày giọng, trộn, master — mất 20-30 giây. Với
 * người ngồi chỉnh thì đó không phải công cụ, đó là chờ đợi. Đưa chuỗi vào
 * trình duyệt thì kéo thanh là nghe ngay.
 *
 * PHÂN CÔNG: máy chủ vẫn tách stem (Demucs cần GPU) và vẫn render bản cuối để
 * tải về. Trình duyệt chỉ lo phần NGHE THỬ, từ hai stem thô mà máy chủ gửi về.
 *
 * KHỚP TỚI ĐÂU so với bản render:
 *   chính xác  — cắt trầm, EQ, bề rộng, mức giọng, độ to (cùng công thức
 *                biquad RBJ; riêng đường cong cân phổ thì nạp thẳng bộ lọc FIR
 *                4097 hệ số của máy chủ vào ConvolverNode nên khớp từng dB)
 *   xấp xỉ     — khử xì, hai tầng nén giọng, nén tổng, hạn đỉnh (trình duyệt
 *                không có khối tương đương; dùng DynamicsCompressorNode)
 *
 * Nên bản nghe thử có thể đặc/thoáng hơi khác file tải về. Đó là đánh đổi có
 * chủ ý, và giao diện nói rõ chỗ này.
 */
const Chuoi = (() => {
  "use strict";

  function db2he(db) { return Math.pow(10, db / 20); }

  /** Một tầng nén xấp xỉ. Bản máy chủ dùng đường bao tính ở tốc độ điều khiển
   *  với ngưỡng, tỉ lệ, gối mềm riêng; ở đây ánh xạ sang khối có sẵn gần nhất. */
  function nen(ctx, nguong, tiLe, goc, nhanh, nha) {
    const n = ctx.createDynamicsCompressor();
    n.threshold.value = nguong;
    n.ratio.value = tiLe;
    n.knee.value = goc;
    n.attack.value = nhanh;
    n.release.value = nha;
    return n;
  }

  function loc(ctx, loai, f, Q, db) {
    const b = ctx.createBiquadFilter();
    b.type = loai;
    b.frequency.value = f;
    if (Q !== undefined && Q !== null) b.Q.value = Q;
    if (db !== undefined && db !== null) b.gain.value = db;
    return b;
  }

  function noi(ds) {
    for (let i = 0; i < ds.length - 1; i++) ds[i].connect(ds[i + 1]);
    return { dau: ds[0], cuoi: ds[ds.length - 1] };
  }

  /** Dựng cả đồ thị trong một ngữ cảnh bất kỳ.
   *
   *  Dùng được cho cả AudioContext (nghe) lẫn OfflineAudioContext (render lấy
   *  đỉnh sóng). Cùng một hàm dựng nên hai đằng chắc chắn giống nhau — dựng
   *  hai lần bằng hai đoạn mã là kiểu gì cũng có ngày lệch.
   */
  function dung(ctx, demVocal, demNhac, demLoc, ts) {
    const k = {};              // các khối cần chỉnh về sau

    // ----------------------------------------------------------- track giọng
    k.nguonVocal = ctx.createBufferSource();
    k.nguonVocal.buffer = demVocal;

    k.catTram = loc(ctx, "highpass", 85, 0.707);
    const catTram = k.catTram;

    // Khử xì trong bản NGHE THỬ là một lát EQ tĩnh ở 7 kHz, không phải máy
    // khử xì động như bản máy chủ.
    //
    // Bản đầu tôi dựng đúng kiểu động: tách dải xì, nén nó, trừ phần thừa khỏi
    // đường khô. Nhưng DynamicsCompressorNode của Chromium tự cộng makeup nên
    // "dải xì đã nén" TO HƠN dải xì gốc, phép trừ hoá thành phép cộng, và nó
    // đẩy vống dải 5,5-9,5 kHz. Sai ngược hẳn tác dụng cần có.
    //
    // Lát EQ tĩnh thì không bám theo tiếng xì, nhưng ít nhất nó đi đúng chiều
    // và đoán trước được.
    k.xiMuc = loc(ctx, "peaking", 7000, 1.2, 0);
    const tronVocal = ctx.createGain();
    catTram.connect(k.xiMuc);
    k.xiMuc.connect(tronVocal);

    k.eqDuc = loc(ctx, "peaking", 300, 1.0, 0);
    k.eqNet = loc(ctx, "peaking", 3200, 0.9, 0);
    k.eqThoang = loc(ctx, "highshelf", 11000, 0.707, 0);
    // HAI TẦNG NÉN GIỌNG: bản nghe thử KHÔNG nén, chỉ cộng đúng lượng bù mà
    // hai tầng đó cộng ở máy chủ (+2,5 và +1,5 dB).
    //
    // Lý do đo được chứ không phải chọn cho tiện: DynamicsCompressorNode của
    // Chromium tự cộng một lượng makeup rất mạnh và không tắt được. Bật hai
    // tầng đó lên thì giọng — vốn nằm ở dải giữa — bị đẩy vống, và cán bằng
    // phổ của cả bài lệch 4,2 dB so với bản máy chủ render (trầm +6,17 tụt
    // xuống +1,95 dB so với dải giữa). Đo bằng cách bật/tắt từng khối một.
    //
    // Đổi lại: bản nghe thử có giọng kém đều hơn bản tải về. Đó là chỗ xấp xỉ
    // đã biết, và nó không đụng tới thứ người dùng đang chỉnh (cân bằng phổ,
    // mức giọng, độ to).
    // Một khối bù duy nhất, đặt bằng SỐ ĐO máy chủ gửi về (`bu_giong`): khối
    // giọng bên đó làm track to/nhỏ đi đúng bao nhiêu dB.
    //
    // Không suy ra được từ tham số. Hai tầng nén vừa hạ phần to vừa cộng bù
    // (+2,5 và +1,5 dB), nên mức cuối phụ thuộc bài đó ồn tới đâu. Lần đầu
    // tôi đặt cứng +4 dB theo đúng lượng bù, bỏ qua phần hạ — giọng vống lên
    // và cán cân phổ lệch 3,5 dB so với bản máy chủ.
    k.buGiong = ctx.createGain();
    k.buGiong.gain.value = 1;
    const nenCham = k.buGiong, nenNhanh = ctx.createGain();
    k.mucGiong = ctx.createGain();

    const sauVocal = noi([tronVocal, k.eqDuc, k.eqNet, k.eqThoang,
                          nenCham, nenNhanh, k.mucGiong]);

    // Nhân đôi: hai bản sao trễ, dao động chậm, trải hai bên. Cùng ý tưởng với
    // bản Python, khác chỗ ở đó tự nội suy còn ở đây DelayNode lo.
    const tronDay = ctx.createGain();
    k.mucGiong.connect(tronDay);
    k.day = [];
    [[0.011, 0.23], [0.015, 0.31]].forEach(([tre, hz], i) => {
      const d = ctx.createDelay(0.1);
      d.delayTime.value = tre;
      const lfo = ctx.createOscillator();
      lfo.frequency.value = hz;
      const sau = ctx.createGain();
      sau.gain.value = 0.0012;
      lfo.connect(sau);
      sau.connect(d.delayTime);
      lfo.start(ts);
      const toi = loc(ctx, "lowpass", 7000, 0.707);
      const cao = loc(ctx, "highpass", 150, 0.707);
      const m = ctx.createGain();
      m.gain.value = 0;
      const trai = ctx.createGain();
      const phai = ctx.createGain();
      trai.gain.value = i === 0 ? 0.85 : 0.15;
      phai.gain.value = i === 0 ? 0.15 : 0.85;
      const gop = ctx.createChannelMerger(2);
      k.mucGiong.connect(d);
      d.connect(toi); toi.connect(cao); cao.connect(m);
      m.connect(trai); m.connect(phai);
      trai.connect(gop, 0, 0);
      phai.connect(gop, 0, 1);
      gop.connect(tronDay);
      k.day.push(m);
    });

    // ----------------------------------------------------------- nhạc nền
    k.nguonNhac = ctx.createBufferSource();
    k.nguonNhac.buffer = demNhac;
    const tron = ctx.createGain();
    tronDay.connect(tron);
    k.nguonNhac.connect(tron);
    k.nguonVocal.connect(catTram);

    // Lối rẽ "chỉ nghe giọng": lấy ngay sau khối nhân đôi.
    k.chiGiong = ctx.createGain();
    tronDay.connect(k.chiGiong);

    // ----------------------------------------------------------- khâu master
    // Đường cong cân phổ nạp thẳng bộ lọc của máy chủ -> khớp từng dB.
    const canPho = ctx.createConvolver();
    canPho.normalize = false;
    canPho.buffer = demLoc;
    k.canPhoMuc = ctx.createGain();      // 0 = tắt (thanh Tone)
    const boCanPho = ctx.createGain();
    tron.connect(canPho);
    canPho.connect(k.canPhoMuc);
    tron.connect(boCanPho);
    const sauPho = ctx.createGain();
    k.canPhoMuc.connect(sauPho);
    k.boPho = boCanPho;
    boCanPho.connect(sauPho);

    k.eqTram = loc(ctx, "lowshelf", 110, 0.707, 0);
    k.eqCao = loc(ctx, "highshelf", 9000, 0.707, 0);

    // Bề rộng bằng giữa/hai bên: tách M và S, chỉnh S, ghép lại.
    const tachL = ctx.createChannelSplitter(2);
    const giua = ctx.createGain();
    const ben = ctx.createGain();
    const benDao = ctx.createGain();
    benDao.gain.value = -1;
    giua.gain.value = 0.5;
    ben.gain.value = 0.5;
    k.rong = ctx.createGain();
    const traiRa = ctx.createGain();
    const phaiRa = ctx.createGain();
    const gopMS = ctx.createChannelMerger(2);

    const sauEQ = noi([sauPho, k.eqTram, k.eqCao]);
    sauEQ.cuoi.connect(tachL);
    tachL.connect(giua, 0); tachL.connect(giua, 1);
    tachL.connect(ben, 0); tachL.connect(benDao, 1);
    benDao.connect(ben);
    ben.connect(k.rong);
    // L = M + S, R = M - S. Nhánh S vào kênh phải phải đảo dấu, nên nối qua
    // một khối nhân -1 chứ không nối thẳng rồi gỡ ra.
    const rongDao = ctx.createGain();
    rongDao.gain.value = -1;
    k.rong.connect(rongDao);
    giua.connect(traiRa); k.rong.connect(traiRa);
    giua.connect(phaiRa); rongDao.connect(phaiRa);
    traiRa.connect(gopMS, 0, 0);
    phaiRa.connect(gopMS, 0, 1);

    // Nén tổng: bản nghe thử KHÔNG nén. Cùng lý do — makeup tự động của
    // Chromium làm lệch cán cân phổ, mà nén tổng chỉ đóng góp 0,3 dB tác dụng
    // thật (đo bằng cách bật/tắt). Bỏ đi thì mất rất ít, đổi lại bản nghe thử
    // đúng phổ.
    k.nenTong = ctx.createGain();
    const nenTong = k.nenTong;
    k.doTo = ctx.createGain();
    // Hạn đỉnh: xén mềm bằng đường cong tanh thay cho máy nén. Nó chỉ chạm
    // vào phần vượt trần nên không đổi màu tiếng, và có tác dụng đúng cái cần
    // ở đây: kéo độ to lên cao thì nghe được là đang chạm trần.
    k.hanDinh = ctx.createWaveShaper();
    {
      const N = 2048, c = new Float32Array(N);
      for (let i = 0; i < N; i++) {
        const x = (i / (N - 1)) * 2 - 1;
        c[i] = Math.tanh(x * 1.18) / Math.tanh(1.18);
      }
      k.hanDinh.curve = c;
      k.hanDinh.oversample = "4x";
    }
    const hanDinh = k.hanDinh;
    k.ra = ctx.createGain();
    noi([gopMS, nenTong, k.doTo, hanDinh, k.ra]);

    return k;
  }

  return { dung, db2he };
})();
