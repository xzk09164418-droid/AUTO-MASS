using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Globalization;
using System.IO;
using System.Net;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using BetterGenshinImpact.View.Controls.ChildSession;

namespace BetterGenshinImpact.Service.ChildSession
{
    /// <summary>
    /// 复刻 BetterGI `ChildSessionWindow.xaml` 暗色 Fluent 风格的本地远程桌面窗口与 HTTP IPC 服务端。
    /// 支持：
    /// 1. 默认系统托盘化运行（NotifyIcon + 离屏保活），完全不打扰主桌面，同时保证 MsRdpClient10 ActiveX 句柄常驻有效。
    /// 2. 与 BetterGI 桌面分身一致的顶部暗色控制栏（状态指示灯、启动、隐藏到托盘、切换窗口 Win+Tab、
    ///    观看模式/普通鼠标切换、控制中心下拉菜单、静音、置顶）与居中暗色连接/诊断卡片。
    /// 3. 常驻 Windows Child Session 远程桌面连接 + 计划任务 (`TASK_RUN_USE_SESSION_ID`) 子会话进程/包装器启动。
    /// 4. 外部程序借用远程桌面（Disconnect 让渡画面但保持 Child Session 存活）与停止使用后回传重连（Reconnect）。
    /// </summary>
    public sealed partial class ChildSessionHostForm : Form
    {
        private readonly RdpActiveXHost _rdpHost;
        private readonly HttpListener _httpListener;
        private readonly int _port;
        private readonly CancellationTokenSource _cts = new CancellationTokenSource();

        // BGI 风格配色
        private static readonly Color BgDark = Color.FromArgb(0, 0, 0);
        private static readonly Color TitleBarBg = Color.FromArgb(31, 31, 31);
        private static readonly Color CardBg = Color.FromArgb(23, 23, 23);
        private static readonly Color CardInnerBg = Color.FromArgb(32, 32, 32);
        private static readonly Color CardBorder = Color.FromArgb(58, 58, 58);
        private static readonly Color BtnBg = Color.FromArgb(43, 43, 43);
        private static readonly Color BtnHoverBg = Color.FromArgb(60, 60, 60);
        private static readonly Color AccentBlue = Color.FromArgb(47, 164, 231);
        private static readonly Color StatusGreen = Color.FromArgb(76, 195, 138);
        private static readonly Color StatusYellow = Color.FromArgb(255, 185, 0);
        private static readonly Color StatusGray = Color.FromArgb(138, 138, 138);
        private static readonly Color TextPrimary = Color.FromArgb(245, 245, 245);
        private static readonly Color TextSecondary = Color.FromArgb(200, 200, 200);
        private static readonly Color TextMuted = Color.FromArgb(156, 156, 156);

        // UI 控件
        private Panel _topBar;
        private Panel _statusDotPanel;
        private Label _titleLabel;
        private FlowLayoutPanel _rightButtonFlow;
        private Button _btnLaunch;
        private Button _btnHide;
        private Button _btnTaskView;
        private Button _btnWatchMode;
        private Button _btnControlCenter;
        private Button _btnMute;
        private Button _btnTopmost;
        private ContextMenuStrip _controlCenterMenu;

        // 系统托盘控件
        private NotifyIcon _trayIcon;
        private ContextMenuStrip _trayMenu;
        private ToolStripMenuItem _trayToggleVisibleItem;
        private ToolStripMenuItem _trayWatchModeItem;
        private bool _isHiddenToTray;
        private bool _trayBalloonShown;
        private Point _lastVisibleLocation = new Point(120, 80);

        private Panel _infoBarPanel;
        private Label _infoBarLabel;
        private Button _infoBarCloseBtn;

        private Panel _workspaceContainer;
        private Panel _overlayBackdrop;
        private Panel _centerCard;
        private Panel _badgePanel;
        private Panel _cardStatusDot;
        private Label _cardTitleLabel;
        private Label _cardDescLabel;
        private Panel _diagBox;
        private Label _lblRdpStateValue;
        private Label _lblSessionStateValue;
        private Label _lblLeaseStateValue;
        private Label _lblEnvSummary;
        private Button _btnPrimaryConnect;
        private Button _btnRefreshDiag;
        private Button _btnHelpDoc;
        private Label _lblFooterHint1;
        private Label _lblFooterHint2;

        // 状态字段
        private Size _desktopSize = new Size(2560, 1440);
        private bool _watchModeEnabled = true;
        private bool _audioMuted = true;
        private bool _smartSizingEnabled = true;
        private bool _sendShortcutsToRemote = true;
        private bool _lockDesktopAspectRatio = false;
        private bool _miniWindowMode = false;
        private Rectangle _normalBounds;
        private FormWindowState _windowStateBeforeMini;
        private bool _allowClose;
        private bool _isConnecting;
        private string _statusMessage = "桌面分身宿主已初始化（默认托盘常驻运行）";
        private string _externalLeaseHolder;
        private TaskCompletionSource<bool> _loginTcs;
        private readonly ChildSessionConnectionAttempt _connectionAttempt = new ChildSessionConnectionAttempt();

        public ChildSessionHostForm(int port = 36165, int width = 2560, int height = 1440, bool startHidden = true)
        {
            _port = port;
            _desktopSize = new Size(width, height);
            _isHiddenToTray = startHidden;

            AutoScaleMode = AutoScaleMode.None;
            Text = "automass桌面分身";
            MinimumSize = new Size(415, 90);
            StartPosition = FormStartPosition.Manual;
            var screenArea = Screen.PrimaryScreen != null ? Screen.PrimaryScreen.WorkingArea : new Rectangle(0, 0, 1920, 1080);
            ClientSize = new Size(Math.Min(1280, Math.Max(375, screenArea.Width - 40)),
                Math.Min(752, Math.Max(200, screenArea.Height - 80)));
            _lastVisibleLocation = new Point(
                screenArea.Left + Math.Max(0, (screenArea.Width - Width) / 2),
                screenArea.Top + Math.Max(0, (screenArea.Height - Height) / 2));
            Location = _lastVisibleLocation;

            BackColor = BgDark;
            ForeColor = TextPrimary;
            DoubleBuffered = true;
            Font = new Font("Microsoft YaHei UI", 9F, FontStyle.Regular, GraphicsUnit.Point);

            TryLoadWindowIcon();

            _rdpHost = new RdpActiveXHost();
            _rdpHost.LoginCompleted += OnRdpLoginCompleted;
            _rdpHost.ConnectionFailed += OnRdpConnectionFailed;
            _rdpHost.SessionDisconnected += OnRdpSessionDisconnected;

            BuildBgiStyleInterface();
            BuildSystemTrayIcon();
            InitializeResponsiveLayout();

            if (_isHiddenToTray)
            {
                ApplyTrayHiddenWindowState(showBalloon: false);
            }

            _httpListener = new HttpListener();
            _httpListener.Prefixes.Add(string.Format("http://127.0.0.1:{0}/", _port));
        }

