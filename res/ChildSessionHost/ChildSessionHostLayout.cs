using System;
using System.Collections.Generic;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace BetterGenshinImpact.Service.ChildSession
{
    public sealed partial class ChildSessionHostForm
    {
        private readonly Dictionary<Control, Font> _designFonts = new Dictionary<Control, Font>();
        private readonly Dictionary<ToolStripItem, Font> _designMenuFonts = new Dictionary<ToolStripItem, Font>();
        private readonly List<Font> _scaledFonts = new List<Font>();
        private float _layoutScale = 1f;
        private bool _responsiveReady;
        private bool _layingOut;

        [DllImport("user32.dll")]
        private static extern uint GetDpiForWindow(IntPtr window);

        private int Ui(int value) { return Math.Max(1, (int)Math.Ceiling(value * _layoutScale)); }

        private void RememberFonts(Control control)
        {
            if (control == _rdpHost) return;
            // ActiveX 的 COM IFont 要求点单位字体。仅缩放文字控件，
            // 不改变 Form/Panel 的继承字体，避免 RDP 激活时继承像素字体而崩溃。
            if (control is Label || control is Button || control is ToolStrip)
                _designFonts[control] = control.Font;
            foreach (Control child in control.Controls) RememberFonts(child);
        }

        private void RememberMenuFonts(ToolStripItemCollection items)
        {
            foreach (ToolStripItem item in items)
            {
                _designMenuFonts[item] = item.Font;
                var menu = item as ToolStripMenuItem;
                if (menu != null) RememberMenuFonts(menu.DropDownItems);
            }
        }

        protected override void Dispose(bool disposing)
        {
            base.Dispose(disposing);
            if (disposing)
            {
                foreach (var font in _scaledFonts) font.Dispose();
                _scaledFonts.Clear();
            }
        }

        private void InitializeResponsiveLayout()
        {
            RememberFonts(this);
            RememberFonts(_controlCenterMenu);
            RememberFonts(_trayMenu);
            RememberMenuFonts(_controlCenterMenu.Items);
            RememberMenuFonts(_trayMenu.Items);
            _rightButtonFlow.Dock = DockStyle.None;
            _rightButtonFlow.AutoSize = false;
            _rightButtonFlow.WrapContents = true;
            _titleLabel.AutoSize = false;
            _overlayBackdrop.AutoScroll = true;
            _infoBarLabel.AutoEllipsis = false;
            _responsiveReady = true;
            SizeChanged += delegate { LayoutResponsiveControls(); };
            _infoBarLabel.TextChanged += delegate { LayoutResponsiveControls(); };
            ApplyDisplayDpi(IsHandleCreated ? (int)GetDpiForWindow(Handle) : 96);
        }

        protected override void OnHandleCreated(EventArgs e)
        {
            base.OnHandleCreated(e);
            if (_responsiveReady) ApplyDisplayDpi((int)GetDpiForWindow(Handle));
        }

        protected override void WndProc(ref Message message)
        {
            const int DpiChanged = 0x02E0;
            base.WndProc(ref message);
            if (message.Msg == DpiChanged && _responsiveReady)
            {
                ApplyDisplayDpi((int)(message.WParam.ToInt64() & 0xffff));
            }
        }

        private void ApplyDisplayDpi(int dpi)
        {
            // 使用明确的像素字体，只缩放一次；避免 WinForms 自动缩放与手动坐标叠加。
            _layoutScale = Math.Max(96, dpi) / 96f;
            var previous = new List<Font>(_scaledFonts);
            _scaledFonts.Clear();
            SuspendLayout();
            foreach (var entry in _designFonts)
            {
                var font = new Font(entry.Value.FontFamily, entry.Value.SizeInPoints * Math.Max(96, dpi) / 72f,
                    entry.Value.Style, GraphicsUnit.Pixel);
                _scaledFonts.Add(font);
                entry.Key.Font = font;
            }
            foreach (var entry in _designMenuFonts)
            {
                var font = new Font(entry.Value.FontFamily, entry.Value.SizeInPoints * Math.Max(96, dpi) / 72f,
                    entry.Value.Style, GraphicsUnit.Pixel);
                _scaledFonts.Add(font);
                entry.Key.Font = font;
            }
            ResumeLayout(false);
            LayoutResponsiveControls();
            foreach (var font in previous) font.Dispose();
        }

        private int PlaceLabel(Label label, int x, int y, int width)
        {
            label.AutoSize = false;
            label.AutoEllipsis = false;
            label.UseMnemonic = false;
            var size = TextRenderer.MeasureText(label.Text.Length == 0 ? " " : label.Text, label.Font,
                new Size(Math.Max(1, width), int.MaxValue), TextFormatFlags.WordBreak | TextFormatFlags.NoPrefix);
            label.SetBounds(x, y, Math.Max(1, width), size.Height + Ui(4));
            return label.Bottom;
        }

        private void LayoutResponsiveControls()
        {
            if (!_responsiveReady || _layingOut || ClientSize.Width == 0) return;
            _layingOut = true;
            try
            {
                int padding = Ui(12), gap = Ui(6);
                int available = Math.Max(Ui(100), ClientSize.Width - 2 * padding);
                int titleBottom = PlaceLabel(_titleLabel, padding + Ui(20), gap, available - Ui(20));
                _statusDotPanel.SetBounds(padding, gap + Ui(5), Ui(12), Ui(12));
                int rowWidth = 0, rows = 1, rowHeight = 0;
                foreach (Control control in _rightButtonFlow.Controls)
                {
                    var button = (Button)control;
                    var measured = TextRenderer.MeasureText(button.Text, button.Font);
                    button.Size = new Size(Math.Min(available, measured.Width + Ui(22)), measured.Height + Ui(12));
                    button.Margin = new Padding(0, 0, gap, gap);
                    if (rowWidth > 0 && rowWidth + button.Width + gap > available) { rows++; rowWidth = 0; }
                    rowWidth += button.Width + gap;
                    rowHeight = Math.Max(rowHeight, button.Height + gap);
                }
                _rightButtonFlow.Padding = Padding.Empty;
                _rightButtonFlow.SetBounds(padding, titleBottom + gap, available, rows * rowHeight);
                _topBar.Height = _rightButtonFlow.Bottom + gap;
                _infoBarPanel.Padding = new Padding(padding, gap, padding, gap);
                _infoBarCloseBtn.Width = Ui(28);
                int infoWidth = Math.Max(1, available - _infoBarCloseBtn.Width);
                _infoBarPanel.Height = TextRenderer.MeasureText(_infoBarLabel.Text.Length == 0 ? " " : _infoBarLabel.Text,
                    _infoBarLabel.Font, new Size(infoWidth, int.MaxValue), TextFormatFlags.WordBreak | TextFormatFlags.NoPrefix).Height + 2 * gap;

                int width = Math.Max(Ui(160), Math.Min(Ui(620), _overlayBackdrop.ClientSize.Width - 2 * padding - SystemInformation.VerticalScrollBarWidth));
                int inset = Ui(24), content = Math.Max(1, width - 2 * inset), y = Ui(20);
                _badgePanel.SetBounds((width - Ui(68)) / 2, y, Ui(68), Ui(68));
                y = _badgePanel.Bottom + Ui(14);
                _cardStatusDot.SetBounds(inset, y + Ui(10), Ui(10), Ui(10));
                y = PlaceLabel(_cardTitleLabel, inset + Ui(18), y, content - Ui(18)) + gap;
                y = PlaceLabel(_cardDescLabel, inset, y, content) + Ui(14);
                _diagBox.SetBounds(inset, y, content, Ui(100));
                var values = new Label[] { _lblRdpStateValue, _lblSessionStateValue, _lblLeaseStateValue };
                var keys = new List<Label>();
                foreach (Control c in _diagBox.Controls)
                {
                    var label = c as Label;
                    if (label != null && label != _lblEnvSummary && Array.IndexOf(values, label) < 0) keys.Add(label);
                }
                int dy = padding, keyWidth = Math.Min(Ui(112), content / 3);
                for (int i = 0; i < values.Length; i++)
                {
                    int bottom = PlaceLabel(keys[i], padding, dy, keyWidth);
                    bottom = Math.Max(bottom, PlaceLabel(values[i], padding + keyWidth + gap, dy,
                        Math.Max(1, content - 2 * padding - keyWidth - gap)));
                    dy = bottom + gap;
                }
                dy = PlaceLabel(_lblEnvSummary, padding, dy, Math.Max(1, content - 2 * padding)) + padding;
                _diagBox.Height = dy;
                y = _diagBox.Bottom + Ui(14);
                int bx = inset, lineHeight = 0;
                foreach (var button in new Button[] { _btnPrimaryConnect, _btnRefreshDiag, _btnHelpDoc })
                {
                    var measured = TextRenderer.MeasureText(button.Text, button.Font);
                    int bw = Math.Min(content, measured.Width + Ui(28)), bh = measured.Height + Ui(16);
                    if (bx > inset && bx + bw > width - inset) { bx = inset; y += lineHeight + gap; lineHeight = 0; }
                    button.SetBounds(bx, y, bw, bh);
                    bx += bw + gap;
                    lineHeight = Math.Max(lineHeight, bh);
                }
                y += lineHeight + Ui(14);
                y = PlaceLabel(_lblFooterHint1, inset, y, content) + gap;
                y = PlaceLabel(_lblFooterHint2, inset, y, content) + Ui(20);
                _centerCard.Size = new Size(width, y);
                _overlayBackdrop.AutoScrollMinSize = new Size(width + 2 * padding, y + 2 * padding);
                Point scroll = _overlayBackdrop.AutoScrollPosition;
                _centerCard.Location = new Point(Math.Max(padding, (_overlayBackdrop.ClientSize.Width - width) / 2) + scroll.X,
                    Math.Max(padding, (_overlayBackdrop.ClientSize.Height - y) / 2) + scroll.Y);
            }
            finally { _layingOut = false; }
        }
    }
}
