using System;
using System.Globalization;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Windows.Forms;
using BetterGenshinImpact.Service.ChildSession;
using DrawingSize = System.Drawing.Size;

namespace BetterGenshinImpact.View.Controls.ChildSession
{
    internal sealed class RdpActiveXHost : AxHost
    {
        // Windows 10+ 自带的非脚本化 RDP ActiveX 控件（MsRdpClient10）。
        private const string RdpClientClsid = "A0C63C30-F08D-4AB4-907C-34905D770C7D";
        private const short VariantFalse = 0;
        private const short VariantTrue = -1;
        private const int RedirectAudioToClient = 0;
        private const int DisableRemoteAudio = 2;
        private static readonly TimeSpan ReconnectDelay = TimeSpan.FromSeconds(1);

        private static readonly RemoteKey LeftWindowsKey = new RemoteKey(0x5B, true);
        private static readonly RemoteKey DKey = new RemoteKey(0x20, false);
        private static readonly RemoteKey TabKey = new RemoteKey(0x0F, false);
        private ConnectionPointCookie _eventCookie;
        private RdpEventSink _eventSink;
        private bool _connectionAttemptInProgress;
        private bool _connectionFailureReported;
        private ChildSessionConnectionFailedEventArgs _lastConnectionDiagnostic;
        private bool _disconnectRequested;
        private bool _sendSystemShortcutsToRemote = true;
        private bool _audioMuted;
        private DrawingSize? _pendingReconnectDesktopSize;
        private bool _smartSizingEnabled = true;
        private bool _inputBlocked;
        private DrawingSize _remoteDesktopSize;

        internal DrawingSize RemoteDesktopSize { get { return _remoteDesktopSize; } }

        internal event EventHandler<ChildSessionConnectionFailedEventArgs> ConnectionFailed;

        internal event EventHandler LoginCompleted;

        internal event EventHandler SessionDisconnected;

        internal ChildSessionConnectionFailedEventArgs LastConnectionDiagnostic
        {
            get { return _lastConnectionDiagnostic; }
        }

        internal RdpActiveXHost()
            : base(RdpClientClsid)
        {
        }

        internal void FitToWorkspace()
        {
            if (Parent == null) return;

            var area = Parent.ClientSize;
            var size = area;
            if (_smartSizingEnabled && _remoteDesktopSize.Width > 0 && _remoteDesktopSize.Height > 0)
            {
                double scale = Math.Min((double)area.Width / _remoteDesktopSize.Width,
                    (double)area.Height / _remoteDesktopSize.Height);
                size = new DrawingSize((int)Math.Round(_remoteDesktopSize.Width * scale),
                    (int)Math.Round(_remoteDesktopSize.Height * scale));
            }
            SetBounds((area.Width - size.Width) / 2, (area.Height - size.Height) / 2, size.Width, size.Height);
        }

        private void UpdateRemoteDesktopSize(int width, int height)
        {
            if (width <= 0 || height <= 0) return;

            _remoteDesktopSize = new DrawingSize(width, height);
            FitToWorkspace();
        }

        internal int ConnectedState
        {
            get
            {
                if (!IsHandleCreated)
                {
                    return 0;
                }

                try
                {
                    return Convert.ToInt32(
                        GetComProperty(GetRequiredOcx(), "Connected"),
                        CultureInfo.InvariantCulture);
                }
                catch
                {
                    return 0;
                }
            }
        }

        private static int ClampDimension(int value, int min, int max)
        {
            if (value < min) return min;
            if (value > max) return max;
            return value;
        }

