// Giao diện Mastering. Không khung, không bước dựng — mở là chạy.

const $ = (id) => document.getElementById(id);

let tep = null;       // bài cần xử lý
let tepMau = null;    // bài mẫu để so phổ (tuỳ chọn)
let maViec = null;
let cheDo = "full";
let dichLufs = -14;
let soDo = null;      // LUFS trước/sau, để cân mức khi so A/B
let dinh = {};        // đỉnh sóng theo từng bản, vẽ lại khi đổi A/B

let dangNghe = "mastered";

/* ------------------------------------------------------------------ bộ phát
 *
 * Cả ba bản chạy SONG SONG trên MỘT đồng hồ, đổi A/B chỉ là chuyển âm lượng.
 *
 * Vì sao không dùng thẻ <audio> nữa: bản trước có ba thẻ, đổi bản là pause thẻ
 * này rồi play thẻ kia kèm gán currentTime. Gán currentTime là ra lệnh tua,
 * trình duyệt xả đệm giải mã rồi nạp lại — hụt tiếng chừng một nhịp. Và cắt
 * tiếng giữa chu kỳ sóng thì biên độ nhảy đột ngột về 0, nghe thành tiếng
 * "tách". Cái cần so là hai bản khác nhau ở đâu, mà mỗi lần bấm lại chen vào
 * một khoảng lặng và một tiếng tách — hai thứ to hơn chính khác biệt cần nghe.
 *
 * Bản này giải mã sẵn cả ba vào bộ nhớ, phát cùng lúc, mỗi bản qua một núm âm
 * lượng riêng. Đổi bản = hạ núm này, nâng núm kia trong 20 ms. Không tua,
 * không nạp lại, và ba bản khớp nhau tới từng mẫu vì cùng một đồng hồ — nên so
 * A/B là so ĐÚNG một khoảnh khắc trong bài.
 *
 * Giá phải trả là bộ nhớ: bài 4 phút, ba bản, 48 kHz nổi 32 bit ≈ 280 MB. Đổi
 * được: đằng nào cũng phải giải mã cả ba để vẽ sóng, giờ chỉ là giữ lại thay
 * vì bỏ đi.
 */
const may = (() => {
  let ctx = null;
  const dem = {};            // AudioBuffer từng bản
  const num = {};            // GainNode từng bản
  let nguon = {};            // BufferSource đang chạy
  let chay = false;
  let t0 = 0;                // ctx.currentTime lúc bấm phát
  let viTri = 0;             // mốc trong bài lúc bấm phát
  const he = {};             // hệ số cân mức từng bản
  let khiDoi = null;         // gọi lại khi phát/dừng, để đổi chữ trên nút

  // 20 ms: đủ dài để không nghe ra tiếng tách, đủ ngắn để tai coi là tức thì.
  const REO = 0.02;

  function may_ctx() {
    if (!ctx) {
      const C = window.AudioContext || window.webkitAudioContext;
      // Tạo được ngay mà không cần người dùng bấm gì; nó ở trạng thái treo và
      // decodeAudioData vẫn chạy. Chỉ resume() mới cần một cú bấm.
      ctx = new C();
    }
    return ctx;
  }

  function dat(k, gt, tuc_thi) {
    if (!num[k]) return;
    const g = num[k].gain;
    const t = ctx.currentTime;
    g.cancelScheduledValues(t);
    if (tuc_thi) { g.value = gt; return; }
    g.setValueAtTime(g.value, t);
    // Chuyển thẳng (linear) chứ không theo công suất: hai bản là cùng một bản
    // nhạc nên chúng cộng vào nhau, dùng đường công suất là giữa lúc chuyển bị
    // vồng lên chừng 3 dB.
    g.linearRampToValueAtTime(gt, t + REO);
  }

  /** Cho một bản vào giữa lúc đang phát, khớp đúng mốc của những bản kia.
   *
   *  Bắt đầu ở mốc `ts` với đoạn `off` thì tới thời điểm T nó đang ở
   *  off + (T - ts); cần bằng viTri + (T - t0), nên off = viTri + (ts - t0).
   */
  function _nhapLan(k) {
    if (nguon[k] || !dem[k]) return;
    const ts = ctx.currentTime + 0.02;
    const off = viTri + (ts - t0);
    if (off >= dem[k].duration - 0.01) return;
    const src = ctx.createBufferSource();
    src.buffer = dem[k];
    src.connect(num[k]);
    src.start(ts, off);
    nguon[k] = src;
  }

  function _ngat() {
    Object.values(nguon).forEach((x) => { try { x.stop(); } catch (_) {} });
    nguon = {};
    chay = false;
  }

  return {
    /** Giải mã trên ĐÚNG cái ctx sẽ phát. Giải mã ở ctx khác thì tần số lấy
     *  mẫu có thể lệch, và ba bản lệch tần số là hết khớp nhau. */
    giaiMa(buf) { return may_ctx().decodeAudioData(buf); },

    /** Giữ lại bản đã giải mã. Gọi từ docDinh(), chỗ đằng nào cũng phải giải mã. */
    nap(k, buf) {
      const c = may_ctx();
      dem[k] = buf;
      if (!num[k]) {
        num[k] = c.createGain();
        num[k].connect(c.destination);
      }
      if (he[k] === undefined) he[k] = 1;
      num[k].gain.value = (k === dangNghe) ? he[k] : 0;
      // Bản này giải mã xong SAU khi đã bấm Play thì nó chưa có nguồn nào
      // chạy — đổi sang là im tiếng. Cho nó nhập làn ngay, khớp đúng mốc mà
      // hai bản kia đang ở.
      if (chay) _nhapLan(k);
    },

    xoa() {
      _ngat();
      Object.keys(dem).forEach((k) => delete dem[k]);
      viTri = 0;
    },

    co(k) { return !!dem[k || dangNghe]; },
    // Chỉ để phép thử soi được: bản này có nguồn đang chạy hay không.
    _chan(k) { return !!nguon[k]; },
    dai() { return dem[dangNghe] ? dem[dangNghe].duration : 0; },
    dangPhat() { return chay; },
    gio() {
      if (!chay) return viTri;
      return Math.max(0, Math.min(this.dai(), viTri + (ctx.currentTime - t0)));
    },

    khiDoiTrangThai(f) { khiDoi = f; },

    phat() {
      if (chay || !dem[dangNghe]) return;
      const c = may_ctx();
      if (c.state === "suspended") c.resume();
      if (viTri >= this.dai() - 0.01) viTri = 0;
      // Lùi 30 ms rồi mới bắt đầu: đủ để cả ba nguồn được xếp lịch trước khi
      // đồng hồ chạy tới, nhờ vậy chúng vào cùng một mốc chứ không lệch nhau
      // vài mẫu theo thứ tự khởi tạo.
      const t = c.currentTime + 0.03;
      Object.keys(dem).forEach((k) => {
        const src = c.createBufferSource();
        src.buffer = dem[k];
        src.connect(num[k]);
        src.start(t, Math.min(viTri, dem[k].duration - 0.01));
        nguon[k] = src;
      });
      t0 = t;
      chay = true;
      if (khiDoi) khiDoi(true);
    },

    dung() {
      if (!chay) return;
      viTri = this.gio();
      _ngat();
      if (khiDoi) khiDoi(false);
    },

    batTat() { chay ? this.dung() : this.phat(); },

    /** Tua CẢ BA bản. So A/B ở hai mốc khác nhau thì vô nghĩa. */
    datGio(t) {
      const dp = chay;
      viTri = Math.max(0, Math.min(this.dai(), t || 0));
      if (dp) { _ngat(); this.phat(); }
    },

    doiBan(k) {
      if (!dem[k] || k === dangNghe) return;
      may_ctx();
      const cu = dangNghe;
      dangNghe = k;
      dat(cu, 0);
      dat(k, he[k]);
    },

    /** Hạ bản to xuống cho bằng bản nhỏ, hoặc thả về nguyên mức. */
    canMuc(bat, lech) {
      const hs = Math.pow(10, -Math.abs(lech) / 20);
      he.original = bat && lech < 0 ? hs : 1;
      he.mastered = bat && lech > 0 ? hs : 1;
      he.vocal = 1;
      if (!ctx) return;
      Object.keys(dem).forEach((k) => dat(k, k === dangNghe ? he[k] : 0));
    },
  };
})();

