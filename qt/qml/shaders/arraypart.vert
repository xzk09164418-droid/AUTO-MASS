// 档案阵列的实例化部件：波浪、呼吸、选择涟漪、悬停抬起与飞入都在这里逐顶点计算，
// CPU 每帧只更新少量 uniform（实例表只在换档时重建）。数值与演示基线 / 原项目 motion.ts 一致。
// INSTANCE_DATA = (列, 行, 实例表里已烘入的静态高度, 0)
VARYING float vPanel;

float smoothT(float t) { t = clamp(t, 0.0, 1.0); return t * t * t * (10.0 + t * (-15.0 + 6.0 * t)); }
float bell(float x, float w) { float q = x / w; return exp(-0.5 * q * q); }
float settling(float d)
{
    float age = 26.56 - 25.05 - abs(d) * 0.065;
    float envelope = max(-0.42, 2.15 - 0.17 * (sqrt(d * d + 1.0) - 1.0));
    float ring = age > 0.0 ? sin(age * 5.1) * exp(-age * 1.3) : 0.0;
    return envelope * (smoothT(age / 0.62) + 0.18 * ring * smoothT(age / 0.16));
}
float selection(float dist, float age)
{
    if (age < 0.0 || age > 3.2) return 0.0;
    return 0.8 * smoothT(age / 0.2) * exp(-age * 1.15) * cos((dist - age * 8.0) * 0.58) * bell(dist - age * 8.0, 3.4);
}
float ripple(vec4 p, float r, float l)
{
    if (p.w < 0.5) return 0.0;
    return selection(length(vec2(r - p.y, (l - p.x) * 2.2)), uTime - p.z);
}
float field(float r, float l)
{
    float t = uTime;
    float idle = 0.075 * sin(t * 3.14159265 / 4.0 + r * 0.3 - l * 0.45) + 0.027 * sin(t * 3.14159265 * 2.0 / 13.0 - r * 0.17 + l * 0.3);
    float rp = ripple(uPulse0, r, l) + ripple(uPulse1, r, l) + ripple(uPulse2, r, l) + ripple(uPulse3, r, l) + ripple(uPulse4, r, l) + ripple(uPulse5, r, l);
    return settling(r - uShoulder) * (0.25 + 0.75 * bell(l - uFocus, 0.55)) + idle * uIdle + clamp(rp, -0.6, 0.6) * uPulseGain;
}
float hoverLift(vec4 h, float r, float l) { return abs(h.x - l) < 0.5 && abs(h.y - r) < 0.5 ? h.z : 0.0; }

void MAIN()
{
    float l = INSTANCE_DATA.x, r = INSTANCE_DATA.y;
    float y = field(r, l) - INSTANCE_DATA.z + hoverLift(uHover0, r, l) + hoverLift(uHover1, r, l) + hoverLift(uHover2, r, l);
    float a = (field(r + 0.5, l) - field(r - 0.5, l)) * 0.024 * (1.0 - uDetail);
    // 飞入：从画面右上方之外沿录像带长边（世界 +x，画面里由右上往左下）斜向滑入各自的格位，不竖直下落；
    // 以选中格为中心按行列距离错峰
    float delay = 0.025 * abs(r - uCellRow) + 0.07 * abs(l - uCellLane);
    float p = clamp((uFly - delay) / 0.9, 0.0, 1.0);
    float e = 1.0 - (1.0 - p) * (1.0 - p) * (1.0 - p);
    vec3 v = VERTEX;
    vPanel = v.y / 3.7;
    float c = cos(a), s = sin(a);
    VERTEX = vec3(v.x, c * v.y - s * v.z, s * v.y + c * v.z) + vec3(26.0 * (1.0 - e), y + 1.5 * (1.0 - e), 0.0);
    vec3 n = NORMAL;
    NORMAL = vec3(n.x, c * n.y - s * n.z, s * n.y + c * n.z);
}