        internal void ConnectToChildSession(DrawingSize desktopSize)
        {
            if (ConnectedState != 0)
            {
                return;
            }

            ChildSessionNativeMethods.ClearRdpInputWindowCache(Handle);
            var client = GetRequiredOcx();
            var width = ClampDimension(desktopSize.Width, 200, 8192);
            var height = ClampDimension(desktopSize.Height, 200, 8192);
            UpdateRemoteDesktopSize(width, height);

            SetComProperty(client, "Server", "localhost");
            SetComProperty(client, "DesktopWidth", width);
            SetComProperty(client, "DesktopHeight", height);
            SetComProperty(client, "ColorDepth", 32);
            SetComProperty(client, "ConnectingText", "正在创建 automass桌面分身...");
            SetComProperty(client, "DisconnectedText", "automass桌面分身已断开");

            var securedSettings = GetComProperty(client, "SecuredSettings2");
            if (securedSettings == null)
            {
                throw new COMException("RDP ActiveX 未返回 SecuredSettings2。");
            }
            RunComStep("设置系统组合键发送位置", delegate
            {
                SetComProperty(
                    securedSettings,
                    "KeyboardHookMode",
                    _sendSystemShortcutsToRemote ? 1 : 0);
            });
            RunComStep("设置远程音频重定向", delegate
            {
                SetComProperty(
                    securedSettings,
                    "AudioRedirectionMode",
                    _audioMuted ? DisableRemoteAudio : RedirectAudioToClient);
            });

            var advancedSettings = GetComProperty(client, "AdvancedSettings7");
            if (advancedSettings == null)
            {
                throw new COMException("RDP ActiveX 未返回 AdvancedSettings7。");
            }
            RunComStep("设置 RDP 连接端口", delegate
            {
                SetComProperty(
                    advancedSettings,
                    "RDPPort",
                    ChildSessionNativeMethods.GetConfiguredRdpPort());
            });
            RunComStep("启用 CredSSP", delegate
            {
                SetComProperty(advancedSettings, "EnableCredSspSupport", true);
            });
            RunComStep("启用远程 Windows 键", delegate
            {
                SetComProperty(advancedSettings, "EnableWindowsKey", 1);
            });
            RunComStep("设置显示缩放", delegate
            {
                SetComProperty(advancedSettings, "SmartSizing", _smartSizingEnabled);
            });

            object connectToChildSession = true;
            RunComStep("设置 ConnectToChildSession", delegate
            {
                var extendedSettings = (IMsRdpExtendedSettings)client;
                TrySetExtendedProperty(extendedSettings, "EnableZoom", true);
                extendedSettings.set_Property("ConnectToChildSession", ref connectToChildSession);
            });

            _connectionAttemptInProgress = true;
            _connectionFailureReported = false;
            _lastConnectionDiagnostic = null;
            _disconnectRequested = false;
            try
            {
                RunComStep("调用 RDP Connect()", delegate { InvokeComMethod(client, "Connect"); });
            }
            catch
            {
                _connectionAttemptInProgress = false;
                throw;
            }
        }

        internal void SendShowDesktopShortcut()
        {
            KeyStroke[] strokes = new KeyStroke[]
            {
                new KeyStroke(LeftWindowsKey, false),
                new KeyStroke(DKey, false),
                new KeyStroke(DKey, true),
                new KeyStroke(LeftWindowsKey, true)
            };

            SendShortcut(strokes, "Win+D");
        }

        internal void SendTaskViewShortcut()
        {
            KeyStroke[] strokes = new KeyStroke[]
            {
                new KeyStroke(LeftWindowsKey, false),
                new KeyStroke(TabKey, false),
                new KeyStroke(TabKey, true),
                new KeyStroke(LeftWindowsKey, true)
            };

            SendShortcut(strokes, "Win+Tab");
        }

        internal void SetSmartSizing(bool enabled)
        {
            _smartSizingEnabled = enabled;
            FitToWorkspace();
            if (!IsHandleCreated)
            {
                return;
            }

            var advancedSettings = GetComProperty(GetRequiredOcx(), "AdvancedSettings7");
            if (advancedSettings == null)
            {
                throw new COMException("RDP ActiveX 未返回 AdvancedSettings7。");
            }
            RunComStep("设置显示缩放", delegate
            {
                SetComProperty(advancedSettings, "SmartSizing", enabled);
            });
        }