function gio(t) {
  if (!isFinite(t)) return "0:00";
  const p = Math.floor(t / 60), s = Math.floor(t % 60);
  return p + ":" + String(s).padStart(2, "0");
}

function gioLe(t) {
  return gio(t) + "." + String(Math.floor((t % 1) * 100)).padStart(2, "0");
}

// ------------------------------------------------------------------ chọn file

function gan(vungId, inputId, xong) {
  const v = $(vungId);
  v.onclick = () => $(inputId).click();
  $(inputId).onchange = (e) => xong(e.target.files[0]);
  ["dragenter", "dragover"].forEach((s) =>
    v.addEventListener(s, (e) => { e.preventDefault(); v.classList.add("keo"); }));
  ["dragleave", "drop"].forEach((s) =>
    v.addEventListener(s, (e) => { e.preventDefault(); v.classList.remove("keo"); }));
  v.addEventListener("drop", (e) => xong(e.dataTransfer.files[0]));
}

let maTepDaTai = null;      // id file đã tải lên, dùng lại lúc bấm Process

gan("tha", "chon-file", async (f) => {
  if (!f) return;
  tep = f;
  maTepDaTai = null;
  $("ten-file").textContent = f.name;
  $("thong-tin").textContent = (f.size / 1048576).toFixed(1) + " MB";
  $("chay").disabled = false;
  // Chọn file xong là tool quên mọi thứ của bài trước.
  tayKeo.clear();
  Object.keys(mocAuto).forEach((k) => delete mocAuto[k]);
  document.querySelectorAll(".keo .moc").forEach((m) => m.remove());
  ["vocal", "master"].forEach((g) => $("the-" + g).classList.remove("bat"));
  hienSoDo(null);

  if (!$("tu-dong").checked) return;
  try {
    // Tải file lên NGAY chứ không đợi lúc bấm Process. Vừa để phân tích được,
    // vừa làm cú bấm Process sau đó chạy luôn thay vì đứng đợi tải.
    datTrangThai("Reading the track", false);
    maTepDaTai = await taiLen(f, (p, i, n) => {
      $("thanh-tien").style.width = (p * 100).toFixed(1) + "%";
      datTrangThai(`Uploading ${Math.round(p * 100)}%  (${i}/${n})`, false);
    });
    const r = await fetch("/api/phan-tich", {
      method: "POST",
      body: new URLSearchParams({ audio_ma: maTepDaTai }),
    });
    if (!r.ok) throw new Error("analysis failed");
    const kq = await r.json();
    hienSoDo(kq.do, kq.bo_qua);
    datNhom("master", kq.thanh);
    datTrangThai(kq.bo_qua ? "" : "Ready", false);
    $("thanh-tien").style.width = "0%";
  } catch (e) {
    // Phân tích hỏng thì thôi, không chặn người dùng: thanh giữ mặc định và
    // bấm Process vẫn chạy được như thường.
    datTrangThai("", false);
    $("thanh-tien").style.width = "0%";
  }
});

gan("tha-mau", "chon-mau", (f) => {
  if (!f) return;
  tepMau = f;
  $("ten-mau").textContent = f.name;
});

// ------------------------------------------------------------------ điều khiển

