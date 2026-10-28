using System;
using System.Diagnostics;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Web.Script.Serialization;
using System.ComponentModel;
using System.Runtime.InteropServices;

namespace AutoMas.Launcher
{
    /// <summary>
    /// AUTO-MAS 原生无黑框启动器与系统托盘守护进程 (编译为 AUTO-MAS.exe)。
    /// 支持两种运行方式：
    /// 1. 默认模式（双击启动）：后台无窗口拉起 Node.js 前端服务 (frontend/server.js) 与 Python 后端 (main.py)，
    ///    远程桌面默认在系统托盘静默运行，并通过 Node.js 自动调用系统浏览器打开 AUTO-MAS 控制台。
    /// 2. 无窗口直跑模式（传入 --headless / --no-window / --auto-run / --run-queue / --run-script）：
    ///    直接静默拉起后端并立即执行指定队列或脚本，不开任何浏览器或控制台窗口，完全不打扰主桌面。
    /// </summary>
    internal sealed class LauncherTrayContext : ApplicationContext
    {
        [DllImport("wtsapi32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool WTSGetChildSessionId(out uint sessionId);

        [DllImport("wtsapi32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool WTSLogoffSession(
            IntPtr serverHandle, uint sessionId, [MarshalAs(UnmanagedType.Bool)] bool wait);

        private readonly string _rootDir;
        private readonly string[] _args;
        private readonly bool _headless;
        private readonly int _frontendPort = 36162;
        private readonly int _backendPort = 36163;
        private readonly SemaphoreSlim _servicesLock = new SemaphoreSlim(1, 1);
        private NotifyIcon _trayIcon;
        private ContextMenuStrip _trayMenu;
        private bool _openingBrowser;

        public LauncherTrayContext(string[] args)
        {
            _rootDir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\', '/');
            _args = args ?? new string[0];
            _headless = HasFlag(_args, "--headless") || HasFlag(_args, "--no-window") || HasFlag(_args, "--no-browser");

            BuildTrayIcon();
            Task.Run(async () =>
            {
                try { await StartServicesAsync(true); }
                catch (Exception error) { ShowControlError(error); }
            });
        }

        private static bool HasFlag(string[] args, string flag)
        {
            foreach (var a in args)
            {
                if (string.Equals(a, flag, StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }
            return false;
        }

        private void BuildTrayIcon()
        {
            _trayMenu = new ContextMenuStrip();

            var itemOpenWeb = new ToolStripMenuItem("🌐 打开 AUTO-MAS 浏览器控制台");
            itemOpenWeb.Font = new Font(itemOpenWeb.Font, FontStyle.Bold);
            itemOpenWeb.Click += delegate { OpenBrowserConsole(); };

            var itemShowRdp = new ToolStripMenuItem("🖥 显示 BetterGI 本地远程桌面窗口");
            itemShowRdp.Click += delegate { PostJsonAsync("/api/child-session/window", "{\"visible\":true}"); };

            var itemHideRdp = new ToolStripMenuItem("👁 隐藏远程桌面窗口到托盘");
            itemHideRdp.Click += delegate { PostJsonAsync("/api/child-session/window", "{\"visible\":false}"); };

            var itemToggleTask = new ToolStripMenuItem("⏯ 启停任务队列 (Ctrl+Alt+S)");
            itemToggleTask.Click += delegate { PostJsonAsync("/api/dispatch/navigation/toggle", "{}"); };

            var itemPrevTask = new ToolStripMenuItem("⏮ 上一个任务 (Ctrl+Alt+Left)");
            itemPrevTask.Click += delegate { PostJsonAsync("/api/dispatch/navigation/previous", "{}"); };

            var itemNextTask = new ToolStripMenuItem("⏭ 下一个任务 (Ctrl+Alt+Right)");
            itemNextTask.Click += delegate { PostJsonAsync("/api/dispatch/navigation/next", "{}"); };

            var itemExitFrontend = new ToolStripMenuItem("仅退出前端");
            itemExitFrontend.Click += async delegate { await RunControlAsync(StopFrontendAsync); };

            var itemPauseBackend = new ToolStripMenuItem("暂停后端服务（停止队列）");
            itemPauseBackend.Click += async delegate
            {
                await RunControlAsync(async () =>
                {
                    await SendJsonAsync(_backendPort, "/api/dispatch/stop", "{\"taskId\":\"ALL\"}");
                    _trayIcon.Text = "AUTO-MAS（队列已停止，后端仍在运行）";
                });
            };

            var itemExitAll = new ToolStripMenuItem("完全退出");
            itemExitAll.Click += async delegate { await RunControlAsync(ShutdownAndExitAsync); };

            _trayMenu.Items.Add(itemOpenWeb);
            _trayMenu.Items.Add(new ToolStripSeparator());
            _trayMenu.Items.Add(itemShowRdp);
            _trayMenu.Items.Add(itemHideRdp);
            _trayMenu.Items.Add(new ToolStripSeparator());
            _trayMenu.Items.Add(itemToggleTask);
            _trayMenu.Items.Add(itemPrevTask);
            _trayMenu.Items.Add(itemNextTask);
            _trayMenu.Items.Add(new ToolStripSeparator());
            _trayMenu.Items.Add(itemExitFrontend);
            _trayMenu.Items.Add(itemPauseBackend);
            _trayMenu.Items.Add(itemExitAll);

            Icon appIcon = SystemIcons.Application;
            var iconPath = Path.Combine(_rootDir, "res", "icons", "AUTO-MAS.ico");
            if (File.Exists(iconPath))
            {
                try { appIcon = new Icon(iconPath); } catch { }
            }

            _trayIcon = new NotifyIcon
            {
                Icon = appIcon,
                Text = _headless ? "AUTO-MAS (无窗口静默运行中)" : "AUTO-MAS 自动化调度平台",
                ContextMenuStrip = _trayMenu,
                Visible = true
            };
            _trayIcon.DoubleClick += delegate { OpenBrowserConsole(); };
        }

        private string ResolvePythonExe()
        {
            string[] candidates = new string[]
            {
                Path.Combine(_rootDir, ".venv", "Scripts", "pythonw.exe"),
                Path.Combine(_rootDir, ".venv", "Scripts", "python.exe"),
                Path.Combine(_rootDir, "venv", "Scripts", "pythonw.exe"),
                Path.Combine(_rootDir, "venv", "Scripts", "python.exe"),
                Path.Combine(_rootDir, "python", "python.exe"),
                "python.exe"
            };
            foreach (var c in candidates)
            {
                if (Path.IsPathRooted(c) && File.Exists(c))
                {
                    return c;
                }
            }
            return "python.exe";
        }

        private string ResolveNodeExe()
        {
            string[] candidates = new string[]
            {
                Path.Combine(_rootDir, "node", "node.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "nodejs", "node.exe"),
                "node.exe"
            };
            foreach (var c in candidates)
            {
                if (Path.IsPathRooted(c) && File.Exists(c))
                {
                    return c;
                }
            }
            return "node.exe";
        }

        private async Task StartServicesAsync(bool initialLaunch)
        {
            await _servicesLock.WaitAsync();
            try
            {
                if (CheckPortReady(_frontendPort, "/__frontend_config"))
                {
                    if (initialLaunch && !_headless)
                        OpenBrowserWindow(_frontendPort);
                    return;
                }
                await StartServicesCoreAsync(initialLaunch);
                if (initialLaunch && !_headless)
                    OpenBrowserWindow(CheckPortReady(_frontendPort, "/__frontend_config") ? _frontendPort : _backendPort);
            }
            finally { _servicesLock.Release(); }
        }

        private async Task StartServicesCoreAsync(bool initialLaunch)
        {
            var serverJs = Path.Combine(_rootDir, "frontend", "server.js");
            // 从托盘重新打开页面不重放 --run-queue / --run-script 等启动动作。
            var joinedArgs = initialLaunch ? string.Join(" ", _args) + " --no-browser" : "--no-browser";

            // 优先通过 Node.js 前后端分离宿主启动（会自动拉起 Python 后端并调用系统浏览器）
            if (File.Exists(serverJs) && CanRunCommand(ResolveNodeExe(), "--version"))
            {
                var psi = new ProcessStartInfo
                {
                    FileName = ResolveNodeExe(),
                    Arguments = string.Format("\"{0}\" {1}", serverJs, joinedArgs).Trim(),
                    WorkingDirectory = _rootDir,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };
                Process.Start(psi);
                if (await WaitForServiceAsync(_frontendPort, "/__frontend_config", 60000)) return;
                throw new InvalidOperationException("前端启动超时，请检查 Node.js 启动日志。");
            }

            // 回退：直接无窗口拉起 Python 后端
            var mainPy = Path.Combine(_rootDir, "main.py");
            var pyPsi = new ProcessStartInfo
            {
                FileName = ResolvePythonExe(),
                Arguments = string.Format("\"{0}\" --no-admin-restart {1}", mainPy, joinedArgs).Trim(),
                WorkingDirectory = _rootDir,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            if (!CheckPortReady(_backendPort))
            {
                pyPsi.EnvironmentVariables["AUTO_MAS_BROWSER_HOST"] = "1";
                Process.Start(pyPsi);
            }

            if (!_headless)
            {
                await WaitForServiceAsync(_backendPort, "/api/core/health", 30000);
            }
        }

        private static async Task<bool> WaitForServiceAsync(int port, string path, int timeoutMs)
        {
            var elapsed = Stopwatch.StartNew();
            while (elapsed.ElapsedMilliseconds < timeoutMs)
            {
                if (CheckPortReady(port, path)) return true;
                var remaining = timeoutMs - elapsed.ElapsedMilliseconds;
                if (remaining <= 0) break;
                // 初始窗口快速发现就绪；慢启动恢复低频探测，避免持续增加请求。
                var interval = elapsed.ElapsedMilliseconds < 5000 ? 100 : 500;
                await Task.Delay((int)Math.Min(interval, remaining));
            }
            return false;
        }

        private static bool CanRunCommand(string exe, string args)
        {
            try
            {
                var p = Process.Start(new ProcessStartInfo
                {
                    FileName = exe,
                    Arguments = args,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true
                });
                if (p == null) return false;
                p.WaitForExit(3000);
                return p.ExitCode == 0;
            }
            catch
            {
                return false;
            }
        }

        private static bool CheckPortReady(int port, string path = "/api/core/health")
        {
            try
            {
                var req = (HttpWebRequest)WebRequest.Create(string.Format("http://127.0.0.1:{0}{1}", port, path));
                req.Timeout = 1200;
                using (var resp = (HttpWebResponse)req.GetResponse())
                {
                    return resp.StatusCode == HttpStatusCode.OK;
                }
            }
            catch
            {
                return false;
            }
        }

        private static bool IsPortListening(int port)
        {
            try
            {
                using (var client = new TcpClient())
                    return client.ConnectAsync("127.0.0.1", port).Wait(1000) && client.Connected;
            }
            catch { return false; }
        }

        private void OpenBrowserWindow(int port)
        {
            string browser = null;
            foreach (string basePath in new[] {
                Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),
                Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData) })
            {
                foreach (string relativePath in new[] {
                    "Microsoft\\Edge\\Application\\msedge.exe",
                    "Google\\Chrome\\Application\\chrome.exe" })
                {
                    string candidate = Path.Combine(basePath, relativePath);
                    if (File.Exists(candidate)) { browser = candidate; break; }
                }
                if (browser != null) break;
            }
            string url = string.Format("http://127.0.0.1:{0}", port);
            // 独立配置目录避免用户浏览器扩展启动 Native Messaging 的 CMD 宿主。
            Process.Start(new ProcessStartInfo
            {
                FileName = browser ?? "explorer.exe",
                Arguments = browser == null ? url : string.Format(
                    "--disable-extensions --no-first-run --no-default-browser-check --user-data-dir=\"{0}\" \"{1}\"",
                    Path.Combine(_rootDir, "data", "browser-profile"), url),
                UseShellExecute = false,
                CreateNoWindow = true
            });
        }

        private async void OpenBrowserConsole()
        {
            if (_openingBrowser) return;
            _openingBrowser = true;
            try
            {
                await StartServicesAsync(false);
                int targetPort = CheckPortReady(_frontendPort, "/__frontend_config") ? _frontendPort : _backendPort;
                OpenBrowserWindow(targetPort);
            }
            catch (Exception error)
            {
                ShowControlError(error);
            }
            finally { _openingBrowser = false; }
        }

        private void PostJsonAsync(string path, string jsonBody)
        {
            Task.Run(async () =>
            {
                try { await SendJsonAsync(_backendPort, path, jsonBody); }
                catch (Exception error) { ShowControlError(error); }
            });
        }

        private static async Task SendJsonAsync(int port, string path, string jsonBody)
        {
            var req = (HttpWebRequest)WebRequest.Create(string.Format("http://127.0.0.1:{0}{1}", port, path));
            req.Method = "POST";
            req.ContentType = "application/json; charset=utf-8";
            req.ReadWriteTimeout = 120000;
            var bytes = Encoding.UTF8.GetBytes(jsonBody);
            req.ContentLength = bytes.Length;
            using (var timeout = new CancellationTokenSource(120000))
            using (timeout.Token.Register(req.Abort))
            {
                using (var s = await req.GetRequestStreamAsync())
                {
                    await s.WriteAsync(bytes, 0, bytes.Length);
                }
                using (var resp = await req.GetResponseAsync())
                using (var reader = new StreamReader(resp.GetResponseStream(), Encoding.UTF8))
                {
                    var result = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(await reader.ReadToEndAsync());
                    if ((result.ContainsKey("code") && Convert.ToInt32(result["code"]) != 200) ||
                        (result.ContainsKey("success") && !Convert.ToBoolean(result["success"])))
                        throw new InvalidOperationException(result.ContainsKey("message") ? Convert.ToString(result["message"]) : "本机操作失败");
                }
            }
        }

        private async Task StopFrontendAsync()
        {
            if (!IsPortListening(_frontendPort)) return;
            await SendJsonAsync(_frontendPort, "/__host/invoke", "{\"method\":\"frontendStop\",\"args\":[]}");
            for (int i = 0; i < 40; i++)
            {
                if (!IsPortListening(_frontendPort)) return;
                await Task.Delay(100);
            }
            throw new InvalidOperationException("前端尚未退出，请稍后重试。");
        }

        private async Task RunControlAsync(Func<Task> action)
        {
            _trayMenu.Enabled = false;
            await _servicesLock.WaitAsync();
            try { await action(); }
            catch (Exception error) { ShowControlError(error); }
            finally
            {
                _servicesLock.Release();
                if (!_trayMenu.IsDisposed) _trayMenu.Enabled = true;
            }
        }

        private static void ShowControlError(Exception error)
        {
            MessageBox.Show(error.Message, "AUTO-MAS 操作未完成", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }

        private async Task ShutdownAndExitAsync()
        {
            if (IsPortListening(_backendPort))
            {
                await SendJsonAsync(_backendPort, "/api/core/close", "{}");
                bool stopped = false;
                for (int i = 0; i < 240; i++)
                {
                    if (!IsPortListening(_backendPort)) { stopped = true; break; }
                    await Task.Delay(500);
                }
                if (!stopped) throw new InvalidOperationException("后端尚未完成清理，保留服务运行，请查看日志后重试。");
            }
            // 后端已完成任务收尾；宿主可能已关闭，直接注销子会话以释放其中的进程和内存。
            await Task.Run(() =>
            {
                uint childSessionId;
                if (!WTSGetChildSessionId(out childSessionId))
                {
                    var error = Marshal.GetLastWin32Error();
                    if (error == 1168) return; // 当前没有子会话。
                    throw new Win32Exception(error, "无法取得远程桌面子会话，完全退出未完成。");
                }
                if (childSessionId == uint.MaxValue) return;
                if (!WTSLogoffSession(IntPtr.Zero, childSessionId, true))
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "无法注销远程桌面子会话，完全退出未完成。");
            });
            await StopFrontendAsync();
            if (_trayIcon != null)
            {
                _trayIcon.Visible = false;
                _trayIcon.Dispose();
                _trayIcon = null;
            }
            Application.Exit();
        }
    }

    internal static class Program
    {
        [STAThread]
        private static void Main(string[] args)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new LauncherTrayContext(args));
        }
    }
}