        internal void SetSendSystemShortcutsToRemote(bool enabled)
        {
            _sendSystemShortcutsToRemote = enabled;
        }

        internal void SetAudioMuted(bool muted)
        {
            _audioMuted = muted;
        }

        internal void SetInputBlocked(bool blocked)
        {
            _inputBlocked = blocked;
            if (!IsHandleCreated)
            {
                return;
            }

            ChildSessionNativeMethods.SetRdpInputWindowEnabled(Handle, !blocked);
        }

        internal void ReconnectToChildSession(DrawingSize desktopSize)
        {
            if (_disconnectRequested || _pendingReconnectDesktopSize.HasValue)
            {
                _pendingReconnectDesktopSize = desktopSize;
                return;
            }

            if (ConnectedState == 0)
            {
                ConnectToChildSession(desktopSize);
                return;
            }

            _pendingReconnectDesktopSize = desktopSize;
            try
            {
                if (!DisconnectCore())
                {
                    _pendingReconnectDesktopSize = null;
                    ConnectToChildSession(desktopSize);
                }
            }
            catch
            {
                _pendingReconnectDesktopSize = null;
                throw;
            }
        }

        internal void DisconnectSession()
        {
            _pendingReconnectDesktopSize = null;
            DisconnectCore();
        }

        private bool DisconnectCore()
        {
            if (IsHandleCreated)
            {
                ChildSessionNativeMethods.ClearRdpInputWindowCache(Handle);
            }

            if (ConnectedState == 0)
            {
                return false;
            }

            _disconnectRequested = true;
            try
            {
                InvokeComMethod(GetRequiredOcx(), "Disconnect");
                return true;
            }
            catch
            {
                _disconnectRequested = false;
                throw;
            }
        }

        internal bool IsInputWindowFocused()
        {
            return ConnectedState == 1
                   && ChildSessionNativeMethods.IsRdpInputWindowFocused(Handle);
        }

        protected override void OnHandleDestroyed(EventArgs e)
        {
            if (IsHandleCreated)
            {
                ChildSessionNativeMethods.ClearRdpInputWindowCache(Handle);
            }

            base.OnHandleDestroyed(e);
        }

        protected override void CreateSink()
        {
            base.CreateSink();

            _eventSink = new RdpEventSink(this);
            _eventCookie = new ConnectionPointCookie(
                GetOcx(),
                _eventSink,
                typeof(IMsTscAxEvents));
        }

        protected override void DetachSink()
        {
            try
            {
                if (_eventCookie != null)
                {
                    _eventCookie.Disconnect();
                }
                _eventCookie = null;
                _eventSink = null;
            }
            finally
            {
                base.DetachSink();
            }
        }

        private void SendShortcut(KeyStroke[] strokes, string displayName)
        {
            if (ConnectedState != 1)
            {
                throw new InvalidOperationException(
                    string.Format("桌面分身尚未完全连接，无法发送 {0}。", displayName));
            }

            if (_inputBlocked)
            {
                ChildSessionNativeMethods.SetRdpInputWindowEnabled(Handle, true);
            }

            try
            {
                if (!ChildSessionNativeMethods.TryFocusRdpInputWindow(Handle))
                {
                    throw new InvalidOperationException("无法将键盘焦点切换到桌面分身。");
                }

                RunComStep(
                    string.Format("向 Child Session 发送 {0}", displayName),
                    delegate { SendKeyStrokes(strokes); });
            }
            finally
            {
                if (_inputBlocked)
                {
                    ChildSessionNativeMethods.SetRdpInputWindowEnabled(Handle, false);
                }
            }
        }

        private void SendKeyStrokes(KeyStroke[] strokes)
        {
            var keyUpStates = new short[strokes.Length];
            var keyData = new int[strokes.Length];

            for (var index = 0; index < strokes.Length; index++)
            {
                var stroke = strokes[index];
                keyUpStates[index] = stroke.IsKeyUp ? VariantTrue : VariantFalse;
                keyData[index] = CreateRdpScanCode(stroke.Key);
            }

            var nonScriptableClient = (IMsRdpClientNonScriptable)GetRequiredOcx();
            nonScriptableClient.SendKeys(
                strokes.Length,
                ref keyUpStates[0],
                ref keyData[0]);
        }