$("che-do").onclick = (e) => {
  const m = e.target.dataset.mode;
  if (!m) return;
  cheDo = m;
  [...$("che-do").children].forEach((b) => b.classList.toggle("chon", b.dataset.mode === m));
  $("khoi-giong").style.display = m === "full" ? "" : "none";
  $("ghi-mode").textContent = m === "full"
    ? "Splits stems, thickens the vocal, remixes, then masters."
    : "Masters the mix as it is. Nothing can touch the vocal alone.";
};

$("do-lon").onclick = (e) => {
  const v = e.target.dataset.lufs;
  if (!v) return;
  dichLufs = +v;
  [...$("do-lon").children].forEach((b) => b.classList.toggle("chon", b.dataset.lufs === v));
};

// Auto bật thì hàng nút LUFS mờ đi nhưng KHÔNG bị ẩn: người dùng vẫn thấy
// mức nào đang được nhắm, và bỏ tích là lấy lại quyền ngay tại chỗ.
function capNhatAuto() {
  const bat = $("tu-dong").checked;
  $("do-lon").classList.toggle("tat", bat);
  $("ghi-lufs").textContent = bat
    ? "Auto aims at −10.2 LUFS, measured from your reference masters. Untick to set the target yourself."
    : "Target LUFS. −14 is the streaming standard.";
}
$("tu-dong").onchange = capNhatAuto;
capNhatAuto();

const THANH = ["thickness", "presence", "space", "deess", "warmth",
               "vocal_gain", "bass", "air", "width", "tone"];

// Thanh nào hiển thị kèm đơn vị dB, thanh nào chỉ hiện số trần.
const THEO_DB = new Set(["vocal_gain", "bass", "air"]);

function veThanh(k) {
  const el = $(k);
  $("v-" + k).textContent = THEO_DB.has(k)
    ? (el.value > 0 ? "+" : "") + el.value + " dB"
    : el.value;
}

THANH.forEach((k) => {
  $(k).oninput = () => {
    veThanh(k);
    boPreset();
    danhDauTay(k);            // người dùng vừa kéo tay -> tool đừng đè lên nữa
  };
  veThanh(k);
});

// Preset chỉ là một bộ giá trị đặt sẵn cho các thanh — bấm xong vẫn kéo tay
// được. Không giấu tham số nào đi: người dùng luôn nhìn thấy preset vừa đặt
// những gì, nên học được dần thay vì phụ thuộc mãi vào bốn cái nút.
const PRESET = {
  natural:  { thickness: 25, presence: 30, space: 0, deess: 40, warmth: 0,  bass: 0,    air: 0,   width: 100 },
  balanced: { thickness: 50, presence: 50, space: 0, deess: 50, warmth: 0,  bass: 0,    air: 0,   width: 100 },
  warm:     { thickness: 55, presence: 35, space: 30, deess: 60, warmth: 35, bass: 1.5,  air: -1,  width: 105 },
  open:     { thickness: 45, presence: 70, space: 35, deess: 55, warmth: 0,  bass: -0.5, air: 2,   width: 120 },
};

function boPreset() {
  [...$("preset").children].forEach((b) => b.classList.remove("chon"));
}

$("preset").onclick = (e) => {
  const t = e.target.dataset.preset;
  if (!t) return;
  Object.entries(PRESET[t]).forEach(([k, v]) => {
    $(k).value = v;
    veThanh(k);
  });
  boPreset();
  e.target.classList.add("chon");
};

/* -------------------------------------------------- tự chỉnh thanh kéo
 *
 * Hai đợt, vì lý do kỹ thuật chứ không phải thẩm mỹ:
 *   đợt 1  nhập file xong  -> đo bản phối (2 giây) -> nhóm MASTER
 *   đợt 2  lúc xử lý       -> sau khi tách stem   -> nhóm VOCAL
 * Muốn biết giọng dày hay mỏng thì phải tách nó ra khỏi bản phối trước, mà
 * tách stem mất 20-30 giây — bắt người dùng đợi ngần ấy ngay lúc nhập file là
 * vô lý, trong khi lúc xử lý thì đằng nào cũng phải tách.
 */
const NHOM = {
  vocal: ["thickness", "presence", "space", "deess", "vocal_gain"],
  master: ["bass", "air", "width"],
};
const tayKeo = new Set();     // thanh người dùng đã tự kéo
const mocAuto = {};           // mức tool đã chọn, để vẽ vạch và quay về

const itChuyenDong = window.matchMedia
  && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function nhomCua(k) {
  return Object.keys(NHOM).find((g) => NHOM[g].includes(k));
}

/** Người dùng kéo tay một thanh: thẻ của cả nhóm mờ đi, và từ đó tool không
 *  đặt lại thanh này nữa. Đè lên chỉnh tay của người dùng là cách nhanh nhất
 *  để họ không bao giờ tin tính năng tự động nữa. */
function danhDauTay(k) {
  // KHÔNG lọc theo "tool đã đặt thanh này chưa". Người dùng có thể kéo một
  // thanh của nhóm VOCAL ngay lúc vừa nhập file, tức trước khi đợt hai chạy —
  // lọc như vậy là bỏ qua đúng những lần chỉnh tay sớm nhất, rồi đợt hai đè
  // lên ngay trước mắt họ. Đã dính thật khi chạy thử.
  tayKeo.add(k);
  const g = nhomCua(k);
  if (g) $("the-" + g).classList.remove("bat");
}

/** Vạch nhỏ trên rãnh trượt, đúng chỗ tool đã chọn. Bấm vào là về lại đó. */
function datMoc(k, gt) {
  const el = $(k);
  const nhan = el.closest(".keo");
  if (!nhan) return;
  let m = nhan.querySelector(".moc");
  if (!m) {
    m = document.createElement("i");
    m.className = "moc";
    m.title = "Auto-master picked this — click to go back";
    m.onclick = () => {
      tayKeo.delete(k);
      chayThanh(k, mocAuto[k], 0);
      const g = nhomCua(k);
      // Thẻ nhóm sáng lại chỉ khi KHÔNG còn thanh nào trong nhóm bị kéo tay.
      if (g && !NHOM[g].some((x) => tayKeo.has(x))) $("the-" + g).classList.add("bat");
    };
    nhan.appendChild(m);
  }
  const lo = +el.min, hi = +el.max;
  const w = el.clientWidth || nhan.clientWidth;
  const NUM = 13;                         // bề ngang núm, khớp với extra.css
  const ti = (gt - lo) / (hi - lo);
  m.style.left = (NUM / 2 + ti * (w - NUM)).toFixed(1) + "px";
}

