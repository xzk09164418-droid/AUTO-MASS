// 独立后端启动代理：不依赖 Node 生命周期，不承载业务逻辑。
using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.IO.Pipes;
using System.Linq;
using System.Net;
using System.Net.NetworkInformation;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Web.Script.Serialization;

namespace AutoMas.BackendAgent
{
    internal static class Program
    {
        private static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = 1048576 };
        private static readonly UTF8Encoding Utf8 = new UTF8Encoding(false);
        private static readonly object OutputLock = new object();

        private static int Main(string[] args)
        {
            try
            {
                if (args.Length == 2 && args[0] == "--worker") return RunWorker(args[1]);
                // winexe 没有控制台，不能调用 SetConsoleOutputCP；直接包装继承的标准句柄。
                Console.SetOut(new StreamWriter(Console.OpenStandardOutput(), Utf8) { AutoFlush = true });
                Console.SetError(new StreamWriter(Console.OpenStandardError(), Utf8) { AutoFlush = true });
                if (args.Length < 4 || args[0] != "--python" || args[2] != "--")
                    throw new ArgumentException("Expected --python <executable> -- <backend arguments>");
                return RunBridge(Path.GetFullPath(args[1]), args.Skip(3).ToArray());
            }
            catch (Exception error)
            {
                Console.Error.WriteLine(DateTime.UtcNow.AddHours(8).ToString("yyyy-MM-dd HH:mm:ss.fff") +
                    " | ERROR    | 后端启动代理 | " + error.GetBaseException().Message);
                return 1;
            }
        }

        // 非标准配置继续交给原有 Python 校验和迁移，代理只处理完整、有效的启动提示。
        private static Dictionary<string, object> ReadDesktopHints(string root)
        {
            try
            {
                var config = Json.Deserialize<Dictionary<string, object>>(File.ReadAllText(Path.Combine(root, "config", "Config.json"), Utf8));
                if (config == null) return null;
                var desktop = config["ChildSession"] as Dictionary<string, object>;
                if (desktop == null || !(desktop["Enabled"] is bool) || !(bool)desktop["Enabled"] ||
                    !(desktop["HostPort"] is int) || !(desktop["StartHidden"] is bool)) return null;
                int port = (int)desktop["HostPort"];
                var resolution = desktop["Resolution"] as string;
                var match = Regex.Match(resolution ?? "", @"^(\d{3,5})x(\d{3,5})$");
                if (port < 1024 || port > 65535 || !match.Success) return null;
                int width = int.Parse(match.Groups[1].Value), height = int.Parse(match.Groups[2].Value);
                if (width < 200 || height < 200 || width > 16384 || height > 16384) return null;
                desktop["width"] = width;
                desktop["height"] = height;
                return desktop;
            }
            catch (Exception error)
            {
                if (error is IOException || error is ArgumentException || error is KeyNotFoundException || error is InvalidOperationException)
                    return null;
                throw;
            }
        }