        private static int CreateRdpScanCode(RemoteKey key)
        {
            const int extendedScanCodeFlag = 0x0100;
            return key.ScanCode | (key.IsExtended ? extendedScanCodeFlag : 0);
        }

        private void OnLoginComplete()
        {
            _connectionAttemptInProgress = false;
            _connectionFailureReported = false;
            _lastConnectionDiagnostic = null;
            var handler = LoginCompleted;
            if (handler != null)
            {
                handler(this, EventArgs.Empty);
            }
        }

        private void OnDisconnected(int disconnectReason)
        {
            var failedWhileConnecting = _connectionAttemptInProgress;
            _connectionAttemptInProgress = false;

            if (_disconnectRequested)
            {
                _disconnectRequested = false;
                if (_pendingReconnectDesktopSize.HasValue && !IsDisposed && !Disposing)
                {
                    try
                    {
                        BeginInvoke(new Action(ConnectPendingReconnect));
                    }
                    catch (InvalidOperationException)
                    {
                        _pendingReconnectDesktopSize = null;
                    }
                }
                else
                {
                    var discHandler = SessionDisconnected;
                    if (discHandler != null)
                    {
                        discHandler(this, EventArgs.Empty);
                    }
                }
                return;
            }

            var extendedDisconnectReason = TryGetExtendedDisconnectReason();
            if (_connectionFailureReported
                || (!failedWhileConnecting
                    && IsNormalDisconnect(disconnectReason, extendedDisconnectReason)))
            {
                var discHandler = SessionDisconnected;
                if (discHandler != null)
                {
                    discHandler(this, EventArgs.Empty);
                }
                return;
            }

            var errorDescription = TryGetErrorDescription(
                disconnectReason,
                extendedDisconnectReason);
            var failureTitle = failedWhileConnecting
                ? "RDP 连接失败"
                : "RDP 连接意外断开";
            var message = string.IsNullOrWhiteSpace(errorDescription)
                ? string.Format(
                    "{0}。\n\n断开原因：{1}\n扩展原因：{2}",
                    failureTitle,
                    FormatErrorCode(disconnectReason),
                    FormatErrorCode(extendedDisconnectReason))
                : string.Format(
                    "{0}：{1}\n\n断开原因：{2}\n扩展原因：{3}",
                    failureTitle,
                    errorDescription,
                    FormatErrorCode(disconnectReason),
                    FormatErrorCode(extendedDisconnectReason));

            ReportConnectionFailure(
                message,
                disconnectReason,
                extendedDisconnectReason);
        }

        private async void ConnectPendingReconnect()
        {
            await Task.Delay(ReconnectDelay);

            var desktopSize = _pendingReconnectDesktopSize;
            _pendingReconnectDesktopSize = null;
            if (!desktopSize.HasValue || IsDisposed || Disposing)
            {
                return;
            }

            try
            {
                ConnectToChildSession(desktopSize.Value);
            }
            catch (Exception exception)
            {
                if (exception is COMException ||
                    exception is TargetInvocationException ||
                    exception is InvalidOperationException)
                {
                    var actualException = exception.GetBaseException();
                    var comException = actualException as COMException;
                    var errorCode = comException != null ? comException.ErrorCode : 0;
                    ReportConnectionFailure(
                        string.Format("RDP 自动重新连接失败：{0}", actualException.Message),
                        errorCode);
                    return;
                }
                throw;
            }
        }

        private void OnFatalError(int errorCode)
        {
            _connectionAttemptInProgress = false;
            if (_disconnectRequested)
            {
                return;
            }

            ReportConnectionFailure(
                string.Format(
                    "RDP 客户端发生致命错误：{0}\n\n错误代码：{1}",
                    GetFatalErrorDescription(errorCode),
                    FormatErrorCode(errorCode)),
                errorCode);
        }