/** Trượt một thanh tới mức mới thay vì nhảy cóc.
 *
 *  Lệch nhau 40 ms một thanh: cùng nhảy một lúc thì trông như lỗi vẽ, lệch
 *  nhau thì đọc ra là tool đang lần lượt đặt từng thứ. */
function chayThanh(k, dich, tre) {
  const el = $(k);
  const dau = +el.value;
  if (itChuyenDong || dau === dich) {
    el.value = dich;
    veThanh(k);
    datMoc(k, dich);
    return;
  }
  const nhan = el.closest(".keo");
  const so = nhan && nhan.querySelector("b");
  const DAI = 500;
  setTimeout(() => {
    if (so) so.classList.add("dang-chay");
    const t0 = performance.now();
    const buoc = () => {
      const p = Math.min(1, (performance.now() - t0) / DAI);
      const e = 1 - Math.pow(1 - p, 3);        // ease-out
      el.value = dau + (dich - dau) * e;
      veThanh(k);
      if (p < 1) requestAnimationFrame(buoc);
      else {
        el.value = dich;
        veThanh(k);
        datMoc(k, dich);
        if (so) so.classList.remove("dang-chay");
      }
    };
    requestAnimationFrame(buoc);
  }, tre);
}

/** Đặt cả một nhóm, bỏ qua thanh nào người dùng đã tự kéo. */
function datNhom(g, thanh) {
  const ds = Object.entries(thanh || {}).filter(([k]) => !tayKeo.has(k));
  ds.forEach(([k, v], i) => {
    mocAuto[k] = v;
    chayThanh(k, v, i * 40);
  });
  if (ds.length) $("the-" + g).classList.add("bat");
}

/** Dãy số ĐO ĐƯỢC dưới tên file. Hiện số đo chứ không chỉ hiện kết quả — đây
 *  là thứ làm người dùng tin đang dùng một thiết bị đo. */
function hienSoDo(d, bo_qua) {
  const el = $("so-do-file");
  const c = [];
  if (d) {
    if (d.lufs !== undefined) c.push(d.lufs + " LUFS");
    if (d.dr !== undefined) c.push(d.dr + " dB dyn");
    if (d.tram !== undefined) c.push("bass " + (d.tram > 20 ? "heavy" : d.tram < 17 ? "light" : "even"));
    if (d.cao !== undefined) c.push("top " + (d.cao > -14.5 ? "bright" : d.cao < -18 ? "dull" : "even"));
    if (d.rong !== undefined) c.push("width " + d.rong);
  }
  if (bo_qua) c.push(bo_qua);
  el.innerHTML = c.map((x) => "<span>" + x + "</span>").join("");
  el.hidden = !c.length;
}

// ------------------------------------------------------------------ chạy việc

// ------------------------------------------------------------ tải file lên

// Chia 4 MB một phần.
//
// VÌ SAO: khi app mở ra ngoài qua đường hầm Cloudflare, gói miễn phí CẮT MỌI
// REQUEST SAU 100 GIÂY. Một file WAV 32 MB trên đường tải lên 2 Mbps mất 132
// giây -> bị cắt giữa đường, người dùng nhận lỗi 524 mà không hiểu vì sao.
//
// Chia phần thì mỗi phần là một request riêng, chỉ mất vài giây. Không bao giờ
// chạm mốc 100 giây, bất kể file lớn cỡ nào và mạng nhanh chậm ra sao.
//
// 4 MB là chỗ cân: nhỏ hơn thì số lượt gửi tăng, mà mỗi lượt tốn một vòng
// đi-về qua Cloudflare; lớn hơn thì gặp mạng chậm lại bắt đầu rủi ro.
const KHOI_TAI = 4 * 1024 * 1024;

async function taiLen(f, bao) {
  const tong = Math.max(1, Math.ceil(f.size / KHOI_TAI));
  let ma = "";
  for (let i = 0; i < tong; i++) {
    const fd = new FormData();
    fd.append("file", f.slice(i * KHOI_TAI, (i + 1) * KHOI_TAI));
    fd.append("ma", ma);
    fd.append("chi_so", String(i));
    fd.append("tong", String(tong));
    fd.append("ten", f.name);
    const r = await fetch("/api/upload", { method: "POST", body: fd });
    if (!r.ok) {
      let chi = r.statusText;
      try { chi = (await r.json()).detail || chi; } catch (_) {}
      throw new Error("Upload failed: " + chi);
    }
    ma = (await r.json()).ma;
    // Báo tiến độ theo phần ĐÃ GỬI XONG, không theo phần đang gửi: người dùng
    // thấy 100% thì đúng là đã xong, không phải "đang gửi phần cuối".
    if (bao) bao((i + 1) / tong, i + 1, tong);
  }
  return ma;
}

