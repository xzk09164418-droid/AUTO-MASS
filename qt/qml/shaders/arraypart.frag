// 档案阵列部件的表面：取演示基线的阵列材质（颜色为线性值）。
// 外壳另带原项目的竖向渐变：底部暖褐、顶部近白（three.js 里是 onBeforeCompile 注入的同一段）。
VARYING float vPanel;
VARYING float vRaised;
VARYING float vClarity;

void MAIN()
{
    vec3 col = uColor;
    vec3 tint = mix(vec3(0.40, 0.30, 0.20), vec3(1.0, 0.98, 0.94), smoothstep(0.1, 1.0, vPanel));
    col *= mix(vec3(1.0), tint, uGradient);
    // 顶边先清晰，底边最后清晰；抬升本身不触发解密。
    float front = 1.0 - 1.24 * vClarity;
    float clear = smoothstep(front, front + 0.24, clamp(vPanel, 0.0, 1.0));
    BASE_COLOR = vec4(mix(col, uRaisedColor, clear), 1.0);
    ROUGHNESS = mix(uRoughness, 0.025, clear);
    METALNESS = uMetalness;
    TRANSMISSION_FACTOR = mix(uTransmission, 0.985, clear);
    THICKNESS_FACTOR = mix(uThickness,0.018,clear);
    ATTENUATION_COLOR = uAttenuation;
    ATTENUATION_DISTANCE = mix(uAttenuationDistance,8.0,clear);
    CLEARCOAT_AMOUNT = uClearcoat;
    CLEARCOAT_ROUGHNESS = uClearcoatRoughness;
    // 深色主题：抽出的那盒自身发出柔光（uGlow 只在深色下非 0）
    EMISSIVE_COLOR = uRaisedColor * vRaised * uGlow;
}
