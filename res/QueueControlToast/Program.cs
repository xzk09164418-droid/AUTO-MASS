using System;
using System.Collections.Generic;
using System.Net;
using System.Text;
using System.Web.Script.Serialization;

// 原生通知协议入口：仅向固定的本机控制接口提交带轮次身份的动作。
internal static class QueueControlToast
{
    [STAThread]
    private static void Main(string[] args)
    {
        try
        {
            if (args.Length != 1) return;
            Uri uri = new Uri(args[0]);
            if (!uri.Scheme.StartsWith("automas-control-", StringComparison.Ordinal)) return;
            string encoded = uri.AbsolutePath.Trim('/').Replace('-', '+').Replace('_', '/');
            encoded = encoded.PadRight(encoded.Length + (4 - encoded.Length % 4) % 4, '=');
            var json = new JavaScriptSerializer();
            var data = json.Deserialize<Dictionary<string, object>>(Encoding.UTF8.GetString(Convert.FromBase64String(encoded)));
            string action = Convert.ToString(data["action"]);
            if (action != "pause" && action != "continue") return;
            int port = Convert.ToInt32(data["port"]);
            if (port < 1 || port > 65535) return;
            var body = new Dictionary<string, object> {
                {"action", action}, {"taskId", data["taskId"]}, {"token", data["token"]}
            };
            byte[] bytes = Encoding.UTF8.GetBytes(json.Serialize(body));
            var request = (HttpWebRequest)WebRequest.Create("http://127.0.0.1:" + port + "/api/dispatch/navigation/control");
            request.Proxy = null;
            request.Method = "POST";
            request.Timeout = 10000;
            request.ContentType = "application/json";
            request.Headers["X-AUTO-MAS-Instance"] = Convert.ToString(data["instanceId"]);
            request.ContentLength = bytes.Length;
            using (var stream = request.GetRequestStream()) stream.Write(bytes, 0, bytes.Length);
            using (var response = request.GetResponse()) { }
        }
        catch { /* 失效或已退出的队列不重新启动程序，也不重试旧动作。 */ }
    }
}
