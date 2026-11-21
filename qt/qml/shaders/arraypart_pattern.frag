// 漫射板（录像带内部的那块板）：在 arraypart_opaque.frag 的基础上，按格位（列、行）取随机种子，
// 从 6 种莱茵档案风格的图案里挑一种程序化画出——点阵、斜纹、同心环、条码、电路走线、准星，部分另带橙色角标。
// 平时盒子不透明、图案不显示；抽出（抬起）时外壳转为透明，一道橙色扫描线随抽出进度自下而上扫过，
// 扫过的部分逐渐显出这一盒专属的图案，像把盒内资料「读出来」。
VARYING float vPanel;
VARYING float vRaised;
VARYING float vClarity;
VARYING vec3 vLocal;
VARYING vec2 vCell;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
// 抗锯齿的线条覆盖：d 为到线中心的距离，w 为半线宽
float lineMask(float d, float w) { float aa = max(fwidth(d), 1e-4); return 1.0 - smoothstep(w - aa, w + aa, abs(d)); }
float boxMask(vec2 p, vec2 lo, vec2 hi) {
    vec2 aa = max(fwidth(p), vec2(1e-4));
    vec2 a = smoothstep(lo - aa, lo + aa, p) * (1.0 - smoothstep(hi - aa, hi + aa, p));
    return a.x * a.y;
}

float pattern(vec2 p, vec2 cell, out float accent)
{
    accent = 0.0;
    float h = hash(cell);
    float h2 = hash(cell + 17.3);
    float h3 = hash(cell + 41.9);
    int kind = int(floor(h * 6.0));
    // 图案只画在板中央的取景框里，四周留白
    vec2 lo = vec2(-1.95, 0.55), hi = vec2(1.95, 3.2);
    float frame = boxMask(p, lo, hi);
    vec2 q = p - lo;
    float m = 0.0;
    if (kind == 0) {                      // 点阵
        float s = mix(0.62, 0.86, h2);
        vec2 g = mod(q, s) - 0.5 * s;
        float aa = max(fwidth(length(g)), 1e-4);
        m = 1.0 - smoothstep(0.15 - aa, 0.15 + aa, length(g));
    } else if (kind == 1) {               // 斜纹
        float s = mix(0.55, 0.8, h2);
        float d = mod(q.x + q.y * (h3 > 0.5 ? 1.0 : -1.0), s) - 0.5 * s;
        m = lineMask(d, 0.11);
    } else if (kind == 2) {               // 同心环
        vec2 c = vec2(mix(-1.2, 1.2, h2), mix(1.2, 2.6, h3));
        float r = length(p - c);
        float s = 0.52;
        m = lineMask(mod(r, s) - 0.5 * s, 0.09) * (1.0 - smoothstep(1.7, 1.8, r));
        accent = 1.0 - smoothstep(0.2, 0.24, r);
    } else if (kind == 3) {               // 条码
        float col = floor(q.x * 3.2);
        float bar = step(0.45, hash(vec2(col, cell.x * 3.1 + cell.y)));
        float thin = step(0.55, fract(q.x * 3.2)) * step(0.7, hash(vec2(col, h)));
        m = max(bar, thin) * boxMask(p, vec2(lo.x, 1.0), vec2(hi.x, 2.4));
        accent = boxMask(p, vec2(lo.x, 2.6), vec2(lo.x + 1.1, 2.95));
    } else if (kind == 4) {               // 电路走线：网格上随机取横 / 竖段，节点画方点
        float s = 0.95;
        vec2 id = floor(q / s), f = fract(q / s) - 0.5;
        float hr = hash(id + cell * 0.37), vr = hash(id.yx + cell * 0.53 + 9.1);
        float horiz = step(0.55, hr) * lineMask(f.y * s, 0.08) * step(-0.5, f.x);
        float vert = step(0.6, vr) * lineMask(f.x * s, 0.08) * step(-0.5, f.y);
        float node = step(0.75, hr) * boxMask(f * s, vec2(-0.16), vec2(0.16));
        m = max(max(horiz, vert), node);
    } else {                              // 准星：外圈 + 十字 + 刻度
        vec2 c = vec2(mix(-0.8, 0.8, h2), 1.85);
        vec2 d = p - c;
        float r = length(d);
        float ring = lineMask(r - 1.05, 0.1) + lineMask(r - 0.55, 0.07);
        float cross = (lineMask(d.x, 0.07) + lineMask(d.y, 0.07)) * (1.0 - smoothstep(1.3, 1.35, r)) * step(0.3, r);
        float ang = atan(d.y, d.x);
        float ticks = lineMask(mod(ang, 0.5236) - 0.2618, 0.05) * step(1.15, r) * (1.0 - step(1.4, r));
        m = clamp(ring + cross + ticks, 0.0, 1.0);
        accent = 1.0 - smoothstep(0.17, 0.21, r);
    }
    // 约三分之一的盒子带一枚橙色角标（位置随机落在四角之一）
    if (h3 > 0.66) {
        vec2 corner = vec2(h2 > 0.5 ? hi.x - 0.5 : lo.x + 0.05, hash(cell + 3.3) > 0.5 ? hi.y - 0.5 : lo.y + 0.05);
        accent = max(accent, boxMask(p, corner, corner + 0.45));
    }
    accent *= frame;
    return m * frame;
}

void MAIN()
{
    vec3 col = uColor;
    if (uGradient > 0.5)
        col *= mix(vec3(0.72, 0.64, 0.55), vec3(1.0, 0.98, 0.94), smoothstep(0.1, 1.0, vPanel));
    vec3 lifted = uRaisedColor;
    // 扫描进度：随抽出量自下而上推进，抽满后扫描线移出板外
    float t = clamp((vLocal.y - 0.125) / 3.47, 0.0, 1.0);
    float front = vRaised * 1.25 - 0.12;
    float shown = 1.0 - smoothstep(front - 0.08, front, t);
    float accent = 0.0;
    float m = pattern(vLocal.xy, vCell, accent);
    lifted = mix(lifted, uPatternColor, m * shown * uPatternAmount);
    lifted = mix(lifted, uAccentColor, accent * shown);
    // 扫描线：亮橙色细带，前缘稍带拖尾
    float aa = max(fwidth(t), 1e-4);
    float scan = (1.0 - smoothstep(0.004, 0.004 + 2.0 * aa, abs(t - front))) + 0.35 * shown * (1.0 - smoothstep(0.0, 0.06, front - t));
    scan *= step(0.02, vRaised) * (1.0 - step(0.999, vRaised));
    lifted = mix(lifted, uScanColor, clamp(scan, 0.0, 1.0));
    BASE_COLOR = vec4(mix(col, lifted, vRaised), 1.0);
    EMISSIVE_COLOR = uScanColor * clamp(scan, 0.0, 1.0) * 1.6 * vRaised + lifted * vRaised * uGlow;
    ROUGHNESS = uRoughness;
    METALNESS = uMetalness;
    CLEARCOAT_AMOUNT = uClearcoat;
    CLEARCOAT_ROUGHNESS = uClearcoatRoughness;
}
