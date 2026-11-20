// 档案阵列部件的表面：取演示基线的阵列材质（颜色为线性值）。
// 外壳另带原项目的竖向渐变：底部暖褐、顶部近白（three.js 里是 onBeforeCompile 注入的同一段）。
VARYING float vPanel;

void MAIN()
{
    vec3 col = uColor;
    if (uGradient > 0.5)
        col *= mix(vec3(0.72, 0.64, 0.55), vec3(1.0, 0.98, 0.94), smoothstep(0.1, 1.0, vPanel));
    BASE_COLOR = vec4(col, 1.0);
    ROUGHNESS = uRoughness;
    METALNESS = uMetalness;
    TRANSMISSION_FACTOR = uTransmission;
    THICKNESS_FACTOR = uThickness;
    ATTENUATION_COLOR = uAttenuation;
    ATTENUATION_DISTANCE = uAttenuationDistance;
    CLEARCOAT_AMOUNT = uClearcoat;
    CLEARCOAT_ROUGHNESS = uClearcoatRoughness;
}
