// Giao diện Mastering. Không khung, không bước dựng — mở là chạy.

const $ = (id) => document.getElementById(id);

let tep = null;       // bài cần xử lý
let tepMau = null;    // bài mẫu để so phổ (tuỳ chọn)
let maViec = null;
let cheDo = "full";
let dichLufs = -14;
let soDo = null;      // LUFS trước/sau, để cân mức khi so A/B
let dinh = {};        // đỉnh sóng theo từng bản, vẽ lại khi đổi A/B

// Ba thẻ audio nạp sẵn, đổi qua lại là nghe ngay. Nếu dùng một thẻ rồi đổi src
// thì mỗi lần bấm phải chờ tải lại — đúng lúc cần so sánh thì tai đã quên mất
// bản vừa nghe.
const ban = { original: null, mastered: null, vocal: null };
let dangNghe = "mastered";

function gio(t) {
  if (!isFinite(t)) return "0:00";
  const p = Math.floor(t / 60), s = Math.floor(t % 60);
  return p + ":" + String(s).padStart(2, "0");
}

function gioLe(t) {
  return gio(t) + "." + String(Math.floor((t % 1) * 100)).padStart(2, "0");
}

function hienTai() { return ban[dangNghe]; }

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

gan("tha", "chon-file", (f) => {
  if (!f) return;
  tep = f;
  $("ten-file").textContent = f.name;
  $("thong-tin").textContent = (f.size / 1048576).toFixed(1) + " MB";
  $("chay").disabled = false;
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

const THANH = ["thickness", "presence", "space", "deess", "warmth",
               "vocal_gain", "bass", "air", "width"];

// Thanh nào hiển thị kèm đơn vị dB, thanh nào chỉ hiện số trần.
const THEO_DB = new Set(["vocal_gain", "bass", "air"]);

function veThanh(k) {
  const el = $(k);
  $("v-" + k).textContent = THEO_DB.has(k)
    ? (el.value > 0 ? "+" : "") + el.value + " dB"
    : el.value;
}

THANH.forEach((k) => {
  $(k).oninput = () => { veThanh(k); boPreset(); };
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

// ------------------------------------------------------------------ chạy việc

$("chay").onclick = async () => {
  const fd = new FormData();
  fd.append("audio", tep);
  if (tepMau) fd.append("reference", tepMau);
  fd.append("mode", cheDo);
  fd.append("lufs", String(dichLufs));
  THANH.forEach((k) => fd.append(k, $(k).value));

  $("chay").disabled = true;
  datTrangThai("Uploading", false);

  try {
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
  const daMaster = kq.before.lufs > -16 && kq.before.dr < 11;
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

  Object.keys(ban).forEach((k) => {
    if (ban[k]) ban[k].pause();
    ban[k] = null;
  });
  dinh = {};

  ["original", "mastered"].concat(kq.has_vocal ? ["vocal"] : []).forEach((k) => {
    const a = new Audio("/api/audio/" + maViec + "?kind=" + k);
    a.preload = "auto";
    ban[k] = a;
  });

  // Bài mới thì trả cửa sổ xem về cả bài. Giữ mức phóng của lần trước là
  // người dùng xử lý bài mới xong thấy một khúc giữa, không hiểu vì sao.
  xemDau = 0;
  xemDai = 0;

  dangNghe = "mastered";
  danhDauAB();
  canMuc();
  noiSuKien();

  await docDinh("mastered");
  await docDinh("original");
  veSong();
}

function danhDauAB() {
  [...$("ab").children].forEach((b) => b.classList.toggle("chon", b.dataset.kind === dangNghe));
}

function canMuc() {
  // So A/B mà một bản to hơn thì bản to hơn LUÔN nghe hay hơn, bất kể nó có
  // thật sự tốt hơn không — đó là bẫy tâm lý âm thanh kinh điển. Hạ bản to
  // xuống cho bằng bản nhỏ rồi hãy so.
  const bat = $("cung-muc").checked;
  const lech = soDo ? soDo.after.lufs - soDo.before.lufs : 0;
  const hs = Math.pow(10, -Math.abs(lech) / 20);
  if (ban.original) ban.original.volume = bat && lech < 0 ? hs : 1;
  if (ban.mastered) ban.mastered.volume = bat && lech > 0 ? hs : 1;
  if (ban.vocal) ban.vocal.volume = 1;
}

$("cung-muc").onchange = canMuc;

/** Đổi bản đang nghe. Tách thành hàm riêng để phím 1/2/3 gọi được — tai chỉ
 *  nhớ âm thanh vừa nghe trong vài giây, rê chuột lên bấm nút là đã quá muộn. */
function doiBan(k) {
  if (!k || !ban[k]) return;
  const nut = $("ab").querySelector('[data-kind="' + k + '"]');
  if (nut && nut.disabled) return;

  const cu = hienTai();
  const t = cu ? cu.currentTime : 0;
  const dangPhat = cu && !cu.paused;
  if (cu) cu.pause();

  dangNghe = k;
  danhDauAB();
  const moi = hienTai();
  // Giữ nguyên vị trí kim: đổi bản mà nhảy về đầu bài thì không so được gì cả.
  try { moi.currentTime = t; } catch (_) {}
  if (dangPhat) moi.play();
  veSong();
  if (!dinh[k]) docDinh(k).then(veSong);
}

$("ab").onclick = (e) => doiBan(e.target.dataset.kind);

$("phat").onclick = () => {
  const a = hienTai();
  if (!a) return;
  a.paused ? a.play() : a.pause();
};

function noiSuKien() {
  Object.entries(ban).forEach(([k, a]) => {
    if (!a) return;
    a.onplay = () => ($("phat").textContent = "Pause");
    a.onpause = () => ($("phat").textContent = "Play");
    a.ontimeupdate = () => {
      if (k !== dangNghe) return;
      $("gio").textContent = gio(a.currentTime) + " / " + gio(a.duration || 0);
      veSong();
    };
  });
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
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const dl = await ctx.decodeAudioData(buf);
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
    ctx.close();
  } catch (e) { /* trình duyệt không giải mã được thì bỏ sóng, app vẫn chạy */ }
}

function tongDai() {
  const a = hienTai();
  return (a && a.duration) || (soDo && soDo.duration) || 1;
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
  const a = hienTai();
  const t = (a && a.currentTime) || 0;
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
    const a = hienTai();
    if (!a) return;
    const r = c.getBoundingClientRect();
    const px = e.clientX - r.left;
    const py = e.clientY - r.top;
    const t = xemDau + (px / r.width) * xemDai;
    const px_vach = ((a.currentTime - xemDau) / xemDai) * r.width;

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
      const a = hienTai();
      if (a) a.play();
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

/** Đặt mốc phát cho CẢ BA bản cùng lúc.
 *
 *  Đây là chỗ Mastering khác Lyric Sync: có ba thẻ audio nạp sẵn để đổi A/B
 *  cho tức thì. Chỉ tua bản đang nghe thì bấm sang bản kia là nó vẫn đứng ở
 *  chỗ cũ — mà so A/B ở hai mốc thời gian khác nhau thì vô nghĩa. */
function datGio(t) {
  Object.values(ban).forEach((a) => {
    if (!a) return;
    try { a.currentTime = t; } catch (_) {}
  });
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
  const a = hienTai();
  if (!a) return;

  const buoc = e.shiftKey ? 5 : 1;
  switch (e.key) {
    case " ":
      e.preventDefault();          // dấu cách vốn cuộn trang xuống một màn
      a.paused ? a.play() : a.pause();
      break;
    case "ArrowLeft":
      e.preventDefault();
      datGio(Math.max(0, a.currentTime - buoc));
      veSong();
      break;
    case "ArrowRight":
      e.preventDefault();
      datGio(Math.min(tongDai(), a.currentTime + buoc));
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