$("chay").onclick = async () => {
  $("chay").disabled = true;

  try {
    const bao = (nhan) => (p, i, n) => {
      $("thanh-tien").style.width = (p * 100).toFixed(1) + "%";
      datTrangThai(`Uploading ${nhan} ${Math.round(p * 100)}%  (${i}/${n})`, false);
    };
    // Đã tải sẵn lúc chọn file thì dùng lại, khỏi tải hai lần.
    const ma_tep = maTepDaTai || await taiLen(tep, bao("track"));
    const ma_mau = tepMau ? await taiLen(tepMau, bao("reference")) : "";

    const fd = new FormData();
    fd.append("audio_ma", ma_tep);
    if (ma_mau) fd.append("reference_ma", ma_mau);
    fd.append("mode", cheDo);
    fd.append("lufs", String(dichLufs));
    fd.append("auto", $("tu-dong").checked ? "true" : "false");
    fd.append("tay", [...tayKeo].join(","));
    THANH.forEach((k) => fd.append(k, $(k).value));

    datTrangThai("Starting", false);
    const r = await fetch("/api/master", { method: "POST", body: fd });
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
    maViec = (await r.json()).id;
    theoDoi();
  } catch (e) {
    datTrangThai(String(e.message || e), true);
    $("chay").disabled = false;
  }
};

function datTrangThai(s, loi) {
  const el = $("trang-thai");
  el.textContent = s;
  el.classList.toggle("loi", !!loi);
}

async function theoDoi() {
  const v = await (await fetch("/api/job/" + maViec)).json();
  $("thanh-tien").style.width = (v.tien_do * 100).toFixed(1) + "%";
  datTrangThai(v.thong_bao, v.trang_thai === "error");

  if (v.trang_thai === "done") {
    $("chay").disabled = false;
    await veKetQua(v.ket_qua);
    return;
  }
  if (v.trang_thai === "error") {
    datTrangThai(v.loi || "Failed", true);
    $("chay").disabled = false;
    return;
  }
  setTimeout(theoDoi, 700);
}

// ------------------------------------------------------------------ kết quả

async function veKetQua(kq) {
  soDo = kq;
  $("trong").hidden = true;
  $("kq").hidden = false;

  $("sl-lufs").textContent = kq.after.lufs;
  $("sl-lufs0").textContent = "LUFS  (was " + kq.before.lufs + ")";
  $("sl-dr").textContent = kq.after.dr + " dB";
  $("sl-dr0").textContent = "Dynamics  (was " + kq.before.dr + ")";
  // Hiện đỉnh LIÊN MẪU, không phải đỉnh thường: đây mới là con số các
  // nền tảng nhạc kiểm, và là con số quyết định có rè khi nén MP3 không.
  $("sl-peak").textContent = kq.after.tp + " dBTP";
  $("sl-tg").textContent = gio(kq.duration);

  // Cảnh báo khi file đưa vào vốn đã được master rồi. Dấu hiệu: đã to sẵn,
  // đỉnh đã bị chặn, dải động đã hẹp. Master chồng lên một bản như vậy chỉ
  // đổi thêm vài phần mười decibel độ lớn lấy vài decibel dải động — một cuộc
  // trao đổi lỗ, mà nhìn con số LUFS tăng lên thì lại tưởng là được.
  // Kể lại tool đã tự chọn gì. Một hộp đen quyết định giùm người dùng mà
  // không nói nó quyết định cái gì thì lần sau họ không tin nó nữa.
  const tc = $("tu-chon");
  if (kq.auto) {
    const a = kq.auto;
    // Hai câu khác nhau, vì hai quyết định khác nhau. Nói "pushed +0.0 dB"
    // khi tool CỐ Ý không đụng vào độ lớn thì người đọc tưởng nó tính sai.
    tc.innerHTML = a.da_master
      ? "Auto: this is already a master (<b>" + a.lufs_vao + " LUFS</b>, <b>"
        + a.dr_vao + " dB</b> dynamics). Left as it is — only the peak ceiling "
        + "was brought to −1 dBTP. Feed the mix instead to get a full master."
      : "Auto: measured <b>" + a.lufs_vao + " LUFS</b>, aimed at <b>"
        + a.dich + "</b>, pushed <b>" + (a.day > 0 ? "+" : "") + a.day + " dB</b>.";
    tc.hidden = false;
  } else {
    tc.hidden = true;
  }

  // Ngưỡng "file này đã là bản master rồi", đặt theo SỐ ĐO chứ không ước chừng.
  //
  // Năm bản mix của khách nằm ở -12,5 tới -14,9 LUFS, dải động 7,6-10,0 dB.
  // Năm bản master tương ứng nằm ở -9,6 tới -10,9 LUFS, dải động 6,0-8,5 dB.
  // Hai nhóm tách nhau rõ ở mốc -11,5 LUFS, và phải đòi CẢ hai điều kiện.
  //
  // Ngưỡng cũ là `lufs > -16 && dr < 11` — rộng tới mức mọi bản mix bình
  // thường đều dính, nên nó bắn cảnh báo "đây đã là bản master" vào đúng thứ
  // mà tool sinh ra để xử lý. Đã thấy nó bắn nhầm vào một bản mix -13,51 LUFS.
  // Đợt tự chỉnh thứ hai: nhóm VOCAL, giờ mới có số vì stem vừa tách xong.
  if (kq.auto_vocal) {
    datNhom("vocal", kq.auto_vocal.thanh);
    if (kq.auto_vocal.bo_qua) hienSoDo(null, kq.auto_vocal.bo_qua);
  }

  const daMaster = kq.before.lufs > -11.5 && kq.before.dr < 8.5;
  const matDR = kq.before.dr - kq.after.dr;
  const canh = $("canh-bao");
  if (daMaster) {
    // Cả hai chiều đều có thể âm, nên phải chọn động từ theo dấu.
    //
    // File vào đã to sẵn thì kéo về đích là ĐI XUỐNG, và dải động thì có bài
    // còn RỘNG RA. Viết cứng "gained X" / "lost X" là ra những câu vô nghĩa
    // kiểu "gained -3.1 dB of loudness" và "lost -0.3 dB of dynamics".
    const doiLufs = kq.after.lufs - kq.before.lufs;
    const cauLufs = (doiLufs >= 0 ? "up " : "down ") + Math.abs(doiLufs).toFixed(1);
    const cauDR = matDR >= 0
      ? "lost " + matDR.toFixed(1) + " dB of dynamics"
      : "gained " + Math.abs(matDR).toFixed(1) + " dB of dynamics back";
    canh.textContent = "This file already looks mastered (" + kq.before.lufs +
      " LUFS, " + kq.before.dr + " dB dynamics). Loudness went " + cauLufs +
      " dB and it " + cauDR +
      ". Feed a mix, not a master — or use Master only.";
    canh.hidden = false;
  } else if (matDR > 4) {
    canh.textContent = "Lost " + matDR.toFixed(1) +
      " dB of dynamics. That is a lot — try a lower loudness target or less Thickness.";
    canh.hidden = false;
  } else {
    canh.hidden = true;
  }

  $("nut-vocal").disabled = !kq.has_vocal;

  may.xoa();
  dinh = {};

  // Bài mới thì trả cửa sổ xem về cả bài. Giữ mức phóng của lần trước là
  // người dùng xử lý bài mới xong thấy một khúc giữa, không hiểu vì sao.
  xemDau = 0;
  xemDai = 0;

  dangNghe = "mastered";
  danhDauAB();

  // Nạp bản đang nghe trước rồi mới tới bản gốc: bấm Play được ngay, không
  // phải chờ giải mã xong cả hai.
  await docDinh("mastered");
  canMuc();
  veSong();
  await docDinh("original");
  if (kq.has_vocal) await docDinh("vocal");
  canMuc();
  veSong();
}