        private void OnLogonError(int errorCode)
        {
            if (_disconnectRequested)
            {
                return;
            }

            var message = string.Format(
                "RDP 登录阶段：{0}\n\n错误代码：{1}",
                GetLogonErrorDescription(errorCode),
                FormatErrorCode(errorCode));
            if (IsNonTerminalLogonEvent(errorCode))
            {
                _lastConnectionDiagnostic =
                    new ChildSessionConnectionFailedEventArgs(message, errorCode);
                return;
            }

            _connectionAttemptInProgress = false;
            ReportConnectionFailure(
                message.Replace("RDP 登录阶段：", "RDP 登录失败："),
                errorCode);
        }

        private int TryGetExtendedDisconnectReason()
        {
            try
            {
                return Convert.ToInt32(
                    GetComProperty(GetRequiredOcx(), "ExtendedDisconnectReason"),
                    CultureInfo.InvariantCulture);
            }
            catch (Exception exception)
            {
                if (exception is COMException ||
                    exception is TargetInvocationException ||
                    exception is InvalidOperationException)
                {
                    return 0;
                }
                throw;
            }
        }

        private string TryGetErrorDescription(
            int disconnectReason,
            int extendedDisconnectReason)
        {
            try
            {
                return Convert.ToString(
                    InvokeComMethod(
                        GetRequiredOcx(),
                        "GetErrorDescription",
                        disconnectReason,
                        extendedDisconnectReason),
                    CultureInfo.CurrentCulture);
            }
            catch (Exception exception)
            {
                if (exception is COMException ||
                    exception is TargetInvocationException ||
                    exception is InvalidOperationException)
                {
                    return null;
                }
                throw;
            }
        }

        private void ReportConnectionFailure(
            string message,
            int errorCode,
            int? extendedErrorCode = null)
        {
            if (_connectionFailureReported)
            {
                return;
            }

            _connectionFailureReported = true;
            var handler = ConnectionFailed;
            if (handler != null)
            {
                handler(
                    this,
                    new ChildSessionConnectionFailedEventArgs(
                        message,
                        errorCode,
                        extendedErrorCode));
            }
        }

        private static bool IsNormalDisconnect(
            int disconnectReason,
            int extendedDisconnectReason)
        {
            return (disconnectReason == 1 || disconnectReason == 2 || disconnectReason == 3)
                   && (extendedDisconnectReason == 0 || extendedDisconnectReason == 1 || extendedDisconnectReason == 2);
        }

        private static string FormatErrorCode(int errorCode)
        {
            return string.Format("{0} (0x{1:X8})", errorCode, unchecked((uint)errorCode));
        }

        private static string GetFatalErrorDescription(int errorCode)
        {
            switch (errorCode)
            {
                case 0: return "发生未知错误。";
                case 1: return "发生内部错误（1）。";
                case 2: return "内存不足。";
                case 3: return "无法创建 RDP 窗口。";
                case 4: return "发生内部错误（2）。";
                case 5: return "RDP 客户端进入了无效状态。";
                case 6: return "发生内部错误（4）。";
                case 7: return "建立客户端连接时发生不可恢复的错误。";
                case 100: return "Windows 套接字初始化失败。";
                default: return "发生未识别的致命错误。";
            }
        }

        private static string GetLogonErrorDescription(int errorCode)
        {
            switch (errorCode)
            {
                case -7: return "Winlogon 正在显示“拒绝断开现有会话”对话框。";
                case -6: return "Winlogon 正在显示“无权限”对话框。";
                case -5: return "Winlogon 正在显示会话争用选项。";
                case -4: return "Winlogon 正在显示重新连接选项。";
                case -3: return "Winlogon 已静默终止登录。";
                case -1: return "访问被拒绝。";
                case 0: return "登录凭据无效。";
                case 1: return "密码已过期，必须先修改密码。";
                case 2: return "登录或登录后的处理发生错误。";
                case 3: return "RDP 客户端正在显示登录警告。";
                case unchecked((int)0xC000006D): return "用户名或身份验证信息无效。";
                case unchecked((int)0xC000006E): return "身份验证受到用户账户限制。";
                case unchecked((int)0xC0000224): return "密码已过期，必须先修改密码。";
                default: return "登录阶段发生未识别的错误或事件。";
            }
        }

