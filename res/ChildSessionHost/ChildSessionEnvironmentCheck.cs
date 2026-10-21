using System;
using System.Collections.Generic;
using System.IO;
using System.Security;
using System.Text;
using Microsoft.Win32;

namespace BetterGenshinImpact.Service.ChildSession
{
    /// <summary>
    /// 桌面分身的 Windows 环境预检（复用自 BetterGI）。
    /// </summary>
    internal static class ChildSessionEnvironmentCheck
    {
        private const string PasswordLessRegistryPath =
            @"SOFTWARE\Microsoft\Windows NT\CurrentVersion\PasswordLess\Device";

        private const string TerminalServerRegistryPath =
            @"SYSTEM\CurrentControlSet\Control\Terminal Server";

        private const string TerminalServerPolicyRegistryPath =
            @"SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services";

        private const int PasswordLessHelloOnlyValue = 2;

        internal sealed class Issue
        {
            public Issue(string title, string message)
            {
                Title = title;
                Message = message;
            }

            public string Title { get; private set; }
            public string Message { get; private set; }
        }

        internal static IReadOnlyList<Issue> Collect()
        {
            var issues = new List<Issue>();
            CollectRdpHostIssue(issues);
            CollectPasswordLessIssue(issues);
            return issues;
        }

        internal static string BuildSummary(IReadOnlyList<Issue> issues)
        {
            if (issues == null || issues.Count == 0)
            {
                return string.Empty;
            }

            var builder = new StringBuilder();
            foreach (var issue in issues)
            {
                if (builder.Length > 0)
                {
                    builder.AppendLine().AppendLine();
                }

                builder.Append('【').Append(issue.Title).Append('】').AppendLine();
                builder.Append(issue.Message);
            }

            return builder.ToString();
        }

        private static void CollectRdpHostIssue(List<Issue> issues)
        {
            var policyValue = ReadInt(
                RegistryHive.LocalMachine,
                TerminalServerPolicyRegistryPath,
                "fDenyTSConnections");
            var localValue = !policyValue.HasValue
                ? ReadInt(RegistryHive.LocalMachine, TerminalServerRegistryPath, "fDenyTSConnections")
                : null;
            var denyTsConnections = policyValue.HasValue ? policyValue : localValue;
            if (denyTsConnections != 1)
            {
                return;
            }

            var suggestion = policyValue.HasValue
                ? "该值由组策略下发，修改本机注册表会被组策略覆盖。"
                  + "请在 gpedit.msc 的「计算机配置 - 管理模板 - Windows 组件 - 远程桌面服务 - "
                  + "远程桌面会话主机 - 连接」中启用「允许用户通过使用远程桌面服务进行远程连接」，"
                  + "或联系域管理员。"
                : "可以尝试在管理员权限下执行：" + Environment.NewLine
                  + "Set-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server' "
                  + "-Name fDenyTSConnections -Value 0 -Type DWord" + Environment.NewLine
                  + "Restart-Service TermService -Force";

            issues.Add(new Issue(
                "远程桌面主机已关闭",
                string.Format(
                    "注册表 fDenyTSConnections = 1（{0}），本机 RDP 监听器不会启动，桌面分身可能无法建立会话。{1}{2}",
                    policyValue.HasValue ? "组策略" : "本机设置",
                    Environment.NewLine,
                    suggestion)));
        }

        private static void CollectPasswordLessIssue(List<Issue> issues)
        {
            var passwordLessVersion = ReadInt(
                RegistryHive.LocalMachine,
                PasswordLessRegistryPath,
                "DevicePasswordLessBuildVersion");
            if (passwordLessVersion != PasswordLessHelloOnlyValue)
            {
                return;
            }

            issues.Add(new Issue(
                "仅允许 Windows Hello 登录",
                "系统已开启「为了提高安全性，仅允许对此设备上的 Microsoft 帐户使用 Windows Hello 登录」，"
                + "此时 Microsoft 帐户在本机没有可用的密码凭据，桌面分身的登录会一直提示凭据无效，"
                + "无论输入什么密码都会失败。" + Environment.NewLine
                + "可在「设置 - 帐户 - 登录选项」中关闭该选项，然后注销并重新登录（部分情况需要重启系统）。"));
        }

        private static int? ReadInt(RegistryHive hive, string path, string name)
        {
            try
            {
                using (var baseKey = RegistryKey.OpenBaseKey(hive, RegistryView.Registry64))
                using (var key = baseKey.OpenSubKey(path))
                {
                    if (key == null)
                    {
                        return null;
                    }
                    var val = key.GetValue(name);
                    return val is int ? (int?)val : null;
                }
            }
            catch (Exception exception)
            {
                if (exception is SecurityException ||
                    exception is UnauthorizedAccessException ||
                    exception is IOException)
                {
                    return null;
                }
                throw;
            }
        }
    }
}