function danhDauAB() {
  [...$("ab").children].forEach((b) => b.classList.toggle("chon", b.dataset.kind === dangNghe));
}

function canMuc() {
  // So A/B mà một bản to hơn thì bản to hơn LUÔN nghe hay hơn, bất kể nó có
  // thật sự tốt hơn không — đó là bẫy tâm lý âm thanh kinh điển. Hạ bản to
  // xuống cho bằng bản nhỏ rồi hãy so.
  may.canMuc($("cung-muc").checked,
             soDo ? soDo.after.lufs - soDo.before.lufs : 0);
}

$("cung-muc").onchange = canMuc;

/** Đổi bản đang nghe. Tách thành hàm riêng để phím 1/2/3 gọi được — tai chỉ
 *  nhớ âm thanh vừa nghe trong vài giây, rê chuột lên bấm nút là đã quá muộn. */
function doiBan(k) {
  if (!k || !may.co(k)) return;
  const nut = $("ab").querySelector('[data-kind="' + k + '"]');
  if (nut && nut.disabled) return;

  // Không dừng, không tua, không nạp lại — chỉ chuyển âm lượng. Vị trí kim tự
  // giữ nguyên vì cả ba bản vẫn đang chạy cùng nhau.
  may.doiBan(k);
  danhDauAB();
  veSong();
  if (!dinh[k]) docDinh(k).then(veSong);
}

$("ab").onclick = (e) => doiBan(e.target.dataset.kind);

$("phat").onclick = () => may.batTat();

may.khiDoiTrangThai((dang) => {
  $("phat").textContent = dang ? "Pause" : "Play";
  if (dang) nhip();
});

/** Nhịp vẽ lại lúc đang phát.
 *
 *  Bản trước dựa vào sự kiện `timeupdate` của thẻ audio, mà sự kiện đó chỉ nổ
 *  chừng 4 lần một giây — vạch phát nhảy từng bậc nhìn rõ. Đây bám theo nhịp
 *  vẽ của màn hình, và tự tắt khi dừng nên không tốn gì lúc ngồi im.
 */
function nhip() {
  if (!may.dangPhat()) return;
  $("gio").textContent = gio(may.gio()) + " / " + gio(may.dai());
  veSong();
  if (may.gio() >= may.dai() - 0.02) { may.dung(); return; }
  requestAnimationFrame(nhip);
}

// ------------------------------------------------------------------ sóng

// Cửa sổ đang xem, tính bằng giây. Bằng cả bài lúc mới xử lý xong.
let xemDau = 0;
let xemDai = 0;

// Đỉnh sóng lưu ở độ phân giải CAO chứ không theo bề rộng màn hình.
//
// Bản trước rút gọn thẳng về 1000 cột — đủ khi xem cả bài, nhưng phóng vào 10
// giây thì mỗi cột trải ra cả trăm điểm ảnh và sóng thành bậc thang. Giữ ở
// 10 ms một cột rồi mới gộp lúc vẽ: bài 4 phút hết chừng 96 KB cho mỗi bản.
const MS_MOI_COT = 10;

async function docDinh(kind) {
  try {
    const buf = await (await fetch("/api/audio/" + maViec + "?kind=" + kind)).arrayBuffer();
    const dl = await may.giaiMa(buf);
    may.nap(kind, dl);
    const x = dl.getChannelData(0);
    const buoc = Math.max(1, Math.round(dl.sampleRate * MS_MOI_COT / 1000));
    const cot = Math.floor(x.length / buoc);
    const d = new Float32Array(cot);
    for (let i = 0; i < cot; i++) {
      let m = 0;
      const a = i * buoc, b = a + buoc;
      // Nhảy 4 mẫu một: đỉnh trong 10 ms gần như không đổi, mà đọc đủ thì bài
      // 4 phút phải duyệt hơn 10 triệu mẫu ngay trên luồng giao diện.
      for (let j = a; j < b; j += 4) {
        const v = Math.abs(x[j]);
        if (v > m) m = v;
      }
      d[i] = m;
    }
    dinh[kind] = d;
  } catch (e) { /* trình duyệt không giải mã được thì bỏ sóng, app vẫn chạy */ }
}

function tongDai() {
  return may.dai() || (soDo && soDo.duration) || 1;
}

function chuanCuaSo() {
  const tong = tongDai();
  xemDai = Math.max(1, Math.min(xemDai || tong, tong));
  xemDau = Math.max(0, Math.min(tong - xemDai, xemDau));
}

