using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

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
        private readonly string _rootDir;
        private readonly string[] _args;
        private readonly bool _headless;
        private readonly int _frontendPort = 36162;
        private readonly int _backendPort = 36163;
        private Process _managedProcess;
        private NotifyIcon _trayIcon;
        private ContextMenuStrip _trayMenu;

        public LauncherTrayContext(string[] args)
        {
            _rootDir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\', '/');
            _args = args ?? new string[0];
            _headless = HasFlag(_args, "--headless") || HasFlag(_args, "--no-window") || HasFlag(_args, "--no-browser");

            BuildTrayIcon();
            Task.Run(() => StartServicesAsync());
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

            var itemExit = new ToolStripMenuItem("❌ 退出 AUTO-MAS 全部服务");
            itemExit.Click += delegate { ShutdownAndExit(); };

            _trayMenu.Items.Add(itemOpenWeb);
            _trayMenu.Items.Add(new ToolStripSeparator());
            _trayMenu.Items.Add(itemShowRdp);
            _trayMenu.Items.Add(itemHideRdp);
            _trayMenu.Items.Add(new ToolStripSeparator());
            _trayMenu.Items.Add(itemToggleTask);
            _trayMenu.Items.Add(itemPrevTask);
            _trayMenu.Items.Add(itemNextTask);
            _trayMenu.Items.Add(new ToolStripSeparator());
            _trayMenu.Items.Add(itemExit);

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
                Path.Combine(_rootDir, ".venv", "Scripts", "python.exe"),
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

        private async Task StartServicesAsync()
        {
            var serverJs = Path.Combine(_rootDir, "frontend", "server.js");
            var joinedArgs = string.Join(" ", _args);

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
                _managedProcess = Process.Start(psi);
                return;
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
            _managedProcess = Process.Start(pyPsi);

            if (!_headless)
            {
                for (int i = 0; i < 60; i++)
                {
                    if (CheckPortReady(_backendPort))
                    {
                        Process.Start(new ProcessStartInfo
                        {
                            FileName = string.Format("http://127.0.0.1:{0}", _backendPort),
                            UseShellExecute = true
                        });
                        break;
                    }
                    await Task.Delay(500);
                }
            }
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

        private static bool CheckPortReady(int port)
        {
            try
            {
                var req = (HttpWebRequest)WebRequest.Create(string.Format("http://127.0.0.1:{0}/api/core/health", port));
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

        private void OpenBrowserConsole()
        {
            int targetPort = CheckPortReady(_frontendPort) ? _frontendPort : _backendPort;
            try
            {
                Process.Start(new ProcessStartInfo
                {
                    FileName = string.Format("http://127.0.0.1:{0}", targetPort),
                    UseShellExecute = true
                });
            }
            catch
            {
            }
        }

        private void PostJsonAsync(string path, string jsonBody)
        {
            Task.Run(() =>
            {
                try
                {
                    var req = (HttpWebRequest)WebRequest.Create(string.Format("http://127.0.0.1:{0}{1}", _backendPort, path));
                    req.Method = "POST";
                    req.ContentType = "application/json; charset=utf-8";
                    req.Timeout = 4000;
                    var bytes = Encoding.UTF8.GetBytes(jsonBody);
                    req.ContentLength = bytes.Length;
                    using (var s = req.GetRequestStream())
                    {
                        s.Write(bytes, 0, bytes.Length);
                    }
                    using (var resp = req.GetResponse()) { }
                }
                catch
                {
                }
            });
        }

        private void ShutdownAndExit()
        {
            PostJsonAsync("/api/core/close", "{}");
            Thread.Sleep(300);
            try
            {
                if (_managedProcess != null && !_managedProcess.HasExited)
                {
                    using (var killer = Process.Start(new ProcessStartInfo
                    {
                        FileName = "taskkill.exe",
                        Arguments = string.Format("/PID {0} /T /F", _managedProcess.Id),
                        UseShellExecute = false,
                        CreateNoWindow = true
                    }))
                    {
                        if (killer != null) killer.WaitForExit(5000);
                    }
                }
            }
            catch
            {
            }

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
