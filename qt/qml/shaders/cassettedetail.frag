// 刻字和标签需要进入透射材质采样的颜色缓冲。用固定覆盖顺序渐显，始终保留深度写入。
void MAIN()
{
    if (coverage < 1.0) {
        ivec2 pixel = ivec2(gl_FragCoord.xy);
        int x = pixel.x & 3, y = pixel.y & 3;
        int threshold = (((x ^ y) & 1) * 8) + ((y & 1) * 4) + (((x ^ y) & 2)) + (y >> 1);
        if (coverage * 16.0 <= float(threshold)) discard;
    }
    BASE_COLOR = vec4(inkColor, 1.0);
    METALNESS = metal;
    ROUGHNESS = rough;
}