/** Đổi mức thu phóng, GIỮ NGUYÊN mốc thời gian đang nằm dưới con trỏ.
 *
 *  Neo vào con trỏ chứ không vào tâm cửa sổ: lăn chuột ở chỗ nào là đang quan
 *  tâm chỗ đó. Neo vào tâm thì chỗ đang nhìn trôi đi mất, phải kéo lại — thành
 *  hai thao tác cho một ý định. */
function thuPhong(vao, he, xNeo) {
  const r = $("song").getBoundingClientRect();
  const p = xNeo == null ? 0.5 : Math.max(0, Math.min(1, (xNeo - r.left) / r.width));
  const moc = xemDau + p * xemDai;
  const tong = tongDai();
  // Nhân/chia chứ không cộng/trừ: ở mức 5 giây thì cộng 5 giây là nhảy vọt,
  // còn ở mức cả bài thì 5 giây chẳng nhúc nhích.
  xemDai = Math.max(1, Math.min(tong, vao ? xemDai / he : xemDai * he));
  xemDau = moc - p * xemDai;
  chuanCuaSo();
  veSong();
}

function veSong() {
  const c = $("song");
  const r = c.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  c.width = r.width * dpr;
  c.height = r.height * dpr;
  const g = c.getContext("2d");
  g.scale(dpr, dpr);
  g.clearRect(0, 0, r.width, r.height);

  const tong = tongDai();
  if (!xemDai) xemDai = tong;
  chuanCuaSo();

  const CAO_THUOC = 16;
  const caoSong = r.height - CAO_THUOC;
  const x = (t) => ((t - xemDau) / xemDai) * r.width;

  // Vẽ bản gốc mờ phía sau, bản đang nghe đậm phía trước: chênh lệch dải động
  // giữa hai bản nhìn thấy được ngay, không cần nghe.
  const ve = (d, mau) => {
    if (!d) return;
    g.fillStyle = mau;
    const giay_moi_cot = MS_MOI_COT / 1000;
    const i0 = Math.max(0, Math.floor(xemDau / giay_moi_cot));
    const i1 = Math.min(d.length, Math.ceil((xemDau + xemDai) / giay_moi_cot));
    const cot_moi_px = (i1 - i0) / r.width;

    if (cot_moi_px >= 1) {
      for (let px = 0; px < r.width; px++) {
        let m = 0;
        const a = i0 + Math.floor(px * cot_moi_px);
        const b = i0 + Math.floor((px + 1) * cot_moi_px);
        for (let i = a; i < b; i++) if (d[i] > m) m = d[i];
        const h = m * (caoSong * 0.92);
        g.fillRect(px, CAO_THUOC + (caoSong - h) / 2, 1, h);
      }
    } else {
      // Phóng tới mức một cột đỉnh rộng hơn một điểm ảnh: vẽ thành thanh.
      const w = r.width / (i1 - i0);
      for (let i = i0; i < i1; i++) {
        const h = d[i] * (caoSong * 0.92);
        g.fillRect((i - i0) * w, CAO_THUOC + (caoSong - h) / 2,
                   Math.max(0.8, w - 0.3), h);
      }
    }
  };
  if (dangNghe !== "original") ve(dinh.original, "#2e2e38");
  ve(dinh[dangNghe], dangNghe === "original" ? "#4a4a58" : "#6e63f2");

  // Thước thời gian. Bước chia chọn theo CHỖ THẬT SỰ CÓ trên màn: đòi tối
  // thiểu 56 điểm ảnh cho mỗi nhãn rồi lấy bước nhỏ nhất còn vừa.
  const buoc = [0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300]
    .find((b) => (b / xemDai) * r.width >= 56) || 600;
  g.fillStyle = "#0f0f13";
  g.fillRect(0, 0, r.width, CAO_THUOC);
  g.strokeStyle = "#26262e";
  g.beginPath(); g.moveTo(0, CAO_THUOC + .5); g.lineTo(r.width, CAO_THUOC + .5); g.stroke();
  g.fillStyle = "#6b6b74";
  g.font = "10px Inter, system-ui, sans-serif";
  g.textBaseline = "middle";
  for (let t = Math.ceil(xemDau / buoc) * buoc; t < xemDau + xemDai; t += buoc) {
    const px = x(t);
    g.fillRect(px, CAO_THUOC - 4, 1, 4);
    g.fillText(buoc < 1 ? gioLe(t) : gio(t), px + 3, CAO_THUOC / 2);
  }

  // Vạch phát, kèm tay nắm hình thang ở đỉnh cho thấy nó cầm được.
  const t = may.gio();
  if (t >= xemDau - 1 && t <= xemDau + xemDai + 1) {
    const px = x(t);
    g.fillStyle = "#ffffff";
    g.fillRect(px - 0.75, 0, 1.5, r.height);
    g.beginPath();
    g.moveTo(px - 5, 0); g.lineTo(px + 5, 0);
    g.lineTo(px + 5, 7); g.lineTo(px, 11); g.lineTo(px - 5, 7);
    g.closePath();
    g.fill();
  }

  // Bản đồ thu nhỏ khi đang phóng to: không có nó thì phóng xong là mất
  // phương hướng, không biết đang đứng ở đâu trong cả bài.
  if (xemDai < tong - 0.01) {
    const h = 3;
    g.fillStyle = "#1c1c22";
    g.fillRect(0, r.height - h, r.width, h);
    g.fillStyle = "#6e63f2";
    g.fillRect((xemDau / tong) * r.width, r.height - h,
               Math.max(3, (xemDai / tong) * r.width), h);
  }
}

// ------------------------------------------------------- chuột trên sóng

