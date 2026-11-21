// 抽出盒的双卷盘内衬。图案固定在模型局部坐标中，选中进度只控制显现。
VARYING float vRaised;
VARYING float vClarity;
VARYING vec3 vLocal;
float lineMask(float distance, float width)
{
    float aa = max(fwidth(distance), 0.0001);
    return 1.0 - smoothstep(width - aa, width + aa, abs(distance));
}

void MAIN()
{
    vec3 backing = mix(uColor, uRaisedColor, vClarity);
    if (vRaised > 0.0) {
        vec2 p = vLocal.xy - vec2(0.0, 1.82);
        // 斜纹只印在内衬上，两只卷盘通过同一条带路相连。
        vec2 edge = vec2(1.98, 1.35) - abs(p);
        float paper = smoothstep(0.0, 0.025, min(edge.x, edge.y));
        float stripe = lineMask(fract((p.x + p.y) / 0.73) - 0.5, 0.12);
        vec3 printColor = mix(backing, vec3(0.10, 0.085, 0.07), 0.23 * stripe * paper);
        float belt = length(vec2(max(abs(p.x) - 0.91, 0.0), p.y));
        vec2 hub = vec2(abs(p.x) - 0.91, p.y);
        float r = length(hub);
        vec3 graphite = vec3(0.043, 0.035, 0.029);
        printColor = mix(printColor, graphite, 0.70 * lineMask(belt - 0.92, 0.052));
        printColor = mix(printColor, graphite, 0.84 * (1.0 - smoothstep(0.74, 0.78, r)));
        float rim = max(lineMask(r - 0.82, 0.031), lineMask(r - 0.55, 0.023));
        printColor = mix(printColor, uRaisedColor, 0.8 * rim);
        vec2 hole = vec2(abs(hub.x), hub.y);
        float holes = min(length(hub - vec2(0.0, 0.36)), length(hole - vec2(0.312, -0.18)));
        printColor = mix(printColor, uRaisedColor, (1.0 - smoothstep(0.085, 0.105, holes)) * step(p.x, 0.0));
        printColor = mix(printColor, vec3(0.55, 0.20, 0.055), 1.0 - smoothstep(0.20, 0.23, r));
        backing = mix(backing, printColor, vRaised);
    }
    BASE_COLOR = vec4(backing, 1.0);
    EMISSIVE_COLOR = backing * vRaised * uGlow;
    ROUGHNESS = uRoughness;
    METALNESS = uMetalness;
}
