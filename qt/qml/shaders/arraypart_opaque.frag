// 档案阵列的不透光部件（边、漫射板、索引、紧固件）：与 arraypart.frag 相同但不写透射。
// Qt 只要着色器里出现透射就把材质放进透射通道，不再画进屏幕纹理，外壳就透不出这些内部结构（看起来像白模）。
VARYING float vPanel;

void MAIN()
{
    vec3 col = uColor;
    if (uGradient > 0.5)
        col *= mix(vec3(0.72, 0.64, 0.55), vec3(1.0, 0.98, 0.94), smoothstep(0.1, 1.0, vPanel));
    BASE_COLOR = vec4(col, 1.0);
    ROUGHNESS = uRoughness;
    METALNESS = uMetalness;
    CLEARCOAT_AMOUNT = uClearcoat;
    CLEARCOAT_ROUGHNESS = uClearcoatRoughness;
}
