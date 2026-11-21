using System.Drawing;
using System.Windows.Forms;

namespace BetterGenshinImpact.Service.ChildSession
{
    internal sealed class RhineTrayRenderer : ToolStripProfessionalRenderer
    {
        private static readonly Color Paper = Color.FromArgb(28, 39, 44);
        private static readonly Color Rule = Color.FromArgb(83, 97, 102);
        private static readonly Color Accent = Color.FromArgb(224, 122, 44);

        public RhineTrayRenderer() { RoundedEdges = false; }

        protected override void OnRenderToolStripBackground(ToolStripRenderEventArgs e)
        {
            e.Graphics.Clear(Paper);
        }

        protected override void OnRenderImageMargin(ToolStripRenderEventArgs e) { }

        protected override void OnRenderToolStripBorder(ToolStripRenderEventArgs e)
        {
            using (var pen = new Pen(Rule))
                e.Graphics.DrawRectangle(pen, 0, 0, e.ToolStrip.Width - 1, e.ToolStrip.Height - 1);
            using (var brush = new SolidBrush(Accent))
                e.Graphics.FillRectangle(brush, 1, 0, e.ToolStrip.Width - 2, 3);
        }

        protected override void OnRenderMenuItemBackground(ToolStripItemRenderEventArgs e)
        {
            if (!e.Item.Selected) return;
            using (var brush = new SolidBrush(Color.FromArgb(48, 64, 70)))
                e.Graphics.FillRectangle(brush, 0, 0, e.Item.Width, e.Item.Height);
            using (var brush = new SolidBrush(Accent))
                e.Graphics.FillRectangle(brush, 0, 0, 3, e.Item.Height);
        }

        protected override void OnRenderSeparator(ToolStripSeparatorRenderEventArgs e)
        {
            using (var pen = new Pen(Rule))
                e.Graphics.DrawLine(pen, 10, e.Item.Height / 2, e.Item.Width - 10, e.Item.Height / 2);
        }
    }
}
