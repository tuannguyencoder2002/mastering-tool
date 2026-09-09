// Vỏ .exe cho ứng dụng. Nó KHÔNG nhét Python vào trong như PyInstaller — chỉ
// gọi runtime\python\pythonw.exe chạy launcher.py.
//
// Vì sao làm thế thay vì PyInstaller: gói này mang theo hơn 3 GB thư viện CUDA.
// PyInstaller phải giải nén toàn bộ ra thư mục tạm mỗi lần khởi động, mất hàng
// chục giây và tốn thêm chừng ấy dung lượng. Cách này khởi động tức thì, và
// khi có trục trặc thì mọi thứ vẫn nằm nguyên ở dạng file thường để lần ra.
//
// BẢN CŨ CHỈ CÓ Process.Start() RỒI THOÁT, VÀ ĐÓ LÀ MỘT LỖI NẶNG:
//   - Nạp torch mất 20-60 giây (máy không có card NVIDIA còn lâu hơn). Suốt
//     quãng đó màn hình KHÔNG có gì thay đổi. Khách nháy đúp, không thấy gì,
//     tưởng hỏng, nháy đúp thêm mấy lần nữa -> mọc ra mấy máy chủ cùng lúc.
//   - Python chết vì bất cứ lý do gì thì cũng chết CÂM: pythonw.exe không có
//     cửa sổ lệnh, thông báo lỗi rơi vào hư không. Đã gặp thật với một lỗi cú
//     pháp trong launcher.py — nháy đúp xong tuyệt đối không có gì xảy ra.
//
// Bản này: hiện màn chờ, hứng toàn bộ đầu ra của Python vào data\khoi-dong.log,
// và nếu tiến trình con chết thì bày thẳng lỗi ra hộp thoại.
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Text;
using System.Windows.Forms;

static class Launcher
{
    const string TEN = "Mastering";

    static Process _con;
    static readonly StringBuilder _ra = new StringBuilder();
    static readonly object _khoa = new object();
    static string _diaChi, _log;
    static DateTime _batDau;
    static Label _nhan;
    static Form _man;