        private void TryLoadWindowIcon()
        {
            try
            {
                string[] candidates = new string[]
                {
                    Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "AUTO-MAS.ico"),
                    Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "..", "icons", "AUTO-MAS.ico"),
                    Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "..", "..", "..", "..", "icons", "AUTO-MAS.ico"),
                    Path.Combine(Environment.CurrentDirectory, "res", "icons", "AUTO-MAS.ico")
                };
                foreach (var path in candidates)
                {
                    if (File.Exists(path))
                    {
                        Icon = new Icon(path);
                        break;
                    }
                }
            }
            catch
            {
            }
        }

        private void BuildSystemTrayIcon()
        {
            var trayStyle = new RhineTrayRenderer();
            _trayMenu = new ContextMenuStrip
            {
                ShowImageMargin = false,
                Renderer = trayStyle
            };

            _trayToggleVisibleItem = new ToolStripMenuItem("显示 automass桌面分身窗口");
            _trayToggleVisibleItem.Click += delegate
            {
                if (_isHiddenToTray)
                {
                    RestoreWindowFromTray();
                }
                else
                {
                    HideWindowToTray(showBalloon: false);
                }
            };

            _trayWatchModeItem = new ToolStripMenuItem("开启观看模式（屏蔽本机键鼠输入）")
            {
                Checked = _watchModeEnabled
            };
            _trayWatchModeItem.Click += delegate
            {
                _watchModeEnabled = !_watchModeEnabled;
                _rdpHost.SetInputBlocked(_watchModeEnabled);
                UpdateToolbarButtonsVisualState();
            };

            var trayLaunchItem = new ToolStripMenuItem("在桌面分身中启动程序...");
            trayLaunchItem.Click += delegate
            {
                RestoreWindowFromTray();
                PromptAndLaunchInChildSession();
            };

            var trayReconnectItem = new ToolStripMenuItem("立即连接 / 重连桌面分身");
            trayReconnectItem.Click += async delegate
            {
                _externalLeaseHolder = null;
                await EnsureConnectedAsync();
            };

            var trayYieldItem = new ToolStripMenuItem("暂时释放画面供外部程序借用");
            trayYieldItem.Click += async delegate
            {
                await HandleDisconnectForExternalAsync(new Dictionary<string, object>
                {
                    { "caller", "系统托盘手动释放" },
                    { "disconnectRdpView", true }
                });
            };

            var trayLogoffItem = new ToolStripMenuItem("断开并注销桌面分身会话");
            trayLogoffItem.Click += async delegate
            {
                await HandleLogoffAsync();
            };

            var trayExitItem = new ToolStripMenuItem("完全退出桌面分身宿主");
            trayExitItem.Click += delegate
            {
                _allowClose = true;
                Close();
            };

            _trayMenu.Items.Add(_trayToggleVisibleItem);
            _trayMenu.Items.Add(_trayWatchModeItem);
            _trayMenu.Items.Add(new ToolStripSeparator());
            _trayMenu.Items.Add(trayLaunchItem);
            _trayMenu.Items.Add(trayReconnectItem);
            _trayMenu.Items.Add(trayYieldItem);
            _trayMenu.Items.Add(new ToolStripSeparator());
            _trayMenu.Items.Add(trayLogoffItem);
            _trayMenu.Items.Add(trayExitItem);
            _trayMenu.Opening += delegate
            {
                _trayToggleVisibleItem.Text = _isHiddenToTray
                    ? "显示 automass桌面分身窗口"
                    : "隐藏桌面分身窗口到托盘";
                _trayWatchModeItem.Checked = _watchModeEnabled;
                trayStyle.Apply(_trayMenu, RhineTrayRenderer.IsDark(), RhineTrayRenderer.CursorDpi());
            };
            _trayMenu.Disposed += delegate { trayStyle.DisposeFont(); };

            _trayIcon = new NotifyIcon
            {
                Icon = Icon ?? SystemIcons.Application,
                Text = "automass桌面分身 (托盘常驻运行)",
                ContextMenuStrip = _trayMenu,
                Visible = true
            };
            _trayIcon.DoubleClick += delegate
            {
                if (_isHiddenToTray)
                {
                    RestoreWindowFromTray();
                }
                else
                {
                    HideWindowToTray(showBalloon: false);
                }
            };
        }

        /// <summary>
        /// 将窗口隐藏到系统托盘，同时保持 WinForms 句柄与 MsRdpClient10 ActiveX 处于已创建状态，
        /// 既不在任务栏/主桌面显示任何窗口，又保证后台远程桌面连接与渲染正常运作。
        /// </summary>
        private void ApplyTrayHiddenWindowState(bool showBalloon)
        {
            if (!_isHiddenToTray && Location.X > -10000 && Location.Y > -10000)
            {
                _lastVisibleLocation = Location;
            }
            _isHiddenToTray = true;
            ShowInTaskbar = false;
            Opacity = 0.0;
            Location = new Point(-32000, -32000);
            _statusMessage = "桌面分身已在系统托盘静默运行，不会干扰主桌面操作";

            if (showBalloon && !_trayBalloonShown && _trayIcon != null)
            {
                _trayBalloonShown = true;
                try
                {
                    _trayIcon.ShowBalloonTip(
                        2500,
                        "automass桌面分身已最小化到系统托盘",
                        "常驻远程桌面连接在后台保持运行，双击托盘图标可随时查看桌面分身画面。",
                        ToolTipIcon.Info);
                }
                catch
                {
                }
            }
        }

        public void HideWindowToTray(bool showBalloon = true)
        {
            if (InvokeRequired)
            {
                BeginInvoke(new Action<bool>(HideWindowToTray), showBalloon);
                return;
            }
            ApplyTrayHiddenWindowState(showBalloon);
        }

        public void RestoreWindowFromTray()
        {
            if (InvokeRequired)
            {
                BeginInvoke(new Action(RestoreWindowFromTray));
                return;
            }
            _isHiddenToTray = false;
            if (WindowState == FormWindowState.Minimized)
            {
                WindowState = FormWindowState.Normal;
            }
            Location = _lastVisibleLocation;
            Opacity = 1.0;
            ShowInTaskbar = true;
            Show();
            Activate();
            BringToFront();
            RefreshCenterCardUi();
        }

        private void BuildBgiStyleInterface()
        {
            // 1. 顶部工具栏 (复刻 BGI ChildSessionWindow.xaml TitleBar)
            _topBar = new Panel
            {
                Dock = DockStyle.Top,
                Height = 38,
                BackColor = TitleBarBg,
                Padding = new Padding(12, 4, 8, 4)
            };

            _statusDotPanel = new Panel
            {
                Size = new Size(12, 12),
                Location = new Point(14, 13),
                BackColor = Color.Transparent
            };
            _statusDotPanel.Paint += PaintStatusDot;

            _titleLabel = new Label
            {
                AutoSize = true,
                Location = new Point(32, 9),
                Text = "automass桌面分身",
                ForeColor = TextPrimary,
                Font = new Font("Microsoft YaHei UI", 9.5F, FontStyle.Bold, GraphicsUnit.Point)
            };

            _rightButtonFlow = new FlowLayoutPanel
            {
                Dock = DockStyle.Right,
                AutoSize = true,
                FlowDirection = FlowDirection.LeftToRight,
                WrapContents = false,
                BackColor = Color.Transparent,
                Padding = new Padding(0, 1, 0, 0)
            };

            _btnLaunch = CreateToolbarButton("▶ 启动", 76);
            _btnLaunch.Click += delegate { PromptAndLaunchInChildSession(); };

            _btnHide = CreateToolbarButton("👁 托盘隐藏", 88);
            _btnHide.Click += delegate
            {
                HideWindowToTray(showBalloon: true);
            };

            _btnTaskView = CreateToolbarButton("⇄ 切换窗口", 98);
            _btnTaskView.Click += delegate
            {
                try
                {
                    _rdpHost.SendTaskViewShortcut();
                    ShowInfoBar("已向桌面分身发送 Win+Tab 任务视图快捷键");
                }
                catch (Exception ex)
                {
                    ShowInfoBar(ex.Message);
                }
            };

            _btnWatchMode = CreateToolbarButton("👁 观看模式", 104);
            _btnWatchMode.Click += delegate
            {
                _watchModeEnabled = !_watchModeEnabled;
                _rdpHost.SetInputBlocked(_watchModeEnabled);
                UpdateToolbarButtonsVisualState();
                ShowInfoBar(_watchModeEnabled
                    ? "已开启观看模式：本机鼠标与键盘输入已屏蔽，不会干扰分身内脚本运行"
                    : "已切换为普通鼠标模式：本机鼠标与键盘可直接操作桌面分身");
            };

            BuildControlCenterMenu();
            _btnControlCenter = CreateToolbarButton("⊞ 控制中心 ▾", 108);
            _btnControlCenter.Click += delegate
            {
                SyncControlCenterMenuChecks();
                _controlCenterMenu.Show(_btnControlCenter, new Point(0, _btnControlCenter.Height));
            };

            _btnMute = CreateToolbarButton("🔇", 40);
            _btnMute.Click += delegate
            {
                _audioMuted = !_audioMuted;
                _rdpHost.SetAudioMuted(_audioMuted);
                UpdateToolbarButtonsVisualState();
                if (_rdpHost.ConnectedState == 1)
                {
                    _rdpHost.ReconnectToChildSession(_desktopSize);
                }
                ShowInfoBar(_audioMuted ? "桌面分身已静音" : "已恢复桌面分身声音输出");
            };

            _btnTopmost = CreateToolbarButton("📌", 40);
            _btnTopmost.Click += delegate
            {
                TopMost = !TopMost;
                UpdateToolbarButtonsVisualState();
                ShowInfoBar(TopMost ? "已开启窗口置顶" : "已取消窗口置顶");
            };

            _rightButtonFlow.Controls.Add(_btnLaunch);
            _rightButtonFlow.Controls.Add(_btnHide);
            _rightButtonFlow.Controls.Add(_btnTaskView);
            _rightButtonFlow.Controls.Add(_btnWatchMode);
            _rightButtonFlow.Controls.Add(_btnControlCenter);
            _rightButtonFlow.Controls.Add(_btnMute);
            _rightButtonFlow.Controls.Add(_btnTopmost);

            _topBar.Controls.Add(_rightButtonFlow);
            _topBar.Controls.Add(_statusDotPanel);
            _topBar.Controls.Add(_titleLabel);

            // 2. 顶部悬浮状态提示栏 (对应 BGI StatusInfoBar)
            _infoBarPanel = new Panel
            {
                Dock = DockStyle.Top,
                Height = 34,
                BackColor = Color.FromArgb(38, 38, 38),
                Padding = new Padding(14, 6, 10, 6),
                Visible = false
            };
            _infoBarLabel = new Label
            {
                Dock = DockStyle.Fill,
                ForeColor = TextPrimary,
                TextAlign = ContentAlignment.MiddleLeft,
                AutoEllipsis = true,
                Text = ""
            };
            _infoBarCloseBtn = new Button
            {
                Dock = DockStyle.Right,
                Width = 28,
                Text = "×",
                FlatStyle = FlatStyle.Flat,
                ForeColor = TextSecondary,
                BackColor = Color.Transparent,
                Cursor = Cursors.Hand
            };
            _infoBarCloseBtn.FlatAppearance.BorderSize = 0;
            _infoBarCloseBtn.Click += delegate { _infoBarPanel.Visible = false; };
            _infoBarPanel.Controls.Add(_infoBarLabel);
            _infoBarPanel.Controls.Add(_infoBarCloseBtn);

            // 3. 主工作区（承载 RdpActiveXHost 与 BGI 居中连接/状态卡片遮罩）
            _workspaceContainer = new Panel
            {
                Dock = DockStyle.Fill,
                BackColor = BgDark
            };

            _overlayBackdrop = new Panel
            {
                Dock = DockStyle.Fill,
                BackColor = Color.FromArgb(14, 14, 14)
            };
            _overlayBackdrop.Resize += delegate { CenterOverlayCard(); };

            BuildCenterDiagnosticCard();

            _overlayBackdrop.Controls.Add(_centerCard);
            _workspaceContainer.Controls.Add(_overlayBackdrop);
            _workspaceContainer.Controls.Add(_rdpHost);
            _workspaceContainer.ClientSizeChanged += delegate { _rdpHost.FitToWorkspace(); };
            _rdpHost.FitToWorkspace();
            _overlayBackdrop.BringToFront();

            Controls.Add(_workspaceContainer);
            Controls.Add(_infoBarPanel);
            Controls.Add(_topBar);

            UpdateToolbarButtonsVisualState();
            RefreshCenterCardUi();
        }

        private void BuildCenterDiagnosticCard()
        {
            _centerCard = new Panel
            {
                Size = new Size(620, 490),
                BackColor = CardBg
            };
            _centerCard.Paint += delegate(object s, PaintEventArgs e)
            {
                e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
                using (var pen = new Pen(CardBorder, 1f))
                {
                    e.Graphics.DrawRectangle(pen, 0, 0, _centerCard.Width - 1, _centerCard.Height - 1);
                }
            };

            _badgePanel = new Panel
            {
                Size = new Size(68, 68),
                Location = new Point((620 - 68) / 2, 24),
                BackColor = Color.Transparent
            };
            _badgePanel.Paint += delegate(object s, PaintEventArgs e)
            {
                e.Graphics.ScaleTransform(_badgePanel.Width / 68f, _badgePanel.Height / 68f);
                e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
                using (var brush = new SolidBrush(Color.FromArgb(38, 47, 164, 231)))
                using (var pen = new Pen(Color.FromArgb(95, 47, 164, 231), 1.5f))
                {
                    e.Graphics.FillEllipse(brush, 2, 2, 63, 63);
                    e.Graphics.DrawEllipse(pen, 2, 2, 63, 63);
                }
                using (var font = new Font("Segoe UI Symbol", 22F, FontStyle.Regular))
                using (var sf = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center })
                using (var textBrush = new SolidBrush(AccentBlue))
                {
                    e.Graphics.DrawString("🖥", font, textBrush, new RectangleF(0, 2, 68, 66), sf);
                }
            };

            _cardStatusDot = new Panel
            {
                Size = new Size(10, 10),
                Location = new Point(195, 113),
                BackColor = Color.Transparent
            };
            _cardStatusDot.Paint += PaintStatusDot;

            _cardTitleLabel = new Label
            {
                AutoSize = false,
                Size = new Size(540, 34),
                Location = new Point(40, 100),
                TextAlign = ContentAlignment.MiddleCenter,
                Font = new Font("Microsoft YaHei UI", 16F, FontStyle.Bold, GraphicsUnit.Point),
                ForeColor = TextPrimary,
                Text = "准备启动桌面分身"
            };

            _cardDescLabel = new Label
            {
                AutoSize = false,
                Size = new Size(540, 40),
                Location = new Point(40, 138),
                TextAlign = ContentAlignment.TopCenter,
                Font = new Font("Microsoft YaHei UI", 9.5F, FontStyle.Regular, GraphicsUnit.Point),
                ForeColor = TextSecondary,
                Text = "自动启用 Windows Child Session，并使用当前登录账户进入独立的本地远程桌面会话。"
            };

            _diagBox = new Panel
            {
                Size = new Size(548, 156),
                Location = new Point(36, 184),
                BackColor = CardInnerBg
            };
            _diagBox.Paint += delegate(object s, PaintEventArgs e)
            {
                using (var pen = new Pen(Color.FromArgb(48, 255, 255, 255), 1f))
                {
                    e.Graphics.DrawRectangle(pen, 0, 0, _diagBox.Width - 1, _diagBox.Height - 1);
                }
            };

            var lblRdpKey = new Label
            {
                AutoSize = true,
                Location = new Point(16, 14),
                ForeColor = TextMuted,
                Text = "RDP 状态"
            };
            _lblRdpStateValue = new Label
            {
                AutoSize = false,
                Size = new Size(410, 20),
                Location = new Point(122, 14),
                ForeColor = TextPrimary,
                Font = new Font("Microsoft YaHei UI", 9F, FontStyle.Bold),
                Text = "未连接"
            };

            var lblSessionKey = new Label
            {
                AutoSize = true,
                Location = new Point(16, 42),
                ForeColor = TextMuted,
                Text = "桌面分身会话"
            };
            _lblSessionStateValue = new Label
            {
                AutoSize = false,
                Size = new Size(410, 20),
                Location = new Point(122, 42),
                ForeColor = TextPrimary,
                Font = new Font("Microsoft YaHei UI", 9F, FontStyle.Bold),
                Text = "检测中..."
            };

            var lblLeaseKey = new Label
            {
                AutoSize = true,
                Location = new Point(16, 70),
                ForeColor = TextMuted,
                Text = "外部让渡状态"
            };
            _lblLeaseStateValue = new Label
            {
                AutoSize = false,
                Size = new Size(410, 20),
                Location = new Point(122, 70),
                ForeColor = StatusGreen,
                Font = new Font("Microsoft YaHei UI", 9F, FontStyle.Bold),
                Text = "空闲（AUTO-MAS 队列可用）"
            };

            _lblEnvSummary = new Label
            {
                AutoSize = false,
                Size = new Size(516, 52),
                Location = new Point(16, 98),
                ForeColor = TextSecondary,
                Font = new Font("Microsoft YaHei UI", 8.5F, FontStyle.Regular),
                Text = "Windows Child Session 环境检查正常。"
            };

            _diagBox.Controls.Add(lblRdpKey);
            _diagBox.Controls.Add(_lblRdpStateValue);
            _diagBox.Controls.Add(lblSessionKey);
            _diagBox.Controls.Add(_lblSessionStateValue);
            _diagBox.Controls.Add(lblLeaseKey);
            _diagBox.Controls.Add(_lblLeaseStateValue);
            _diagBox.Controls.Add(_lblEnvSummary);

            _btnPrimaryConnect = new Button
            {
                Size = new Size(168, 38),
                Location = new Point(116, 356),
                Text = "▶ 启动并连接",
                FlatStyle = FlatStyle.Flat,
                BackColor = AccentBlue,
                ForeColor = Color.White,
                Font = new Font("Microsoft YaHei UI", 9.5F, FontStyle.Bold),
                Cursor = Cursors.Hand
            };
            _btnPrimaryConnect.FlatAppearance.BorderSize = 0;
            _btnPrimaryConnect.Click += async delegate
            {
                _externalLeaseHolder = null;
                await EnsureConnectedAsync();
            };

            _btnRefreshDiag = new Button
            {
                Size = new Size(124, 38),
                Location = new Point(296, 356),
                Text = "🔄 刷新状态",
                FlatStyle = FlatStyle.Flat,
                BackColor = BtnBg,
                ForeColor = TextPrimary,
                Cursor = Cursors.Hand
            };
            _btnRefreshDiag.FlatAppearance.BorderColor = CardBorder;
            _btnRefreshDiag.Click += delegate { RefreshCenterCardUi(); };

            _btnHelpDoc = new Button
            {
                Size = new Size(88, 38),
                Location = new Point(432, 356),
                Text = "使用说明",
                FlatStyle = FlatStyle.Flat,
                BackColor = BtnBg,
                ForeColor = TextSecondary,
                Cursor = Cursors.Hand
            };
            _btnHelpDoc.FlatAppearance.BorderColor = CardBorder;
            _btnHelpDoc.Click += delegate
            {
                MessageBox.Show(
                    this,
                    "【automass桌面分身 (Child Session) 说明】\n\n" +
                    "1. 默认托盘运行：远程桌面宿主默认最小化在系统托盘运行，避免打扰主桌面；双击系统托盘图标或在 Web 控制台点击“显示远程桌面窗口”即可查看画面。\n" +
                    "2. 包装器模式：通过任务计划程序 (TASK_RUN_USE_SESSION_ID) 在桌面分身内拉起 child_session_wrapper.py，实时采集脚本 PID 与退出码，并在结束或超上限时间时执行 3 遍 taskkill /F /T。\n" +
                    "3. 外部程序借用与让渡：外部程序可调用 POST /api/child-session/acquire 申请借用桌面分身，队列将在相邻子任务间隔自动暂停并释放画面，待外部程序调用 POST /api/child-session/release 后自动恢复。\n" +
                    "4. 观看模式：开启观看模式后，本机鼠标与键盘不会传入桌面分身，避免误触后台运行的自动化脚本。",
                    "桌面分身帮助说明",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Information);
            };

            _lblFooterHint1 = new Label
            {
                AutoSize = false,
                Size = new Size(548, 22),
                Location = new Point(36, 412),
                TextAlign = ContentAlignment.MiddleCenter,
                ForeColor = TextMuted,
                Font = new Font("Microsoft YaHei UI", 8.5F),
                Text = "首次连接时，Windows 可能会弹出凭据确认框；确认后才会真正创建新的桌面分身。"
            };

            _lblFooterHint2 = new Label
            {
                AutoSize = false,
                Size = new Size(548, 22),
                Location = new Point(36, 436),
                TextAlign = ContentAlignment.MiddleCenter,
                ForeColor = TextMuted,
                Font = new Font("Microsoft YaHei UI", 8.5F),
                Text = "提示：点击右上角关闭或「托盘隐藏」仅隐藏窗口到系统托盘，常驻远程桌面在后台保持运行。"
            };

            _centerCard.Controls.Add(_badgePanel);
            _centerCard.Controls.Add(_cardStatusDot);
            _centerCard.Controls.Add(_cardTitleLabel);
            _centerCard.Controls.Add(_cardDescLabel);
            _centerCard.Controls.Add(_diagBox);
            _centerCard.Controls.Add(_btnPrimaryConnect);
            _centerCard.Controls.Add(_btnRefreshDiag);
            _centerCard.Controls.Add(_btnHelpDoc);
            _centerCard.Controls.Add(_lblFooterHint1);
            _centerCard.Controls.Add(_lblFooterHint2);
        }

        private void CenterOverlayCard()
        {
            if (_overlayBackdrop == null || _centerCard == null)
            {
                return;
            }
            LayoutResponsiveControls();
        }

        private Button CreateToolbarButton(string text, int width)
        {
            var btn = new Button
            {
                Text = text,
                Size = new Size(width, 28),
                Margin = new Padding(3, 0, 3, 0),
                FlatStyle = FlatStyle.Flat,
                BackColor = BtnBg,
                ForeColor = TextPrimary,
                Cursor = Cursors.Hand,
                Font = new Font("Microsoft YaHei UI", 8.5F, FontStyle.Regular, GraphicsUnit.Point)
            };
            btn.FlatAppearance.BorderSize = 1;
            btn.FlatAppearance.BorderColor = CardBorder;
            btn.FlatAppearance.MouseOverBackColor = BtnHoverBg;
            return btn;
        }

        private void BuildControlCenterMenu()
        {
            _controlCenterMenu = new ContextMenuStrip
            {
                BackColor = Color.FromArgb(34, 34, 34),
                ForeColor = TextPrimary,
                ShowImageMargin = true
            };

            var itemLaunch = new ToolStripMenuItem("在桌面分身中运行脚本/程序...");
            itemLaunch.ForeColor = TextPrimary;
            itemLaunch.Click += delegate { PromptAndLaunchInChildSession(); };

            var itemMiniWindow = new ToolStripMenuItem("切换到小窗模式 (480×270 置顶)") { Name = "MenuMiniWindow", ForeColor = TextPrimary };
            itemMiniWindow.Click += delegate { ToggleMiniWindowMode(); };

            var itemWatchMode = new ToolStripMenuItem("开启观看模式（屏蔽本机键鼠输入）") { Name = "MenuWatchMode", ForeColor = TextPrimary };
            itemWatchMode.Click += delegate
            {
                _watchModeEnabled = !_watchModeEnabled;
                _rdpHost.SetInputBlocked(_watchModeEnabled);
                UpdateToolbarButtonsVisualState();
            };

            // 分辨率子菜单
            var menuResolution = new ToolStripMenuItem("桌面分辨率") { Name = "MenuResolution", ForeColor = TextPrimary };
            AddResolutionMenuItem(menuResolution, "1280 × 720 (16:9)", 1280, 720);
            AddResolutionMenuItem(menuResolution, "1280 × 800 (16:10)", 1280, 800);
            AddResolutionMenuItem(menuResolution, "1600 × 900 (16:9)", 1600, 900);
            AddResolutionMenuItem(menuResolution, "1920 × 1080 (16:9)", 1920, 1080);
            AddResolutionMenuItem(menuResolution, "1920 × 1200 (16:10)", 1920, 1200);
            AddResolutionMenuItem(menuResolution, "2560 × 1440 (16:9 默认)", 2560, 1440);
            AddResolutionMenuItem(menuResolution, "2560 × 1600 (16:10)", 2560, 1600);
            AddResolutionMenuItem(menuResolution, "2880 × 1620 (16:9)", 2880, 1620);
            AddResolutionMenuItem(menuResolution, "2880 × 1800 (16:10)", 2880, 1800);
            AddResolutionMenuItem(menuResolution, "3200 × 1800 (16:9)", 3200, 1800);
            AddResolutionMenuItem(menuResolution, "3200 × 2000 (16:10)", 3200, 2000);
            AddResolutionMenuItem(menuResolution, "3840 × 2160 (16:9)", 3840, 2160);
            AddResolutionMenuItem(menuResolution, "3840 × 2400 (16:10)", 3840, 2400);

            // 窗口缩放子菜单
            var menuScaling = new ToolStripMenuItem("窗口画面模式") { Name = "MenuScaling", ForeColor = TextPrimary };
            var itemSmartSizing = new ToolStripMenuItem("自适应缩放 (SmartSizing)") { Name = "ScaleSmart", ForeColor = TextPrimary };
            itemSmartSizing.Click += delegate
            {
                _smartSizingEnabled = true;
                _lockDesktopAspectRatio = false;
                _rdpHost.SetSmartSizing(true);
            };
            var itemNative1To1 = new ToolStripMenuItem("1 : 1 原始像素") { Name = "Scale1To1", ForeColor = TextPrimary };
            itemNative1To1.Click += delegate
            {
                _smartSizingEnabled = false;
                _lockDesktopAspectRatio = false;
                _rdpHost.SetSmartSizing(false);
            };
            var itemDesktopAspect = new ToolStripMenuItem("保持所选桌面宽高比") { Name = "ScaleDesktopAspect", ForeColor = TextPrimary };
            itemDesktopAspect.Click += delegate
            {
                _smartSizingEnabled = true;
                _lockDesktopAspectRatio = true;
                _rdpHost.SetSmartSizing(true);
                EnforceDesktopClientRatio();
            };
            menuScaling.DropDownItems.Add(itemSmartSizing);
            menuScaling.DropDownItems.Add(itemNative1To1);
            menuScaling.DropDownItems.Add(itemDesktopAspect);

            // 快捷键子菜单
            var menuShortcuts = new ToolStripMenuItem("快捷键") { Name = "MenuShortcuts", ForeColor = TextPrimary };
            var itemSendSysKeys = new ToolStripMenuItem("系统组合键发送到桌面分身") { Name = "SendSysKeys", ForeColor = TextPrimary };
            itemSendSysKeys.Click += delegate
            {
                _sendShortcutsToRemote = !_sendShortcutsToRemote;
                _rdpHost.SetSendSystemShortcutsToRemote(_sendShortcutsToRemote);
                if (_rdpHost.ConnectedState == 1)
                {
                    _rdpHost.ReconnectToChildSession(_desktopSize);
                }
            };
            var itemWinD = new ToolStripMenuItem("发送 Win + D 显示桌面") { ForeColor = TextPrimary };
            itemWinD.Click += delegate
            {
                try { _rdpHost.SendShowDesktopShortcut(); }
                catch (Exception ex) { ShowInfoBar(ex.Message); }
            };
            var itemWinTab = new ToolStripMenuItem("发送 Win + Tab 切换窗口") { ForeColor = TextPrimary };
            itemWinTab.Click += delegate
            {
                try { _rdpHost.SendTaskViewShortcut(); }
                catch (Exception ex) { ShowInfoBar(ex.Message); }
            };
            menuShortcuts.DropDownItems.Add(itemSendSysKeys);
            menuShortcuts.DropDownItems.Add(new ToolStripSeparator());
            menuShortcuts.DropDownItems.Add(itemWinD);
            menuShortcuts.DropDownItems.Add(itemWinTab);

            // 更多子菜单
            var menuMore = new ToolStripMenuItem("更多") { Name = "MenuMore", ForeColor = TextPrimary };
            var itemOpenTaskMgr = new ToolStripMenuItem("在桌面分身中打开任务管理器 (taskmgr.exe)") { ForeColor = TextPrimary };
            itemOpenTaskMgr.Click += async delegate { await LaunchQuickToolInChildSessionAsync("taskmgr.exe"); };

            var itemOpenCmd = new ToolStripMenuItem("在桌面分身中打开命令行 (cmd.exe)") { ForeColor = TextPrimary };
            itemOpenCmd.Click += async delegate { await LaunchQuickToolInChildSessionAsync("cmd.exe"); };

            var itemYieldExternal = new ToolStripMenuItem("暂时释放 RDP 画面供外部程序借用") { ForeColor = TextPrimary };
            itemYieldExternal.Click += async delegate
            {
                await HandleDisconnectForExternalAsync(new Dictionary<string, object>
                {
                    { "caller", "手动释放(UI)" },
                    { "disconnectRdpView", true }
                });
            };

            var itemReclaimExternal = new ToolStripMenuItem("从外部程序收回并重连桌面分身") { ForeColor = TextPrimary };
            itemReclaimExternal.Click += async delegate
            {
                await HandleReconnectAfterExternalAsync(null);
            };

            var itemLogoff = new ToolStripMenuItem("断开并注销桌面分身会话") { ForeColor = Color.FromArgb(255, 110, 110) };
            itemLogoff.Click += async delegate
            {
                var confirm = MessageBox.Show(
                    this,
                    "确定要断开并注销桌面分身会话吗？\n这会关闭桌面分身内正在运行的所有程序。",
                    "断开并注销桌面分身",
                    MessageBoxButtons.YesNo,
                    MessageBoxIcon.Warning);
                if (confirm == DialogResult.Yes)
                {
                    await HandleLogoffAsync();
                }
            };

            menuMore.DropDownItems.Add(itemOpenTaskMgr);
            menuMore.DropDownItems.Add(itemOpenCmd);
            menuMore.DropDownItems.Add(new ToolStripSeparator());
            menuMore.DropDownItems.Add(itemYieldExternal);
            menuMore.DropDownItems.Add(itemReclaimExternal);
            menuMore.DropDownItems.Add(new ToolStripSeparator());
            menuMore.DropDownItems.Add(itemLogoff);

            _controlCenterMenu.Items.Add(itemLaunch);
            _controlCenterMenu.Items.Add(itemMiniWindow);
            _controlCenterMenu.Items.Add(itemWatchMode);
            _controlCenterMenu.Items.Add(new ToolStripSeparator());
            _controlCenterMenu.Items.Add(menuResolution);
            _controlCenterMenu.Items.Add(menuScaling);
            _controlCenterMenu.Items.Add(menuShortcuts);
            _controlCenterMenu.Items.Add(new ToolStripSeparator());
            _controlCenterMenu.Items.Add(menuMore);
        }

        private void AddResolutionMenuItem(ToolStripMenuItem parent, string label, int w, int h)
        {
            var item = new ToolStripMenuItem(label)
            {
                Tag = new Size(w, h),
                ForeColor = TextPrimary
            };
            item.Click += delegate
            {
                _desktopSize = new Size(w, h);
                if (_rdpHost.ConnectedState == 1)
                {
                    _rdpHost.ReconnectToChildSession(_desktopSize);
                }
                RefreshCenterCardUi();
                ShowInfoBar(string.Format("桌面分身分辨率已切换为 {0} × {1}", w, h));
            };
            parent.DropDownItems.Add(item);
        }

        private void SyncControlCenterMenuChecks()
        {
            var itemMini = _controlCenterMenu.Items["MenuMiniWindow"] as ToolStripMenuItem;
            if (itemMini != null)
            {
                itemMini.Text = _miniWindowMode ? "恢复普通窗口模式" : "切换到小窗模式 (480×270 置顶)";
                itemMini.Checked = _miniWindowMode;
            }

            var itemWatch = _controlCenterMenu.Items["MenuWatchMode"] as ToolStripMenuItem;
            if (itemWatch != null)
            {
                itemWatch.Text = _watchModeEnabled ? "退出观看模式（恢复本机键鼠输入）" : "开启观看模式（屏蔽本机键鼠输入）";
                itemWatch.Checked = _watchModeEnabled;
            }

            var menuRes = _controlCenterMenu.Items["MenuResolution"] as ToolStripMenuItem;
            if (menuRes != null)
            {
                menuRes.Text = string.Format("桌面分辨率 ({0} × {1})", _desktopSize.Width, _desktopSize.Height);
                foreach (ToolStripItem sub in menuRes.DropDownItems)
                {
                    var mi = sub as ToolStripMenuItem;
                    if (mi != null && mi.Tag is Size)
                    {
                        var sz = (Size)mi.Tag;
                        mi.Checked = sz.Width == _desktopSize.Width && sz.Height == _desktopSize.Height;
                    }
                }
            }

            var menuScale = _controlCenterMenu.Items["MenuScaling"] as ToolStripMenuItem;
            if (menuScale != null)
            {
                var sSmart = menuScale.DropDownItems["ScaleSmart"] as ToolStripMenuItem;
                var s1To1 = menuScale.DropDownItems["Scale1To1"] as ToolStripMenuItem;
                var sDesktopAspect = menuScale.DropDownItems["ScaleDesktopAspect"] as ToolStripMenuItem;
                if (sSmart != null) sSmart.Checked = _smartSizingEnabled && !_lockDesktopAspectRatio;
                if (s1To1 != null) s1To1.Checked = !_smartSizingEnabled;
                if (sDesktopAspect != null) sDesktopAspect.Checked = _lockDesktopAspectRatio;
            }

            var menuShortcuts = _controlCenterMenu.Items["MenuShortcuts"] as ToolStripMenuItem;
            if (menuShortcuts != null)
            {
                var sendSys = menuShortcuts.DropDownItems["SendSysKeys"] as ToolStripMenuItem;
                if (sendSys != null) sendSys.Checked = _sendShortcutsToRemote;
            }
        }

        private void ToggleMiniWindowMode()
        {
            if (!_miniWindowMode)
            {
                _windowStateBeforeMini = WindowState;
                _normalBounds = WindowState == FormWindowState.Normal ? Bounds : RestoreBounds;
                WindowState = FormWindowState.Normal;
                _miniWindowMode = true;
                TopMost = true;
                ClientSize = new Size(520, 328);
                ShowInfoBar("已进入小窗置顶模式，可通过控制中心恢复普通窗口");
            }
            else
            {
                _miniWindowMode = false;
                WindowState = FormWindowState.Normal;
                if (_normalBounds.Width > 200 && _normalBounds.Height > 200)
                {
                    Bounds = _normalBounds;
                }
                else
                {
                    ClientSize = new Size(1280, 752);
                }
                WindowState = _windowStateBeforeMini;
            }
            UpdateToolbarButtonsVisualState();
        }

        private void EnforceDesktopClientRatio()
        {
            if (!_lockDesktopAspectRatio || WindowState != FormWindowState.Normal || _isHiddenToTray)
            {
                return;
            }
            var targetWidth = Math.Max(480, ClientSize.Width);
            var desktop = _rdpHost.RemoteDesktopSize;
            if (desktop.IsEmpty) desktop = _desktopSize;
            if (desktop.Width <= 0 || desktop.Height <= 0) return;
            var targetRdpHeight = (int)Math.Round(targetWidth * (double)desktop.Height / desktop.Width);
            var chromeHeight = _topBar.Height + (_infoBarPanel.Visible ? _infoBarPanel.Height : 0);
            ClientSize = new Size(targetWidth, targetRdpHeight + chromeHeight);
        }

        private void UpdateToolbarButtonsVisualState()
        {
            if (_btnWatchMode != null)
            {
                _btnWatchMode.Text = _watchModeEnabled ? "👁 观看模式" : "🖱 普通鼠标";
                _btnWatchMode.BackColor = _watchModeEnabled ? Color.FromArgb(30, 88, 128) : BtnBg;
                _btnWatchMode.FlatAppearance.BorderColor = _watchModeEnabled ? AccentBlue : CardBorder;
            }
            if (_btnMute != null)
            {
                _btnMute.Text = _audioMuted ? "🔇" : "🔊";
                _btnMute.BackColor = _audioMuted ? BtnBg : Color.FromArgb(30, 88, 128);
            }
            if (_btnTopmost != null)
            {
                _btnTopmost.BackColor = TopMost ? Color.FromArgb(30, 88, 128) : BtnBg;
                _btnTopmost.FlatAppearance.BorderColor = TopMost ? AccentBlue : CardBorder;
            }
            if (_statusDotPanel != null)
            {
                _statusDotPanel.Invalidate();
            }
            if (_cardStatusDot != null)
            {
                _cardStatusDot.Invalidate();
            }
        }

        private Color GetCurrentStatusDotColor()
        {
            if (_isConnecting || !string.IsNullOrEmpty(_externalLeaseHolder))
            {
                return StatusYellow;
            }
            if (_rdpHost != null && _rdpHost.ConnectedState == 1)
            {
                return StatusGreen;
            }
            return StatusGray;
        }

        private void PaintStatusDot(object sender, PaintEventArgs e)
        {
            var panel = sender as Panel;
            if (panel == null) return;
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            using (var brush = new SolidBrush(GetCurrentStatusDotColor()))
            {
                e.Graphics.FillEllipse(brush, 1, 1, panel.Width - 3, panel.Height - 3);
            }
        }

        private void ShowInfoBar(string message)
        {
            if (InvokeRequired)
            {
                BeginInvoke(new Action<string>(ShowInfoBar), message);
                return;
            }
            _statusMessage = message;
            _infoBarLabel.Text = "ℹ " + message;
            _infoBarPanel.Visible = true;
            RefreshCenterCardUi();
        }

        private void RefreshCenterCardUi()
        {
            if (InvokeRequired)
            {
                BeginInvoke(new Action(RefreshCenterCardUi));
                return;
            }

            var connected = _rdpHost != null && _rdpHost.ConnectedState == 1;
            var sid = ChildSessionNativeMethods.TryGetChildSessionId();
            var issues = ChildSessionEnvironmentCheck.Collect();
            var envSummary = ChildSessionEnvironmentCheck.BuildSummary(issues);

            if (_titleLabel != null)
            {
                var sidBadge = sid.HasValue ? string.Format("  [Session #{0}]", sid.Value) : "";
                var leaseBadge = !string.IsNullOrEmpty(_externalLeaseHolder)
                    ? string.Format("  [已让渡: {0}]", _externalLeaseHolder)
                    : "";
                _titleLabel.Text = string.Format("automass桌面分身{0}{1}", sidBadge, leaseBadge);
            }

            if (_trayIcon != null)
            {
                string trayState = !string.IsNullOrEmpty(_externalLeaseHolder)
                    ? "已让渡外部程序"
                    : (connected ? (sid.HasValue ? "已连接 #" + sid.Value : "已连接") : "待连接");
                string trayText = string.Format("automass桌面分身 ({0})", trayState);
                _trayIcon.Text = trayText.Length > 63 ? trayText.Substring(0, 63) : trayText;
            }

            UpdateToolbarButtonsVisualState();

            if (connected && string.IsNullOrEmpty(_externalLeaseHolder))
            {
                _overlayBackdrop.Visible = false;
                LayoutResponsiveControls();
                _rdpHost.BringToFront();
                return;
            }

            _overlayBackdrop.Visible = true;
            _overlayBackdrop.BringToFront();
            CenterOverlayCard();

            if (!string.IsNullOrEmpty(_externalLeaseHolder))
            {
                _cardTitleLabel.Text = "桌面分身已让渡给外部程序";
                _cardDescLabel.Text = string.Format(
                    "当前队列处于子任务间隔，已将本地远程桌面让渡给外部程序 [{0}] 使用；外部程序调用回传释放接口后将自动恢复连接。",
                    _externalLeaseHolder);
                _lblRdpStateValue.Text = connected ? "已保持画面（控制权已让渡）" : "已释放 RDP 画面流（Child Session 存活）";
                _lblLeaseStateValue.Text = string.Format("正由 [{0}] 借用中", _externalLeaseHolder);
                _lblLeaseStateValue.ForeColor = StatusYellow;
                _btnPrimaryConnect.Text = "▶ 立即收回并重连";
            }
            else if (_isConnecting)
            {
                _cardTitleLabel.Text = "正在创建桌面分身...";
                _cardDescLabel.Text = "正在启用 Windows Child Session 并连接本地 RDP 会话，请在弹出的凭据窗口中确认登录。";
                _lblRdpStateValue.Text = "正在连接...";
                _lblLeaseStateValue.Text = "空闲（AUTO-MAS 队列可用）";
                _lblLeaseStateValue.ForeColor = StatusGreen;
                _btnPrimaryConnect.Text = "连接中...";
            }
            else
            {
                _cardTitleLabel.Text = "准备启动桌面分身";
                _cardDescLabel.Text = _statusMessage;
                _lblRdpStateValue.Text = "未连接";
                _lblLeaseStateValue.Text = "空闲（AUTO-MAS 队列可用）";
                _lblLeaseStateValue.ForeColor = StatusGreen;
                _btnPrimaryConnect.Text = "▶ 启动并连接";
            }

            _lblSessionStateValue.Text = sid.HasValue
                ? string.Format("已建立活跃 Child Session (ID = {0}，分辨率 {1}×{2})", sid.Value, _desktopSize.Width, _desktopSize.Height)
                : string.Format("尚未检测到活跃 Child Session（目标分辨率 {0}×{1}）", _desktopSize.Width, _desktopSize.Height);

            _lblEnvSummary.Text = string.IsNullOrWhiteSpace(envSummary)
                ? "✓ Windows Child Session 与 RDP 端口环境预检通过。"
                : envSummary;
            _lblEnvSummary.ForeColor = string.IsNullOrWhiteSpace(envSummary) ? StatusGreen : StatusYellow;
            LayoutResponsiveControls();
        }

        private async void PromptAndLaunchInChildSession()
        {
            using (var dlg = new OpenFileDialog())
            {
                dlg.Title = "选择要在 automass桌面分身中启动的脚本或程序";
                dlg.Filter = "可执行程序或脚本 (*.exe;*.bat;*.cmd;*.py)|*.exe;*.bat;*.cmd;*.py|所有文件 (*.*)|*.*";
                if (dlg.ShowDialog(this) != DialogResult.OK)
                {
                    return;
                }
                await LaunchQuickToolInChildSessionAsync(dlg.FileName);
            }
        }

        private async Task LaunchQuickToolInChildSessionAsync(string exePath, string args = "")
        {
            try
            {
                var sid = ChildSessionNativeMethods.TryGetChildSessionId();
                if (!sid.HasValue)
                {
                    var ok = await EnsureConnectedAsync();
                    sid = ChildSessionNativeMethods.TryGetChildSessionId();
                    if (!ok || !sid.HasValue)
                    {
                        ShowInfoBar("桌面分身尚未连接，无法在子会话中启动程序");
                        return;
                    }
                }

                string resolvedExe = exePath;
                if (!Path.IsPathRooted(resolvedExe))
                {
                    var sys32 = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), resolvedExe);
                    if (File.Exists(sys32))
                    {
                        resolvedExe = sys32;
                    }
                }

                await ChildSessionProcessLauncher.LaunchInChildSessionAsync(sid.Value, resolvedExe, args);
                ShowInfoBar(string.Format("已在桌面分身 (Session #{0}) 启动: {1}", sid.Value, Path.GetFileName(resolvedExe)));
            }
            catch (Exception ex)
            {
                ShowInfoBar("启动程序失败: " + ex.GetBaseException().Message);
            }
        }

        protected override void OnLoad(EventArgs e)
        {
            base.OnLoad(e);
            CenterOverlayCard();
            _rdpHost.SetSmartSizing(_smartSizingEnabled);
            _rdpHost.SetAudioMuted(_audioMuted);
            _rdpHost.SetSendSystemShortcutsToRemote(_sendShortcutsToRemote);

            try
            {
                _httpListener.Start();
                Task.Run(() => AcceptHttpRequestsLoopAsync(_cts.Token));
            }
            catch (Exception ex)
            {
                ShowInfoBar("HTTP IPC 端口监听失败: " + ex.Message);
            }

            var unused = EnsureConnectedAsync();
        }

        protected override void OnResizeEnd(EventArgs e)
        {
            base.OnResizeEnd(e);
            if (!_isHiddenToTray && Location.X > -10000 && Location.Y > -10000)
            {
                _lastVisibleLocation = Location;
            }
            if (_lockDesktopAspectRatio)
            {
                EnforceDesktopClientRatio();
            }
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            if (!_allowClose && e.CloseReason == CloseReason.UserClosing)
            {
                e.Cancel = true;
                HideWindowToTray(showBalloon: true);
                return;
            }

            _cts.Cancel();
            if (_trayIcon != null)
            {
                _trayIcon.Visible = false;
                _trayIcon.Dispose();
                _trayIcon = null;
                _trayMenu.Dispose();
            }
            try
            {
                _httpListener.Stop();
                _httpListener.Close();
            }
            catch
            {
            }

            try
            {
                _rdpHost.DisconnectSession();
            }
            catch
            {
            }

            base.OnFormClosing(e);
        }

        private void OnRdpLoginCompleted(object sender, EventArgs e)
        {
            _isConnecting = false;
            _rdpHost.SetInputBlocked(_watchModeEnabled);
            var sid = ChildSessionNativeMethods.TryGetChildSessionId();
            _statusMessage = string.Format(
                "桌面分身已连接并完成登录 (SessionId={0}，{1})",
                sid.HasValue ? sid.Value.ToString(CultureInfo.InvariantCulture) : "未知",
                _isHiddenToTray ? "托盘静默运行中" : "窗口显示中");
            RefreshCenterCardUi();
            var tcs = _loginTcs;
            if (tcs != null)
            {
                tcs.TrySetResult(true);
            }
        }

        private void OnRdpConnectionFailed(object sender, ChildSessionConnectionFailedEventArgs e)
        {
            _isConnecting = false;
            _statusMessage = string.Format("RDP 连接失败: {0} (Code={1})", e.Message, e.ErrorCode);
            ShowInfoBar(_statusMessage);
            RefreshCenterCardUi();
            var tcs = _loginTcs;
            if (tcs != null)
            {
                tcs.TrySetResult(false);
            }
        }

        private void OnRdpSessionDisconnected(object sender, EventArgs e)
        {
            _isConnecting = false;
            RefreshCenterCardUi();
        }

        public Task<T> RunOnUiThreadAsync<T>(Func<T> func)
        {
            if (!InvokeRequired)
            {
                return Task.FromResult(func());
            }

            var tcs = new TaskCompletionSource<T>();
            BeginInvoke(new Action(delegate
            {
                try
                {
                    tcs.TrySetResult(func());
                }
                catch (Exception ex)
                {
                    tcs.TrySetException(ex);
                }
            }));
            return tcs.Task;
        }

        public Task<bool> EnsureConnectedAsync()
        {
            return _connectionAttempt.Run(ConnectOnceAsync);
        }

        private async Task<bool> ConnectOnceAsync()
        {
            var issues = ChildSessionEnvironmentCheck.Collect();
            string enableError = null;
            try
            {
                if (!ChildSessionNativeMethods.IsChildSessionsEnabled())
                {
                    ChildSessionNativeMethods.EnableChildSessions();
                }
            }
            catch (Exception ex)
            {
                enableError = ex.GetBaseException().Message;
            }
            if (enableError != null)
            {
                await RunOnUiThreadAsync(() =>
                {
                    _isConnecting = false;
                    _statusMessage = "启用 Child Session 失败，已停止连接: " + enableError;
                    RefreshCenterCardUi();
                    return false;
                });
                return false;
            }

            var currentState = await RunOnUiThreadAsync(() => _rdpHost.ConnectedState);
            if (currentState == 1 && ChildSessionNativeMethods.TryGetChildSessionId().HasValue)
            {
                await RunOnUiThreadAsync(() =>
                {
                    RefreshCenterCardUi();
                    return true;
                });
                return true;
            }

            var loginTcs = new TaskCompletionSource<bool>();
            _loginTcs = loginTcs;

            await RunOnUiThreadAsync(() =>
            {
                _isConnecting = true;
                _statusMessage = "正在连接本地远程桌面 (Child Session)...";
                RefreshCenterCardUi();
                try
                {
                    _rdpHost.ConnectToChildSession(_desktopSize);
                }
                catch (Exception ex)
                {
                    _isConnecting = false;
                    _statusMessage = "发起连接失败: " + ex.GetBaseException().Message;
                    RefreshCenterCardUi();
                    loginTcs.TrySetResult(false);
                }
                return true;
            });

            var delayTask = Task.Delay(TimeSpan.FromSeconds(60), _cts.Token);
            var completed = await Task.WhenAny(loginTcs.Task, delayTask);
            if (completed != loginTcs.Task)
            {
                _isConnecting = false;
                var summary = ChildSessionEnvironmentCheck.BuildSummary(issues);
                _statusMessage = string.IsNullOrWhiteSpace(summary)
                    ? "连接本地远程桌面超时 (60s)"
                    : "连接本地远程桌面超时 (60s): " + summary;
                await RunOnUiThreadAsync(() =>
                {
                    RefreshCenterCardUi();
                    return false;
                });
                return false;
            }

            return await loginTcs.Task;
        }

        private async Task AcceptHttpRequestsLoopAsync(CancellationToken ct)
        {
            while (!ct.IsCancellationRequested && _httpListener.IsListening)
            {
                HttpListenerContext context;
                try
                {
                    context = await _httpListener.GetContextAsync();
                }
                catch
                {
                    if (ct.IsCancellationRequested || !_httpListener.IsListening)
                    {
                        break;
                    }
                    continue;
                }

                var ctx = context;
                var unused = Task.Run(() => HandleHttpRequestAsync(ctx), ct);
            }
        }

        private async Task HandleHttpRequestAsync(HttpListenerContext context)
        {
            var req = context.Request;
            var resp = context.Response;
            Dictionary<string, object> errorPayload = null;
            try
            {
                var path = req.Url != null && req.Url.AbsolutePath != null
                    ? req.Url.AbsolutePath.TrimEnd('/')
                    : "";
                string bodyText = "";
                if (req.HasEntityBody)
                {
                    using (var reader = new StreamReader(req.InputStream, req.ContentEncoding ?? Encoding.UTF8))
                    {
                        bodyText = await reader.ReadToEndAsync();
                    }
                }

                var root = SimpleJson.ParseObject(bodyText);

                object payload;
                if (path == "" || path == "/status")
                {
                    payload = await BuildStatusPayloadAsync();
                }
                else if (path == "/connect")
                {
                    payload = await HandleConnectAsync(root);
                }
                else if (path == "/disconnect")
                {
                    payload = await HandleDisconnectForExternalAsync(root);
                }
                else if (path == "/reconnect")
                {
                    payload = await HandleReconnectAfterExternalAsync(root);
                }
                else if (path == "/launch")
                {
                    payload = await HandleLaunchProcessAsync(root);
                }
                else if (path == "/window")
                {
                    payload = await HandleWindowControlAsync(root);
                }
                else if (path == "/logoff")
                {
                    payload = await HandleLogoffAsync();
                }
                else if (path == "/shutdown")
                {
                    payload = await HandleShutdownAsync();
                }
                else
                {
                    payload = new Dictionary<string, object>
                    {
                        { "ok", false },
                        { "error", "Unknown endpoint: " + path }
                    };
                }

                await WriteJsonResponseAsync(resp, 200, payload);
            }
            catch (Exception ex)
            {
                errorPayload = new Dictionary<string, object>
                {
                    { "ok", false },
                    { "error", ex.GetBaseException().Message },
                    { "type", ex.GetType().Name }
                };
            }
            if (errorPayload != null)
            {
                await WriteJsonResponseAsync(resp, 500, errorPayload);
            }
        }

        private async Task<object> BuildStatusPayloadAsync()
        {
            var issues = ChildSessionEnvironmentCheck.Collect();
            var issueList = new List<object>();
            foreach (var issue in issues)
            {
                issueList.Add(new Dictionary<string, object>
                {
                    { "title", issue.Title },
                    { "message", issue.Message }
                });
            }

            return await RunOnUiThreadAsync<object>(() =>
            {
                var enabled = false;
                try
                {
                    enabled = ChildSessionNativeMethods.IsChildSessionsEnabled();
                }
                catch
                {
                }
                var sessionId = ChildSessionNativeMethods.TryGetChildSessionId();
                return new Dictionary<string, object>
                {
                    { "ok", true },
                    { "enabled", enabled },
                    { "childSessionId", sessionId.HasValue ? (object)sessionId.Value : null },
                    { "connectedState", _rdpHost.ConnectedState },
                    { "isVisible", !_isHiddenToTray && Visible },
                    { "trayMode", _isHiddenToTray },
                    { "watchMode", _watchModeEnabled },
                    { "audioMuted", _audioMuted },
                    { "smartSizing", _smartSizingEnabled },
                    { "desktopWidth", _desktopSize.Width },
                    { "desktopHeight", _desktopSize.Height },
                    { "externalLeaseHolder", _externalLeaseHolder },
                    { "rdpWrapperEnabled", ChildSessionNativeMethods.IsRdpWrapperEnabled() },
                    { "environmentIssues", issueList },
                    { "statusText", _statusMessage }
                };
            });
        }

        private async Task<object> HandleConnectAsync(Dictionary<string, object> root)
        {
            if (root != null)
            {
                int w = SimpleJson.GetInt(root, "width", _desktopSize.Width);
                int h = SimpleJson.GetInt(root, "height", _desktopSize.Height);
                _desktopSize = new Size(
                    Math.Max(200, Math.Min(8192, w)),
                    Math.Max(200, Math.Min(8192, h)));
            }

            var connected = await EnsureConnectedAsync();
            var sessionId = ChildSessionNativeMethods.TryGetChildSessionId();
            return new Dictionary<string, object>
            {
                { "ok", connected && sessionId.HasValue },
                { "childSessionId", sessionId.HasValue ? (object)sessionId.Value : null },
                { "statusText", _statusMessage }
            };
        }

        private async Task<object> HandleDisconnectForExternalAsync(Dictionary<string, object> root)
        {
            string caller = SimpleJson.GetString(root, "caller", "external");
            bool disconnectRdp = SimpleJson.GetBool(root, "disconnectRdpView", true);

            _externalLeaseHolder = caller;
            if (disconnectRdp)
            {
                await RunOnUiThreadAsync(() =>
                {
                    _rdpHost.DisconnectSession();
                    _statusMessage = string.Format(
                        "已暂时释放 RDP 画面连接，供外部程序 [{0}] 连接使用（Child Session 保持存活）",
                        caller);
                    RefreshCenterCardUi();
                    return true;
                });
            }
            else
            {
                await RunOnUiThreadAsync(() =>
                {
                    _statusMessage = string.Format("已将桌面分身控制权让渡给外部程序 [{0}]", caller);
                    RefreshCenterCardUi();
                    return true;
                });
            }

            var sid = ChildSessionNativeMethods.TryGetChildSessionId();
            bool disconnected = !disconnectRdp;
            for (int attempt = 0; disconnectRdp && attempt < 40; attempt++)
            {
                if (await RunOnUiThreadAsync(() => _rdpHost.ConnectedState == 0))
                {
                    disconnected = true;
                    break;
                }
                await Task.Delay(100);
            }
            return new Dictionary<string, object>
            {
                { "ok", disconnected },
                { "childSessionId", sid.HasValue ? (object)sid.Value : null },
                { "externalLeaseHolder", _externalLeaseHolder },
                { "statusText", _statusMessage }
            };
        }

        private async Task<object> HandleReconnectAfterExternalAsync(Dictionary<string, object> root)
        {
            // 归还后的连接重试仍由借用方负责，成功前保留标记，避免监督器抢先恢复会话。
            await RunOnUiThreadAsync(() =>
            {
                _statusMessage = "外部程序已归还本地远程桌面，正在恢复常驻 RDP 连接...";
                RefreshCenterCardUi();
                _rdpHost.ReconnectToChildSession(_desktopSize);
                return true;
            });

            var connected = await EnsureConnectedAsync();
            if (connected)
            {
                _externalLeaseHolder = null;
            }
            var sid = ChildSessionNativeMethods.TryGetChildSessionId();
            return new Dictionary<string, object>
            {
                { "ok", connected },
                { "childSessionId", sid.HasValue ? (object)sid.Value : null },
                { "externalLeaseHolder", _externalLeaseHolder },
                { "statusText", _statusMessage }
            };
        }

        private async Task<object> HandleLaunchProcessAsync(Dictionary<string, object> root)
        {
            if (root == null)
            {
                throw new ArgumentException("缺少启动参数 JSON 请求体");
            }

            var exePath = SimpleJson.GetString(root, "executablePath", null);
            if (string.IsNullOrWhiteSpace(exePath))
            {
                throw new ArgumentException("executablePath 不能为空");
            }
            var arguments = SimpleJson.GetString(root, "arguments", "");
            var workingDir = SimpleJson.GetString(root, "workingDirectory", null);

            var sessionId = ChildSessionNativeMethods.TryGetChildSessionId();
            if (!sessionId.HasValue)
            {
                var connected = await EnsureConnectedAsync();
                sessionId = ChildSessionNativeMethods.TryGetChildSessionId();
                if (!connected || !sessionId.HasValue)
                {
                    throw new InvalidOperationException("当前没有可用的桌面分身会话，无法在远程桌面中启动任务。");
                }
            }

            await ChildSessionProcessLauncher.LaunchInChildSessionAsync(
                sessionId.Value,
                exePath,
                arguments,
                workingDir);

            _statusMessage = string.Format(
                "已在远程桌面 (Session {0}) 启动: {1}",
                sessionId.Value,
                Path.GetFileName(exePath));
            return new Dictionary<string, object>
            {
                { "ok", true },
                { "childSessionId", sessionId.Value },
                { "executablePath", exePath },
                { "statusText", _statusMessage }
            };
        }

        private async Task<object> HandleWindowControlAsync(Dictionary<string, object> root)
        {
            if (root == null)
            {
                return await BuildStatusPayloadAsync();
            }

            await RunOnUiThreadAsync(() =>
            {
                if (root.ContainsKey("visible") && root["visible"] != null)
                {
                    bool vis = SimpleJson.GetBool(root, "visible", true);
                    if (vis)
                    {
                        RestoreWindowFromTray();
                    }
                    else
                    {
                        HideWindowToTray(showBalloon: false);
                    }
                }

                if (root.ContainsKey("watchMode") && root["watchMode"] != null)
                {
                    _watchModeEnabled = SimpleJson.GetBool(root, "watchMode", _watchModeEnabled);
                    _rdpHost.SetInputBlocked(_watchModeEnabled);
                }

                if (root.ContainsKey("smartSizing") && root["smartSizing"] != null)
                {
                    _smartSizingEnabled = SimpleJson.GetBool(root, "smartSizing", _smartSizingEnabled);
                    _rdpHost.SetSmartSizing(_smartSizingEnabled);
                }

                if (root.ContainsKey("topmost") && root["topmost"] != null)
                {
                    TopMost = SimpleJson.GetBool(root, "topmost", TopMost);
                }

                string sc = SimpleJson.GetString(root, "shortcut", null);
                if (!string.IsNullOrEmpty(sc))
                {
                    if (string.Equals(sc, "Win+D", StringComparison.OrdinalIgnoreCase))
                    {
                        _rdpHost.SendShowDesktopShortcut();
                    }
                    else if (string.Equals(sc, "Win+Tab", StringComparison.OrdinalIgnoreCase))
                    {
                        _rdpHost.SendTaskViewShortcut();
                    }
                }

                UpdateToolbarButtonsVisualState();
                return true;
            });

            return await BuildStatusPayloadAsync();
        }

        private async Task<object> HandleLogoffAsync()
        {
            await RunOnUiThreadAsync(() =>
            {
                try
                {
                    _rdpHost.DisconnectSession();
                }
                catch
                {
                }
                return true;
            });

            var terminatedId = await Task.Run(() => ChildSessionNativeMethods.TerminateChildSession(true));
            _statusMessage = !terminatedId.HasValue
                ? "当前无活动的桌面分身会话"
                : string.Format("已注销桌面分身会话 {0}", terminatedId.Value);

            await RunOnUiThreadAsync(() =>
            {
                RefreshCenterCardUi();
                return true;
            });

            return new Dictionary<string, object>
            {
                { "ok", true },
                { "terminatedSessionId", terminatedId.HasValue ? (object)terminatedId.Value : null },
                { "statusText", _statusMessage }
            };
        }

        private async Task<object> HandleShutdownAsync()
        {
            var unused = Task.Run(async () =>
            {
                await Task.Delay(150);
                await RunOnUiThreadAsync(() =>
                {
                    _allowClose = true;
                    Close();
                    return true;
                });
            });
            return await Task.FromResult<object>(new Dictionary<string, object>
            {
                { "ok", true },
                { "message", "宿主正在退出" }
            });
        }

        private static async Task WriteJsonResponseAsync(HttpListenerResponse response, int statusCode, object payload)
        {
            var json = SimpleJson.Serialize(payload);
            var bytes = Encoding.UTF8.GetBytes(json);
            response.StatusCode = statusCode;
            response.ContentType = "application/json; charset=utf-8";
            response.ContentLength64 = bytes.Length;
            await response.OutputStream.WriteAsync(bytes, 0, bytes.Length);
            response.OutputStream.Close();
        }
    }

    /// <summary>
    /// 零外部依赖的轻量 JSON 解析与序列化工具，兼容 .NET Framework 4.x (csc.exe) 与 .NET 8。
    /// </summary>
    internal static class SimpleJson
    {
        public static Dictionary<string, object> ParseObject(string json)
        {
            var dict = new Dictionary<string, object>(StringComparer.OrdinalIgnoreCase);
            if (string.IsNullOrWhiteSpace(json))
            {
                return dict;
            }

            var pairPattern = new Regex(
                "\"(?<key>[^\"\\\\]*(?:\\\\.[^\"\\\\]*)*)\"\\s*:\\s*(?:\"(?<str>[^\"\\\\]*(?:\\\\.[^\"\\\\]*)*)\"|(?<bool>true|false)|(?<null>null)|(?<num>-?\\d+))",
                RegexOptions.IgnoreCase);
            foreach (Match m in pairPattern.Matches(json))
            {
                var key = Unescape(m.Groups["key"].Value);
                if (m.Groups["str"].Success)
                {
                    dict[key] = Unescape(m.Groups["str"].Value);
                }
                else if (m.Groups["bool"].Success)
                {
                    dict[key] = string.Equals(m.Groups["bool"].Value, "true", StringComparison.OrdinalIgnoreCase);
                }
                else if (m.Groups["null"].Success)
                {
                    dict[key] = null;
                }
                else if (m.Groups["num"].Success)
                {
                    int v;
                    if (int.TryParse(m.Groups["num"].Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out v))
                    {
                        dict[key] = v;
                    }
                }
            }
            return dict;
        }

        public static string GetString(Dictionary<string, object> dict, string key, string defaultValue)
        {
            if (dict == null || !dict.ContainsKey(key) || dict[key] == null)
            {
                return defaultValue;
            }
            return Convert.ToString(dict[key], CultureInfo.InvariantCulture);
        }

        public static int GetInt(Dictionary<string, object> dict, string key, int defaultValue)
        {
            if (dict == null || !dict.ContainsKey(key) || dict[key] == null)
            {
                return defaultValue;
            }
            int v;
            if (int.TryParse(Convert.ToString(dict[key], CultureInfo.InvariantCulture), out v))
            {
                return v;
            }
            return defaultValue;
        }

        public static bool GetBool(Dictionary<string, object> dict, string key, bool defaultValue)
        {
            if (dict == null || !dict.ContainsKey(key) || dict[key] == null)
            {
                return defaultValue;
            }
            if (dict[key] is bool)
            {
                return (bool)dict[key];
            }
            bool b;
            if (bool.TryParse(Convert.ToString(dict[key], CultureInfo.InvariantCulture), out b))
            {
                return b;
            }
            return defaultValue;
        }

        private static string Unescape(string s)
        {
            if (string.IsNullOrEmpty(s)) return string.Empty;
            var sb = new StringBuilder(s.Length);
            for (int i = 0; i < s.Length; i++)
            {
                char c = s[i];
                if (c == '\\' && i + 1 < s.Length)
                {
                    char next = s[++i];
                    switch (next)
                    {
                        case '"': sb.Append('"'); break;
                        case '\\': sb.Append('\\'); break;
                        case '/': sb.Append('/'); break;
                        case 'b': sb.Append('\b'); break;
                        case 'f': sb.Append('\f'); break;
                        case 'n': sb.Append('\n'); break;
                        case 'r': sb.Append('\r'); break;
                        case 't': sb.Append('\t'); break;
                        case 'u':
                            if (i + 4 < s.Length)
                            {
                                string hex = s.Substring(i + 1, 4);
                                int code;
                                if (int.TryParse(hex, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out code))
                                {
                                    sb.Append((char)code);
                                    i += 4;
                                }
                            }
                            break;
                        default: sb.Append(next); break;
                    }
                }
                else
                {
                    sb.Append(c);
                }
            }
            return sb.ToString();
        }

        public static string Serialize(object obj)
        {
            if (obj == null) return "null";
            if (obj is bool) return ((bool)obj) ? "true" : "false";
            if (obj is int || obj is uint || obj is long || obj is double || obj is float)
            {
                return Convert.ToString(obj, CultureInfo.InvariantCulture);
            }
            var str = obj as string;
            if (str != null)
            {
                return "\"" + Escape(str) + "\"";
            }
            var dict = obj as IDictionary<string, object>;
            if (dict != null)
            {
                var sb = new StringBuilder();
                sb.Append('{');
                bool first = true;
                foreach (var kv in dict)
                {
                    if (!first) sb.Append(',');
                    first = false;
                    sb.Append('"').Append(Escape(kv.Key)).Append("\":").Append(Serialize(kv.Value));
                }
                sb.Append('}');
                return sb.ToString();
            }
            var enumerable = obj as System.Collections.IEnumerable;
            if (enumerable != null)
            {
                var sb = new StringBuilder();
                sb.Append('[');
                bool first = true;
                foreach (var item in enumerable)
                {
                    if (!first) sb.Append(',');
                    first = false;
                    sb.Append(Serialize(item));
                }
                sb.Append(']');
                return sb.ToString();
            }
            return "\"" + Escape(Convert.ToString(obj, CultureInfo.InvariantCulture)) + "\"";
        }

        private static string Escape(string s)
        {
            if (string.IsNullOrEmpty(s)) return string.Empty;
            var sb = new StringBuilder(s.Length + 8);
            foreach (char c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\b': sb.Append("\\b"); break;
                    case '\f': sb.Append("\\f"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < ' ')
                        {
                            sb.AppendFormat(CultureInfo.InvariantCulture, "\\u{0:X4}", (int)c);
                        }
                        else
                        {
                            sb.Append(c);
                        }
                        break;
                }
            }
            return sb.ToString();
        }
    }
}