        private static int RunBridge(string python, string[] arguments)
        {
            string root = Directory.GetCurrentDirectory();
            var hints = ReadDesktopHints(root);
            string hostPath = Path.Combine(root, "res", "ChildSessionHost", "AutoMas.ChildSessionHost.exe");
            if (hints == null || !File.Exists(hostPath))
                return RunPython(python, arguments, root, null, null);
            int port = (int)hints["HostPort"];
            Process ownedHost = null;
            Process hotkeyRelay = null;
            try
            {
                Dictionary<string, object> status = null;
                if (IPGlobalProperties.GetIPGlobalProperties().GetActiveTcpListeners().Any(endpoint => endpoint.Port == port))
                    status = CallHost(port, "/status", null, 2000);
                if (status == null)
                {
                    Log("正在启动远程桌面宿主");
                    ownedHost = Process.Start(new ProcessStartInfo(hostPath,
                        "--port " + port + " --width " + hints["width"] + " --height " + hints["height"] + " --hidden")
                    { UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = root });
                    for (int attempt = 0; attempt < 40 && status == null; attempt++)
                    {
                        if (ownedHost.HasExited) throw new InvalidOperationException("远程桌面宿主已退出");
                        Thread.Sleep(100);
                        status = CallHost(port, "/status", null, 300);
                    }
                }
                if (status == null) throw new TimeoutException("等待远程桌面宿主超时");
                if (!status.ContainsKey("childSessionId") || status["childSessionId"] == null || Convert.ToInt32(status["connectedState"]) != 1)
                    status = CallHost(port, "/connect", new Dictionary<string, object> { { "width", hints["width"] }, { "height", hints["height"] } }, 65000);
                if (status == null || !status.ContainsKey("childSessionId") || status["childSessionId"] == null)
                    throw new InvalidOperationException("未能建立远程桌面执行会话");
                int sessionId = Convert.ToInt32(status["childSessionId"]);
                Log("远程桌面连接就绪: Session=" + sessionId);
                var environment = new Dictionary<string, string>();
                foreach (DictionaryEntry entry in Environment.GetEnvironmentVariables())
                {
                    string key = (string)entry.Key;
                    if (key.StartsWith("AUTO_MAS_", StringComparison.Ordinal) || key.StartsWith("PYTHON", StringComparison.Ordinal))
                        environment[key] = (string)entry.Value;
                }
                environment["AUTO_MAS_EXECUTION_SESSION_ID"] = sessionId.ToString(CultureInfo.InvariantCulture);
                environment["AUTO_MAS_DESKTOP_PARENT_PID"] = Process.GetCurrentProcess().Id.ToString(CultureInfo.InvariantCulture);
                environment["AUTO_MAS_DESKTOP_PARENT_TIME"] = (Process.GetCurrentProcess().StartTime.ToUniversalTime() -
                    new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalSeconds.ToString("R", CultureInfo.InvariantCulture);
                environment["PYTHONIOENCODING"] = "utf-8";
                string pipeName = "AutoMas.Backend." + Guid.NewGuid().ToString("N");
                var security = new PipeSecurity();
                security.SetAccessRuleProtection(true, false);
                security.AddAccessRule(new PipeAccessRule(WindowsIdentity.GetCurrent().User, PipeAccessRights.FullControl, AccessControlType.Allow));
                using (var pipe = new NamedPipeServerStream(pipeName, PipeDirection.InOut, 1, PipeTransmissionMode.Byte,
                    PipeOptions.Asynchronous, 16384, 16384, security))
                {
                    var launched = CallHost(port, "/launch", new Dictionary<string, object> {
                        { "executablePath", Process.GetCurrentProcess().MainModule.FileName },
                        { "arguments", "--worker " + Quote(pipeName) }, { "workingDirectory", root } }, 40000);
                    if (launched == null || !launched.ContainsKey("ok") || !(bool)launched["ok"])
                        throw new InvalidOperationException("远程桌面启动代理失败");
                    if (!pipe.WaitForConnectionAsync().Wait(15000)) throw new TimeoutException("执行会话代理握手超时");
                    Log("执行会话代理已连接，正在启动 Python 后端");
                    using (var reader = new StreamReader(pipe, Utf8, false, 16384, true))
                    using (var writer = new StreamWriter(pipe, Utf8, 16384, true) { AutoFlush = true })
                    {
                        writer.WriteLine(Json.Serialize(new { version = 1, python, arguments, root, sessionId, environment }));
                        // 后端在分身中注册热键；主桌面需要自己的监听器转交同一组调度接口。
                        hotkeyRelay = Process.Start(new ProcessStartInfo(python,
                            "-m app.core.hotkey_relay --parent-pid " + Process.GetCurrentProcess().Id +
                            " -- " + string.Join(" ", arguments.Skip(1).Select(Quote)))
                        { UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = root });
                        string line;
                        while ((line = reader.ReadLine()) != null)
                        {
                            var message = Json.Deserialize<Dictionary<string, object>>(line);
                            string kind = (string)message["kind"];
                            if (kind == "output") Console.Error.WriteLine((string)message["text"]);
                            else if (kind == "exit") return Convert.ToInt32(message["code"]);
                            else if (kind == "error") throw new InvalidOperationException((string)message["text"]);
                            else Console.Out.WriteLine(line);
                        }
                        throw new IOException("执行会话代理连接意外关闭");
                    }
                }
            }
            finally
            {
                if (hotkeyRelay != null)
                {
                    if (!hotkeyRelay.HasExited) hotkeyRelay.Kill();
                    hotkeyRelay.Dispose();
                }
                // 只回收自己创建的宿主；前端关闭与此独立代理无关。
                if (ownedHost != null && !ownedHost.HasExited) CallHost(port, "/shutdown", new Dictionary<string, object>(), 2000);
                if (ownedHost != null) ownedHost.Dispose();
            }
        }

        private static int RunWorker(string name)
        {
            using (var pipe = new NamedPipeClientStream(".", name, PipeDirection.InOut, PipeOptions.None))
            {
                pipe.Connect(15000);
                using (var reader = new StreamReader(pipe, Utf8, false, 16384, true))
                using (var writer = new StreamWriter(pipe, Utf8, 16384, true) { AutoFlush = true })
                {
                    Action<object> send = message => {
                        lock (OutputLock) { try { writer.WriteLine(Json.Serialize(message)); } catch (IOException) { /* 父代理退出后由后端会话守卫收尾。 */ } }
                    };
                    try
                    {
                        var job = Json.Deserialize<Dictionary<string, object>>(reader.ReadLine());
                        if (Convert.ToInt32(job["version"]) != 1 || Process.GetCurrentProcess().SessionId != Convert.ToInt32(job["sessionId"]))
                            throw new InvalidOperationException("执行会话代理握手不匹配");
                        var environment = ((Dictionary<string, object>)job["environment"]).ToDictionary(pair => pair.Key, pair => (string)pair.Value);
                        var arguments = ((ArrayList)job["arguments"]).Cast<string>().ToArray();
                        return RunPython((string)job["python"], arguments, (string)job["root"], environment, send);
                    }
                    catch (Exception error)
                    {
                        send(new { kind = "error", text = error.GetBaseException().Message });
                        return 1;
                    }
                }
            }
        }

        private static int RunPython(string python, string[] arguments, string root,
            Dictionary<string, string> environment, Action<object> send)
        {
            // python.exe 提供可重定向的标准流；CreateNoWindow 保证不会弹出控制台。
            string consolePython = Path.Combine(Path.GetDirectoryName(python), "python.exe");
            if (File.Exists(consolePython)) python = consolePython;
            var start = new ProcessStartInfo(python, string.Join(" ", arguments.Select(Quote))) {
                UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = root,
                RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
                StandardOutputEncoding = Utf8, StandardErrorEncoding = Utf8 };
            if (environment != null) foreach (var pair in environment) start.EnvironmentVariables[pair.Key] = pair.Value;
            using (var process = new Process { StartInfo = start })
            {
                DataReceivedEventHandler output = (sender, data) => {
                    if (data.Data == null) return;
                    if (send == null) { lock (OutputLock) Console.Error.WriteLine(data.Data); }
                    else send(new { kind = "output", text = data.Data });
                };
                process.OutputDataReceived += output;
                process.ErrorDataReceived += output;
                process.Start();
                if (send != null) send(new { kind = "started", pid = process.Id, sessionId = process.SessionId });
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
                process.WaitForExit();
                if (send != null) send(new { kind = "exit", code = process.ExitCode });
                return process.ExitCode;
            }
        }

        private static Dictionary<string, object> CallHost(int port, string path, Dictionary<string, object> body, int timeout)
        {
            try
            {
                var request = (HttpWebRequest)WebRequest.Create("http://127.0.0.1:" + port + path);
                request.Proxy = null;
                request.Timeout = timeout;
                request.ReadWriteTimeout = timeout;
                if (body != null)
                {
                    request.Method = "POST";
                    request.ContentType = "application/json; charset=utf-8";
                    byte[] bytes = Utf8.GetBytes(Json.Serialize(body));
                    request.ContentLength = bytes.Length;
                    using (var stream = request.GetRequestStream()) stream.Write(bytes, 0, bytes.Length);
                }
                using (var response = request.GetResponse())
                using (var reader = new StreamReader(response.GetResponseStream(), Utf8))
                    return Json.Deserialize<Dictionary<string, object>>(reader.ReadToEnd());
            }
            catch (WebException) { return null; }
        }

        private static string Quote(string value)
        {
            // CommandLineToArgvW 的引号规则，保留空参数、路径末尾反斜杠与内嵌引号。
            return "\"" + Regex.Replace(Regex.Replace(value, "(\\\\*)\"", "$1$1\\\""), "(\\\\+)$", "$1$1") + "\"";
        }

        private static void Log(string message)
        {
            Console.Error.WriteLine(DateTime.UtcNow.AddHours(8).ToString("yyyy-MM-dd HH:mm:ss.fff") +
                " | INFO     | 后端启动代理 | " + message);
        }
    }
}