        private static bool IsNonTerminalLogonEvent(int errorCode)
        {
            return errorCode == -5 || errorCode == -4 || errorCode == -2 || errorCode == 3;
        }

        private object GetRequiredOcx()
        {
            if (!IsHandleCreated)
            {
                var unused = Handle;
            }

            var ocx = GetOcx();
            if (ocx == null)
            {
                throw new InvalidOperationException(
                    "RDP ActiveX 控件尚未完成初始化，无法访问 COM 实例。");
            }
            return ocx;
        }

        private static object GetComProperty(object target, string propertyName)
        {
            return target.GetType().InvokeMember(
                propertyName,
                BindingFlags.GetProperty,
                null,
                target,
                null,
                CultureInfo.InvariantCulture);
        }

        private static void SetComProperty(object target, string propertyName, object value)
        {
            target.GetType().InvokeMember(
                propertyName,
                BindingFlags.SetProperty,
                null,
                target,
                new object[] { value },
                CultureInfo.InvariantCulture);
        }

        private static void TrySetExtendedProperty(
            IMsRdpExtendedSettings extendedSettings,
            string propertyName,
            object value)
        {
            try
            {
                extendedSettings.set_Property(propertyName, ref value);
            }
            catch (COMException)
            {
            }
        }

        private static object InvokeComMethod(object target, string methodName, params object[] args)
        {
            return target.GetType().InvokeMember(
                methodName,
                BindingFlags.InvokeMethod,
                null,
                target,
                args,
                CultureInfo.InvariantCulture);
        }

        private static void RunComStep(string stepName, Action action)
        {
            try
            {
                action();
            }
            catch (Exception exception)
            {
                var actualException = exception.GetBaseException();
                var comException = actualException as COMException;
                if (comException != null)
                {
                    throw new COMException(
                        string.Format("{0}失败：{1}", stepName, comException.Message),
                        comException.ErrorCode);
                }

                throw;
            }
        }

        [ComImport]
        [Guid("336D5562-EFA8-482E-8CB3-C5C0FC7A7DB6")]
        [InterfaceType(ComInterfaceType.InterfaceIsIDispatch)]
        [TypeLibType(TypeLibTypeFlags.FDispatchable)]
        private interface IMsTscAxEvents
        {
            [DispId(1)]
            void OnConnecting();

            [DispId(2)]
            void OnConnected();

            [DispId(3)]
            void OnLoginComplete();

            [DispId(4)]
            void OnDisconnected([In] int disconnectReason);

            [DispId(5)]
            void OnEnterFullScreenMode();

            [DispId(6)]
            void OnLeaveFullScreenMode();

            [DispId(7)]
            void OnChannelReceivedData(
                [In, MarshalAs(UnmanagedType.BStr)] string channelName,
                [In, MarshalAs(UnmanagedType.BStr)] string data);

            [DispId(8)]
            void OnRequestGoFullScreen();

            [DispId(9)]
            void OnRequestLeaveFullScreen();

            [DispId(10)]
            void OnFatalError([In] int errorCode);

            [DispId(11)]
            void OnWarning([In] int warningCode);

            [DispId(12)]
            void OnRemoteDesktopSizeChange([In] int width, [In] int height);

            [DispId(13)]
            void OnIdleTimeoutNotification();

            [DispId(14)]
            void OnRequestContainerMinimize();

            [DispId(15)]
            void OnConfirmClose([Out] out bool allowClose);

            [DispId(16)]
            void OnReceivedTSPublicKey(
                [In, MarshalAs(UnmanagedType.BStr)] string publicKey,
                [Out] out bool continueLogon);