(function ganChuot() {
  const c = $("song");

  // Lăn chuột = thu phóng.
  //
  // Gắn bằng addEventListener với passive:false chứ không dùng thuộc tính
  // onwheel: trình duyệt coi wheel là thụ động ở nhiều ngữ cảnh, khi ấy
  // preventDefault vô tác dụng và mỗi lần lăn là cả trang cuộn theo.
  //
  // Nấc 1,22 cho chuột nhẹ hơn nấc 1,45 của phím: một cú lăn phát ra nhiều
  // sự kiện liền nhau, để nấc lớn thì lăn nhẹ một cái đã nhảy hết cỡ.
  c.addEventListener("wheel", (e) => {
    if (e.ctrlKey || e.metaKey) return;    // nhường cho phóng to của trình duyệt
    if (!e.deltaY || $("kq").hidden) return;
    e.preventDefault();
    thuPhong(e.deltaY < 0, 1.22, e.clientX);
  }, { passive: false });

  let keo = null;

  c.addEventListener("pointerdown", (e) => {
    if ($("kq").hidden) return;
    if (!may.co()) return;
    const r = c.getBoundingClientRect();
    const px = e.clientX - r.left;
    const py = e.clientY - r.top;
    const t = xemDau + (px / r.width) * xemDai;
    const px_vach = ((may.gio() - xemDau) / xemDai) * r.width;

    // Ba tầng, phân theo chỗ bấm — không có chế độ nào phải bật tắt:
    //   thước ở trên   -> tua
    //   sát vạch phát  -> tua (vùng bắt rộng 7px; vạch chỉ 1,5px thì không ai
    //                     bấm trúng bằng chuột)
    //   thân sóng      -> kéo để dịch ngang, bấm nhả tại chỗ thì tua
    keo = {
      x0: e.clientX, dau0: xemDau, da_di: false,
      tua: py < 16 || Math.abs(px - px_vach) <= 7,
    };
    c.setPointerCapture(e.pointerId);
    if (keo.tua) datGio(Math.max(0, Math.min(tongDai(), t)));
  });

  c.addEventListener("pointermove", (e) => {
    if (!keo) return;
    const r = c.getBoundingClientRect();
    if (keo.tua) {
      datGio(Math.max(0, Math.min(tongDai(),
        xemDau + ((e.clientX - r.left) / r.width) * xemDai)));
      veSong();
      return;
    }
    const lech = e.clientX - keo.x0;
    // Ngưỡng 4px: dưới mức đó coi là bấm chứ không phải kéo. Không có ngưỡng
    // thì tay run một chút là mất luôn thao tác bấm-để-tua.
    if (!keo.da_di && Math.abs(lech) < 4) return;
    keo.da_di = true;
    xemDau = keo.dau0 - (lech / r.width) * xemDai;
    chuanCuaSo();
    veSong();
  });

  c.addEventListener("pointerup", (e) => {
    if (!keo) return;
    if (!keo.tua && !keo.da_di) {
      const r = c.getBoundingClientRect();
      datGio(xemDau + ((e.clientX - r.left) / r.width) * xemDai);
      may.phat();
    }
    keo = null;
  });
  c.addEventListener("pointercancel", () => (keo = null));

  // Bấm đúp = xem lại cả bài. Lối thoát khi phóng to lạc mất phương hướng.
  c.addEventListener("dblclick", () => {
    xemDai = tongDai();
    xemDau = 0;
    veSong();
  });
})();

/** Tua. Cả ba bản đi cùng nhau vì chúng dùng chung một đồng hồ. */
function datGio(t) {
  may.datGio(t);
}

// ------------------------------------------------------------- phím tắt

function dangGo(e) {
  const t = e.target;
  if (!t) return false;
  return t.tagName === "INPUT" || t.tagName === "TEXTAREA"
      || t.tagName === "SELECT" || t.isContentEditable;
}

window.addEventListener("keydown", (e) => {
  // Cửa chặn này quan trọng hơn ở đây so với Lyric Sync: cả cột trái là thanh
  // kéo, tức là thẻ INPUT. Đang chỉnh Thickness bằng mũi tên mà thiếu cửa chặn
  // thì thay vì nhích thanh kéo, nhạc lại tua đi một giây.
  if (dangGo(e) || e.ctrlKey || e.altKey || e.metaKey) return;
  if ($("kq").hidden) return;
  if (!may.co()) return;

  const buoc = e.shiftKey ? 5 : 1;
  switch (e.key) {
    case " ":
      e.preventDefault();          // dấu cách vốn cuộn trang xuống một màn
      may.batTat();
      break;
    case "ArrowLeft":
      e.preventDefault();
      datGio(Math.max(0, may.gio() - buoc));
      veSong();
      break;
    case "ArrowRight":
      e.preventDefault();
      datGio(Math.min(tongDai(), may.gio() + buoc));
      veSong();
      break;
    case "+": case "=":
      e.preventDefault(); thuPhong(true, 1.45); break;
    case "-": case "_":
      e.preventDefault(); thuPhong(false, 1.45); break;
    case "0":
      e.preventDefault();
      xemDai = tongDai(); xemDau = 0; veSong();
      break;
    // Đổi A/B bằng phím. Tai chỉ nhớ được âm thanh vừa nghe trong vài giây,
    // nên rê chuột lên bấm nút là đã quá muộn.
    case "1": e.preventDefault(); doiBan("original"); break;
    case "2": e.preventDefault(); doiBan("mastered"); break;
    case "3": e.preventDefault(); doiBan("vocal"); break;
  }
});

window.addEventListener("resize", () => { if (!$("kq").hidden) veSong(); });

// ------------------------------------------------------------------ tải về

document.querySelector(".xuat").onclick = (e) => {
  const f = e.target.dataset.fmt;
  if (!f || !maViec) return;
  window.location.href = "/api/download/" + maViec + "?fmt=" + f;
};

// ------------------------------------------------------------------ khởi động

fetch("/api/health").then((r) => r.json()).then((v) => {
  const el = $("the-gpu");
  el.textContent = v.gpu ? v.device.replace("NVIDIA GeForce ", "") : "CPU";
  el.classList.toggle("on", v.gpu);
}).catch(() => ($("the-gpu").textContent = "offline"));