    [STAThread]
    static int Main(string[] args)
    {
        string goc = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        string py = Path.Combine(goc, @"runtime\python\pythonw.exe");
        string kichBan = Path.Combine(goc, "launcher.py");
        _diaChi = Path.Combine(goc, @"data\dia-chi.txt");
        _log = Path.Combine(goc, @"data\khoi-dong.log");

        if (!File.Exists(py) || !File.Exists(kichBan))
        {
            // Thiếu file thì nói rõ THIẾU CÁI GÌ. Người dùng hay chỉ copy mỗi
            // file .exe sang máy khác rồi không hiểu vì sao nó không chạy.
            MessageBox.Show(
                "Missing files in the installation folder:\n\n" +
                (File.Exists(py) ? "" : py + "\n") +
                (File.Exists(kichBan) ? "" : kichBan + "\n") +
                "\nCopy the WHOLE folder to this machine, not just the .exe file.",
                TEN, MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }

        try { Directory.CreateDirectory(Path.Combine(goc, "data")); } catch { }
        // File địa chỉ là tín hiệu "máy chủ đã lên". Phải xoá trước khi chạy,
        // không thì file của lần chạy trước làm màn chờ tắt ngay lập tức.
        try { if (File.Exists(_diaChi)) File.Delete(_diaChi); } catch { }

        var kh = new ProcessStartInfo
        {
            FileName = py,
            Arguments = "\"" + kichBan + "\"",
            WorkingDirectory = goc,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        // Hứng đầu ra ở phía C# chứ không để Python tự ghi log: lỗi cú pháp hay
        // lỗi nạp DLL xảy ra TRƯỚC khi dòng code ghi log đầu tiên chạy, nên
        // Python không tự cứu mình được.
        kh.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
        kh.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";
        foreach (string a in args) kh.Arguments += " \"" + a + "\"";

        try
        {
            _con = new Process { StartInfo = kh, EnableRaisingEvents = true };
            _con.OutputDataReceived += Nhan;
            _con.ErrorDataReceived += Nhan;
            _con.Start();
            _con.BeginOutputReadLine();
            _con.BeginErrorReadLine();
        }
        catch (Exception e)
        {
            MessageBox.Show("Could not start:\n\n" + e.Message,
                            TEN, MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }

        _batDau = DateTime.Now;
        Application.EnableVisualStyles();
        // Lỗi trong chính cái vỏ này cũng phải để lại dấu vết. Không có ba cái
        // bẫy dưới đây thì một ngoại lệ ở luồng phụ làm .exe biến mất không kèn
        // không trống — đúng cái triệu chứng mình đang đi chữa.
        AppDomain.CurrentDomain.UnhandledException +=
            (s, e) => GhiLoi("AppDomain", e.ExceptionObject);
        Application.ThreadException += (s, e) => GhiLoi("Thread", e.Exception);
        try
        {
            Application.Run(ManCho());
        }
        catch (Exception e)
        {
            GhiLoi("Main", e);
            return 1;
        }
        return 0;
    }

    static void GhiLoi(string cho, object e)
    {
        try
        {
            File.AppendAllText(_log,
                "[.exe " + cho + "] " + e + Environment.NewLine, Encoding.UTF8);
        }
        catch { }
    }

    static void Nhan(object s, DataReceivedEventArgs e)
    {
        if (e.Data == null) return;
        lock (_khoa)
        {
            _ra.AppendLine(e.Data);
            try { File.AppendAllText(_log, e.Data + Environment.NewLine, Encoding.UTF8); } catch { }
        }
    }

    // Màn chờ: một khung nhỏ không viền, cùng tông với giao diện app.
    static Form ManCho()
    {
        _man = new Form
        {
            FormBorderStyle = FormBorderStyle.None,
            StartPosition = FormStartPosition.CenterScreen,
            Size = new Size(360, 132),
            BackColor = ColorTranslator.FromHtml("#131316"),
            ShowInTaskbar = true,
            Text = TEN,
            TopMost = true,
        };

        var ten = new Label
        {
            Text = TEN,
            ForeColor = ColorTranslator.FromHtml("#ededf0"),
            Font = new Font("Segoe UI", 12F, FontStyle.Bold),
            AutoSize = true,
            Location = new Point(24, 30),
            BackColor = Color.Transparent,
        };
        _nhan = new Label
        {
            Text = "Starting…",
            ForeColor = ColorTranslator.FromHtml("#8b8b93"),
            Font = new Font("Segoe UI", 8.5F),
            AutoSize = false,
            Size = new Size(312, 40),
            Location = new Point(24, 60),
            BackColor = Color.Transparent,
        };
        _man.Controls.Add(ten);
        _man.Controls.Add(_nhan);

        var dem = new Timer { Interval = 300 };
        dem.Tick += (s, e) => Nhip(dem);
        _man.Shown += (s, e) => dem.Start();
        // Đóng màn chờ giữa chừng = huỷ hẳn. Không giết tiến trình con thì máy
        // chủ sống ngầm, lần sau mở app lại nhảy sang cổng khác.
        _man.FormClosing += (s, e) =>
        {
            dem.Stop();
            if (!File.Exists(_diaChi)) Giet();
        };
        return _man;
    }

    static void Nhip(Timer dem)
    {
        // Máy chủ lên rồi: launcher.py tự mở cửa sổ app, màn chờ rút lui.
        if (File.Exists(_diaChi)) { dem.Stop(); _man.Close(); return; }

        if (_con.HasExited)
        {
            dem.Stop();
            string vet;
            lock (_khoa) vet = _ra.ToString().Trim();
            if (vet.Length == 0) vet = "(no output — exit code " + _con.ExitCode + ")";
            BayLoi(vet);
            return;
        }

        // Đổi lời nhắn theo thời gian chờ: 40 giây im lặng là đủ để người ta
        // tưởng máy treo, phải nói cho họ biết là nó vẫn đang chạy.
        double giay = (DateTime.Now - _batDau).TotalSeconds;
        _nhan.Text = giay < 20
            ? "Starting…"
            : giay < 75
                ? "Loading models — first run takes up to a minute."
                : "Still loading. Close this window to cancel.";
    }

    // Lỗi hiện NGAY TRÊN màn chờ chứ không bung MessageBox: hộp thoại modal gọi
    // từ trong Timer.Tick đóng lại ngay lập tức trên máy này (đã thử, .exe tắt
    // sau 2 giây mà không ai kịp đọc gì). Vả lại đằng nào cũng cần chỗ cho khách
    // BÔI ĐEN CHÉP thông báo gửi lại — MessageBox không chép chọn lọc được.
    static void BayLoi(string vet)
    {
        _nhan.Text = "The app stopped while starting. Send this text back:";
        _nhan.ForeColor = ColorTranslator.FromHtml("#f43f5e");
        _man.Size = new Size(620, 400);
        var mh = Screen.FromControl(_man).WorkingArea;
        _man.Location = new Point(mh.X + (mh.Width - _man.Width) / 2,
                                  mh.Y + (mh.Height - _man.Height) / 2);
        _man.TopMost = false;

        var o = new TextBox
        {
            Multiline = true,
            ReadOnly = true,
            ScrollBars = ScrollBars.Vertical,
            WordWrap = false,
            Text = vet.Replace("\n", Environment.NewLine),
            BackColor = ColorTranslator.FromHtml("#0b0b0d"),
            ForeColor = ColorTranslator.FromHtml("#ededf0"),
            Font = new Font("Consolas", 8.5F),
            BorderStyle = BorderStyle.FixedSingle,
            Location = new Point(24, 96),
            Size = new Size(572, 224),
            Anchor = AnchorStyles.Top | AnchorStyles.Left
                     | AnchorStyles.Right | AnchorStyles.Bottom,
        };
        var nut = new Button
        {
            Text = "Close",
            Location = new Point(516, 336),
            Size = new Size(80, 30),
            FlatStyle = FlatStyle.Flat,
            BackColor = ColorTranslator.FromHtml("#191920"),
            ForeColor = ColorTranslator.FromHtml("#ededf0"),
            Anchor = AnchorStyles.Bottom | AnchorStyles.Right,
        };
        nut.Click += (s, e) => _man.Close();
        var chu = new Label
        {
            Text = @"Full log:   data\khoi-dong.log",
            ForeColor = ColorTranslator.FromHtml("#8b8b93"),
            Font = new Font("Segoe UI", 8F),
            AutoSize = true,
            Location = new Point(24, 344),
            Anchor = AnchorStyles.Bottom | AnchorStyles.Left,
        };
        _man.Controls.Add(o);
        _man.Controls.Add(nut);
        _man.Controls.Add(chu);
        // Giãn khung xong phải vẽ lại toàn bộ: không thì chỗ vừa mở rộng ra
        // còn dính lại vệt ảnh của thứ nằm dưới cửa sổ.
        _man.Invalidate(true);
        _man.Update();
    }

    static void Giet()
    {
        try { if (_con != null && !_con.HasExited) _con.Kill(); } catch { }
    }
}
