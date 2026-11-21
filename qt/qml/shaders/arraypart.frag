// 档案阵列部件的表面：取演示基线的阵列材质（颜色为线性值）。
// 外壳另带原项目的竖向渐变：底部暖褐、顶部近白（three.js 里是 onBeforeCompile 注入的同一段）。
VARYING float vPanel;
VARYING float vRaised;
VARYING float vClarity;

void MAIN()
{
    vec3 col = uColor;
    if (uGradient > 0.5)
        col *= mix(vec3(0.40, 0.30, 0.20), vec3(1.0, 0.98, 0.94), smoothstep(0.1, 1.0, vPanel));
    BASE_COLOR = vec4(mix(col,uRaisedColor,vRaised), 1.0);
    ROUGHNESS = mix(uRoughness,mix(0.21,0.025,vClarity),vRaised);
    METALNESS = uMetalness;
    TRANSMISSION_FACTOR = mix(uTransmission,mix(0.9,0.985,vClarity),vRaised);
    THICKNESS_FACTOR = mix(uThickness,0.018,vClarity);
    ATTENUATION_COLOR = uAttenuation;
    ATTENUATION_DISTANCE = mix(uAttenuationDistance,8.0,vClarity);
    CLEARCOAT_AMOUNT = uClearcoat;
    CLEARCOAT_ROUGHNESS = uClearcoatRoughness;
}
