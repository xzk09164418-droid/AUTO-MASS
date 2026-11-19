.pragma library

// 启动动画的时间工具。时间单位统一为 PV 的 25fps 帧号，便于按原片逐帧校准。

function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v))
}

// a→b 帧之间线性 0→1
function ramp(f, a, b) {
    return clamp((f - a) / (b - a), 0, 1)
}

function easeOut(t) {
    return 1 - Math.pow(1 - t, 3)
}

function easeInOut(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
}

// 关键帧 [[帧, 值], ...] 之间的单调三次插值：保持实测速度，不在每个关键帧停顿、不过冲
function track(keys, f) {
    var last = keys.length - 1
    if (f <= keys[0][0]) return keys[0][1]
    if (f >= keys[last][0]) return keys[last][1]
    function slope(i) {
        return (keys[i + 1][1] - keys[i][1]) / (keys[i + 1][0] - keys[i][0])
    }
    function tangent(i) {
        if (i === 0) return slope(0)
        if (i === last) return slope(last - 1)
        var a = slope(i - 1), b = slope(i)
        if (a * b <= 0) return 0
        var h0 = keys[i][0] - keys[i - 1][0], h1 = keys[i + 1][0] - keys[i][0]
        var w0 = 2 * h1 + h0, w1 = h1 + 2 * h0
        return (w0 + w1) / (w0 / a + w1 / b)
    }
    var i = 0
    while (f > keys[i + 1][0]) i++
    var h = keys[i + 1][0] - keys[i][0]
    var p = (f - keys[i][0]) / h
    return (2 * p * p * p - 3 * p * p + 1) * keys[i][1]
        + (p * p * p - 2 * p * p + p) * h * tangent(i)
        + (-2 * p * p * p + 3 * p * p) * keys[i + 1][1]
        + (p * p * p - p * p) * h * tangent(i + 1)
}

// 离散跳变：从 start 帧起每 hold 帧切换到 values 的下一项，结束后停在最后一项
function steps(f, start, hold, values) {
    if (f < start) return values[0]
    var i = Math.floor((f - start) / hold)
    return values[Math.min(i, values.length - 1)]
}

// 逐字输入：start 帧开始，每 per 帧一个字
function typed(text, f, start, per) {
    if (f < start) return ""
    return text.substring(0, Math.floor((f - start) / (per || 1)) + 1)
}

// 闪现：在 ranges 内的帧可见
function within(f, ranges) {
    for (var i = 0; i < ranges.length; i++)
        if (f >= ranges[i][0] && f < ranges[i][1]) return true
    return false
}