            [DispId(17)]
            void OnAutoReconnecting(
                [In] int disconnectReason,
                [In] int attemptCount,
                [Out] out AutoReconnectContinueState continueStatus);

            [DispId(18)]
            void OnAuthenticationWarningDisplayed();

            [DispId(19)]
            void OnAuthenticationWarningDismissed();

            [DispId(20)]
            void OnRemoteProgramResult(
                [In, MarshalAs(UnmanagedType.BStr)] string remoteProgram,
                [In] RemoteProgramResult error,
                [In] bool isExecutable);

            [DispId(21)]
            void OnRemoteProgramDisplayed(
                [In] bool displayed,
                [In] uint displayInformation);

            [DispId(29)]
            void OnRemoteWindowDisplayed(
                [In] bool displayed,
                [In] ref RemotableHandle windowHandle,
                [In] RemoteWindowDisplayedAttribute windowAttribute);

            [DispId(22)]
            void OnLogonError([In] int errorCode);

            [DispId(23)]
            void OnFocusReleased([In] int direction);

            [DispId(24)]
            void OnUserNameAcquired(
                [In, MarshalAs(UnmanagedType.BStr)] string userName);

            [DispId(26)]
            void OnMouseInputModeChanged([In] bool isRelativeMouseMode);

            [DispId(28)]
            void OnServiceMessageReceived(
                [In, MarshalAs(UnmanagedType.BStr)] string serviceMessage);

            [DispId(30)]
            void OnConnectionBarPullDown();

            [DispId(32)]
            void OnNetworkStatusChanged(
                [In] uint qualityLevel,
                [In] int bandwidth,
                [In] int roundTripTime);

            [DispId(35)]
            void OnDevicesButtonPressed();

            [DispId(33)]
            void OnAutoReconnected();

            [DispId(34)]
            void OnAutoReconnecting2(
                [In] int disconnectReason,
                [In] bool networkAvailable,
                [In] int attemptCount,
                [In] int maxAttemptCount);
        }

        [ComVisible(true)]
        [ClassInterface(ClassInterfaceType.None)]
        private sealed class RdpEventSink : IMsTscAxEvents
        {
            private readonly RdpActiveXHost _owner;

            public RdpEventSink(RdpActiveXHost owner)
            {
                _owner = owner;
            }

            public void OnConnecting() { }

            public void OnConnected() { }

            public void OnLoginComplete()
            {
                _owner.OnLoginComplete();
            }

            public void OnDisconnected(int disconnectReason)
            {
                _owner.OnDisconnected(disconnectReason);
            }

            public void OnEnterFullScreenMode() { }

            public void OnLeaveFullScreenMode() { }

            public void OnChannelReceivedData(string channelName, string data) { }

            public void OnRequestGoFullScreen() { }

            public void OnRequestLeaveFullScreen() { }

            public void OnFatalError(int errorCode)
            {
                _owner.OnFatalError(errorCode);
            }

            public void OnWarning(int warningCode) { }

            public void OnRemoteDesktopSizeChange(int width, int height)
            {
                _owner.UpdateRemoteDesktopSize(width, height);
            }

            public void OnIdleTimeoutNotification() { }

            public void OnRequestContainerMinimize() { }

            public void OnConfirmClose(out bool allowClose)
            {
                allowClose = true;
            }

            public void OnReceivedTSPublicKey(string publicKey, out bool continueLogon)
            {
                continueLogon = true;
            }

            public void OnAutoReconnecting(
                int disconnectReason,
                int attemptCount,
                out AutoReconnectContinueState continueStatus)
            {
                continueStatus = AutoReconnectContinueState.Automatic;
            }

            public void OnAuthenticationWarningDisplayed() { }

            public void OnAuthenticationWarningDismissed() { }

            public void OnRemoteProgramResult(
                string remoteProgram,
                RemoteProgramResult error,
                bool isExecutable) { }

            public void OnRemoteProgramDisplayed(
                bool displayed,
                uint displayInformation) { }

