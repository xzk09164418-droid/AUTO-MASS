using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows.Forms;

// Portable Qt entry point. All paths are relative to this executable.
internal static class AutoMassQtLauncher
{
    private static string Quote(string value)
    {
        var result = new StringBuilder("\"");
        int slashes = 0;
        foreach (char c in value)
        {
            if (c == '\\') { slashes++; continue; }
            if (c == '"') result.Append('\\', slashes * 2 + 1);
            else result.Append('\\', slashes);
            result.Append(c);
            slashes = 0;
        }
        result.Append('\\', slashes * 2);
        return result.Append('"').ToString();
    }

    [STAThread]
    private static void Main(string[] args)
    {
        try
        {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            string python = Path.Combine(root, "python", "pythonw.exe");
            if (!File.Exists(python)) python = Path.Combine(root, ".venv", "Scripts", "pythonw.exe");
            string entry = Path.Combine(root, "qt", "main.py");
            if (!File.Exists(python) || !File.Exists(entry))
                throw new FileNotFoundException("Extract the complete package before starting AUTO-MASS.");
            var command = new StringBuilder("-I " + Quote(entry));
            foreach (string arg in args) command.Append(" " + Quote(arg));
            var start = new ProcessStartInfo(python, command.ToString());
            start.WorkingDirectory = root;
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            foreach (string name in new[] { "PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "QT_PLUGIN_PATH", "QML2_IMPORT_PATH" })
                start.EnvironmentVariables.Remove(name);
            start.EnvironmentVariables["PYTHONNOUSERSITE"] = "1";
            Process.Start(start);
        }
        catch (Exception error)
        {
            MessageBox.Show(error.Message, "AUTO-MASS", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
