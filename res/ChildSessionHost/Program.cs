using System;
using System.Windows.Forms;

namespace BetterGenshinImpact.Service.ChildSession
{
    internal static class Program
    {
        [STAThread]
        private static void Main(string[] args)
        {
            int port = 36165;
            int width = 2560;
            int height = 1440;
            // 默认托盘化静默运行，避免干扰主桌面；传入 --show 时才在启动时直接弹出窗口
            bool startHidden = true;

            if (args != null)
            {
                for (int i = 0; i < args.Length; i++)
                {
                    string arg = (args[i] ?? "").ToLowerInvariant();
                    int val;
                    if (arg == "--port" && i + 1 < args.Length && int.TryParse(args[i + 1], out val))
                    {
                        port = val;
                        i++;
                    }
                    else if (arg == "--width" && i + 1 < args.Length && int.TryParse(args[i + 1], out val))
                    {
                        width = val;
                        i++;
                    }
                    else if (arg == "--height" && i + 1 < args.Length && int.TryParse(args[i + 1], out val))
                    {
                        height = val;
                        i++;
                    }
                    else if (arg == "--hidden" || arg == "--tray")
                    {
                        startHidden = true;
                    }
                    else if (arg == "--show" || arg == "--visible")
                    {
                        startHidden = false;
                    }
                }
            }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new ChildSessionHostForm(port, width, height, startHidden));
        }
    }
}
