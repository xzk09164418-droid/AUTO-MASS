using System;
using System.Drawing;
using System.IO;
using System.IO.MemoryMappedFiles;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using Microsoft.Win32;

namespace BetterGenshinImpact.Service.ChildSession
{
    internal sealed class RhineTrayRenderer : ToolStripProfessionalRenderer
    {
        private Color _paper, _ink, _rule, _accent;
        private Font _font;
        private int _dpi;
        private const TextFormatFlags TextFlags = TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix
            | TextFormatFlags.SingleLine | TextFormatFlags.VerticalCenter;

        public RhineTrayRenderer() { RoundedEdges = false; }

        [DllImport("user32.dll")]
        private static extern IntPtr MonitorFromPoint(Point point, uint flags);
        [DllImport("shcore.dll")]
        private static extern int GetDpiForMonitor(IntPtr monitor, int type, out uint x, out uint y);

        public static int CursorDpi()
        {
            uint x, y;
            return GetDpiForMonitor(MonitorFromPoint(Cursor.Position, 2), 0, out x, out y) == 0 ? (int)x : 96;
        }

        public static bool IsDark()
        {
            try
            {
                using (var theme = MemoryMappedFile.OpenExisting(@"Local\AutoMas.QtTrayDark", MemoryMappedFileRights.Read))
                using (var view = theme.CreateViewAccessor(0, 1, MemoryMappedFileAccess.Read))
                    return view.ReadByte(0) != 0;
            }
            catch (FileNotFoundException) { } // Qt window is closed: both trays follow Windows.
            catch (UnauthorizedAccessException) { }
            return Equals(Registry.GetValue(@"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                "AppsUseLightTheme", 1), 0);
        }

        private int Px(int value) { return (int)Math.Round(value * _dpi / 96.0, MidpointRounding.AwayFromZero); }

        public void Apply(ContextMenuStrip menu, bool dark, int dpi)
        {
            // Mirror the Qt tray's 10pt type, 3px accent, item insets and separator margins.
            _paper = dark ? Color.FromArgb(28, 39, 44) : Color.FromArgb(246, 244, 241);
            _ink = dark ? Color.FromArgb(224, 227, 220) : Color.FromArgb(11, 12, 11);
            _rule = dark ? Color.FromArgb(83, 97, 102) : Color.FromArgb(170, 165, 154);
            _accent = dark ? Color.FromArgb(224, 122, 44) : Color.FromArgb(232, 112, 31);
            if (_dpi != dpi)
            {
                _dpi = dpi;
                var previous = _font;
                _font = new Font("Microsoft YaHei UI", 10f * dpi / 72f, FontStyle.Regular, GraphicsUnit.Pixel);
                menu.Font = _font;
                if (previous != null) previous.Dispose();
            }
            menu.BackColor = _paper;
            menu.ForeColor = _ink;
            int widest = 0;
            menu.SuspendLayout();
            foreach (ToolStripItem item in menu.Items)
            {
                if (item is ToolStripSeparator)
                {
                    item.AutoSize = false;
                    item.Height = Px(9);
                }
                else
                {
                    var text = TextRenderer.MeasureText(item.Text, _font, Size.Empty, TextFlags);
                    widest = Math.Max(widest, text.Width);
                    // WinForms already includes vertical leading in its menu item layout.
                    item.Padding = new Padding(0, Px(4), Px(41), Px(4));
                    item.Margin = new Padding(Px(1),
                        item == menu.Items[0] ? Math.Max(0, Px(8) - menu.Padding.Top) : 0, 0,
                        item == menu.Items[menu.Items.Count - 1] ? Math.Max(0, Px(6) - menu.Padding.Bottom) : 0);
                }
            }
            menu.MinimumSize = new Size(widest + Px(19) + Px(22) + 2 * Px(1), 0);
            menu.ResumeLayout(true);
        }

        public void DisposeFont() { if (_font != null) _font.Dispose(); }

        protected override void OnRenderToolStripBackground(ToolStripRenderEventArgs e)
        {
            e.Graphics.Clear(_paper);
        }

        protected override void OnRenderImageMargin(ToolStripRenderEventArgs e) { }

        protected override void OnRenderToolStripBorder(ToolStripRenderEventArgs e)
        {
            var bounds = new Rectangle(Point.Empty, e.ToolStrip.Size);
            ControlPaint.DrawBorder(e.Graphics, bounds, _rule, Px(1), ButtonBorderStyle.Solid,
                _accent, Px(3), ButtonBorderStyle.Solid, _rule, Px(1), ButtonBorderStyle.Solid,
                _rule, Px(1), ButtonBorderStyle.Solid);
        }

        protected override void OnRenderMenuItemBackground(ToolStripItemRenderEventArgs e)
        {
            if (e.Item.Selected && e.Item.Enabled)
            {
                using (var brush = new SolidBrush(_ink))
                    e.Graphics.FillRectangle(brush, 0, 0, e.ToolStrip.Width - 2 * Px(1), e.Item.Height);
                using (var brush = new SolidBrush(_accent))
                    e.Graphics.FillRectangle(brush, 0, 0, Px(3), e.Item.Height);
            }
        }

        protected override void OnRenderItemText(ToolStripItemTextRenderEventArgs e)
        {
            var color = !e.Item.Enabled ? _rule : e.Item.Selected ? _paper : _ink;
            var bounds = new Rectangle(Px(19), 0, e.Item.Width - Px(19), e.Item.Height);
            TextRenderer.DrawText(e.Graphics, e.Text, _font, bounds, color, TextFlags);
            var item = e.Item as ToolStripMenuItem;
            if (item != null && item.Checked)
            {
                int mid = item.Height / 2;
                using (var pen = new Pen(color, Px(2)))
                    e.Graphics.DrawLines(pen, new[] { new Point(Px(6), mid), new Point(Px(9), mid + Px(3)),
                        new Point(Px(15), mid - Px(4)) });
            }
        }

        protected override void OnRenderSeparator(ToolStripSeparatorRenderEventArgs e)
        {
            using (var brush = new SolidBrush(_rule))
                e.Graphics.FillRectangle(brush, Px(12), Px(4), e.Item.Width - 2 * Px(12), Px(1));
        }
    }
}