            public void OnRemoteWindowDisplayed(
                bool displayed,
                ref RemotableHandle windowHandle,
                RemoteWindowDisplayedAttribute windowAttribute) { }

            public void OnLogonError(int errorCode)
            {
                _owner.OnLogonError(errorCode);
            }

            public void OnFocusReleased(int direction) { }

            public void OnUserNameAcquired(string userName) { }

            public void OnMouseInputModeChanged(bool isRelativeMouseMode) { }

            public void OnServiceMessageReceived(string serviceMessage) { }

            public void OnConnectionBarPullDown() { }

            public void OnNetworkStatusChanged(
                uint qualityLevel,
                int bandwidth,
                int roundTripTime) { }

            public void OnDevicesButtonPressed() { }

            public void OnAutoReconnected()
            {
                _owner.OnLoginComplete();
            }

            public void OnAutoReconnecting2(
                int disconnectReason,
                bool networkAvailable,
                int attemptCount,
                int maxAttemptCount) { }
        }

        private enum AutoReconnectContinueState
        {
            Automatic,
            Stop,
            Manual
        }

        private enum RemoteProgramResult
        {
            Ok,
            Locked,
            ProtocolError,
            NotInWhitelist,
            NetworkPathDenied,
            FileNotFound,
            Failure,
            HookNotLoaded
        }

        private enum RemoteWindowDisplayedAttribute
        {
            None,
            WindowDisplayed,
            ShellIconDisplayed
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct RemotableHandle
        {
            internal int Context;
            internal RemotableHandleUnion Value;
        }

        [StructLayout(LayoutKind.Explicit)]
        private struct RemotableHandleUnion
        {
            [FieldOffset(0)]
            internal int InProcessHandle;

            [FieldOffset(0)]
            internal int RemoteHandle;
        }

        [ComImport]
        [Guid("302D8188-0052-4807-806A-362B628F9AC5")]
        [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IMsRdpExtendedSettings
        {
            void set_Property(
                [In, MarshalAs(UnmanagedType.BStr)] string propertyName,
                [In, MarshalAs(UnmanagedType.Struct)] ref object value);

            [return: MarshalAs(UnmanagedType.Struct)]
            object get_Property([In, MarshalAs(UnmanagedType.BStr)] string propertyName);
        }

        [ComImport]
        [Guid("2F079C4C-87B2-4AFD-97AB-20CDB43038AE")]
        [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IMsRdpClientNonScriptable
        {
            void put_ClearTextPassword([In, MarshalAs(UnmanagedType.BStr)] string value);

            void put_PortablePassword([In, MarshalAs(UnmanagedType.BStr)] string value);

            [return: MarshalAs(UnmanagedType.BStr)]
            string get_PortablePassword();

            void put_PortableSalt([In, MarshalAs(UnmanagedType.BStr)] string value);

            [return: MarshalAs(UnmanagedType.BStr)]
            string get_PortableSalt();

            void put_BinaryPassword([In, MarshalAs(UnmanagedType.BStr)] string value);

            [return: MarshalAs(UnmanagedType.BStr)]
            string get_BinaryPassword();

            void put_BinarySalt([In, MarshalAs(UnmanagedType.BStr)] string value);

            [return: MarshalAs(UnmanagedType.BStr)]
            string get_BinarySalt();

            void ResetPassword();

            void NotifyRedirectDeviceChange(UIntPtr wParam, IntPtr lParam);

            void SendKeys(
                int numKeys,
                [In] ref short keyUpStates,
                [In] ref int keyData);
        }

        private struct RemoteKey
        {
            public readonly int ScanCode;
            public readonly bool IsExtended;

            public RemoteKey(int scanCode, bool isExtended)
            {
                ScanCode = scanCode;
                IsExtended = isExtended;
            }
        }

        private struct KeyStroke
        {
            public readonly RemoteKey Key;
            public readonly bool IsKeyUp;

            public KeyStroke(RemoteKey key, bool isKeyUp)
            {
                Key = key;
                IsKeyUp = isKeyUp;
            }
        }
    }
}
