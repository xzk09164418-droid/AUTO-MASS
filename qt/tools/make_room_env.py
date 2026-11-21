"""生成增强挡位阵列的环境光照贴图 qt/assets3d/room-env.hdr。

演示基线（three.js）用 RoomEnvironment 经 PMREM 作场景环境光（environmentIntensity 0.48），
另加一盏半球光（天 #fffaf5 / 地 #b4a18c，强度 0.65）。Qt Quick 3D 没有这两样，这里按
RoomEnvironment 的几何与灯箱数值做光线求交，把房间与半球光一并烘进一张等距柱状 HDR，
供 SceneEnvironment.lightProbe 使用。

用法：.venv/Scripts/python.exe qt/tools/make_room_env.py
"""

from pathlib import Path

import numpy as np

W, H = 1024, 512
OUT = Path(__file__).resolve().parents[1] / "assets3d" / "room-env.hdr"
LIFT = -3.5                                   # RoomEnvironment.position.y

# 方向：Qt 等距柱状贴图约定（u 绕 Y 轴，v 自上而下）
u = (np.arange(W) + 0.5) / W
v = (np.arange(H) + 0.5) / H
phi = (u - 0.5) * 2 * np.pi
theta = v * np.pi
PH, TH = np.meshgrid(phi, theta)
D = np.stack([np.sin(TH) * np.sin(PH), np.cos(TH), -np.sin(TH) * np.cos(PH)], -1).reshape(-1, 3)
N = D.shape[0]


def box_hit(pos, scale, rot_y=0.0, inside=False):
    """单位立方体经缩放、绕 Y 旋转、平移后，与从原点出发的射线求交：返回 (t, 法线)。"""
    c, s = np.cos(rot_y), np.sin(rot_y)
    # 世界 → 盒子局部（先平移、再逆旋转）
    o = -np.asarray(pos, float)
    R = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])      # 绕 Y 旋转
    Ri = R.T
    ol = Ri @ o
    dl = D @ Ri.T
    half = np.asarray(scale, float) / 2
    with np.errstate(divide="ignore", invalid="ignore"):
        t1 = (-half - ol) / dl
        t2 = (half - ol) / dl
    tmin = np.nanmax(np.minimum(t1, t2), 1)
    tmax = np.nanmin(np.maximum(t1, t2), 1)
    if inside:
        t = np.where(tmax > 0, tmax, np.inf)
        axis = np.argmin(np.abs(np.maximum(t1, t2) - tmax[:, None]), 1)
        sign = -np.sign(dl[np.arange(N), axis])          # 朝内
    else:
        ok = (tmax >= tmin) & (tmin > 0)
        t = np.where(ok, tmin, np.inf)
        axis = np.argmin(np.abs(np.minimum(t1, t2) - tmin[:, None]), 1)
        sign = -np.sign(dl[np.arange(N), axis])          # 朝外（迎向射线）
    nl = np.zeros((N, 3))
    nl[np.arange(N), axis] = sign
    return t, nl @ R.T


lift = np.array([0, LIFT, 0])
room_t, room_n = box_hit(np.array([-0.757, 13.219, 0.717]) + lift, [31.713, 28.305, 28.591], inside=True)
best_t = room_t.copy()
best_n = room_n.copy()
emit = np.zeros(N)
boxes = [
    ([-10.906, 2.009, 1.846], [2.328, 7.905, 4.651], -0.195),
    ([-5.607, -0.754, -0.758], [1.970, 1.534, 3.955], 0.994),
    ([6.167, 0.857, 7.803], [3.927, 6.285, 3.687], 0.561),
    ([-2.017, 0.018, 6.124], [2.002, 4.566, 2.064], 0.333),
    ([2.291, -0.756, -2.621], [1.546, 1.552, 1.496], -0.286),
    ([-2.193, -0.369, -5.547], [3.875, 3.487, 2.986], 0.516),
]
for p, sc, ry in boxes:
    t, n = box_hit(np.array(p) + lift, sc, ry)
    m = t < best_t
    best_t[m] = t[m]; best_n[m] = n[m]; emit[m] = 0
lights = [
    ([-16.116, 14.37, 8.208], [0.1, 2.428, 2.739], 50),
    ([-16.109, 18.021, -8.207], [0.1, 2.425, 2.751], 50),
    ([14.904, 12.198, -1.832], [0.15, 4.265, 6.331], 17),
    ([-0.462, 8.89, 14.520], [4.38, 5.441, 0.088], 43),
    ([3.235, 11.486, -12.541], [2.5, 2.0, 0.1], 20),
    ([0.0, 20.0, 0.0], [1.0, 0.1, 1.0], 100),
]
for p, sc, k in lights:
    t, _ = box_hit(np.array(p) + lift, sc)
    m = t < best_t
    best_t[m] = t[m]; emit[m] = k

# 白色漫反射面受主点光源照明（900 cd，距离 28，衰减 2，无阴影）：L = E / π
P = D * best_t[:, None]
light = np.array([0.418, 16.199, 0.300]) + lift
Lv = light - P
dist = np.linalg.norm(Lv, axis=1)
ndl = np.clip(np.sum(best_n * Lv / dist[:, None], 1), 0, None)
fall = 1 / np.maximum(dist ** 2, 0.01) * np.clip(1 - (dist / 28) ** 4, 0, 1) ** 2
lum = np.where(emit > 0, emit, 900 * fall * ndl / np.pi)
rgb = np.repeat(lum[:, None], 3, 1) * 0.48          # scene.environmentIntensity


def srgb(h):
    c = np.array([int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)])
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


sky, ground = srgb("#fffaf5"), srgb("#b4a18c")
w = (0.5 * D[:, 1] + 0.5)[:, None]
rgb += 0.65 / np.pi * (ground * (1 - w) + sky * w)  # 半球光（漫反射等效辐亮度）
img = rgb.reshape(H, W, 3).astype(np.float32)

# PMREM 的 sigma 0.04 轻微模糊（水平方向按纬度放宽）
k = np.array([1, 4, 6, 4, 1], np.float32); k /= k.sum()
for _ in range(2):
    img = sum(np.roll(img, i - 2, 0) * k[i] for i in range(5))
    img = sum(np.roll(img, i - 2, 1) * k[i] for i in range(5))


def rgbe(a):
    m = a.max(-1)
    e = np.floor(np.log2(np.maximum(m, 1e-32))) + 1
    sc = np.where(m > 1e-32, 256.0 / np.exp2(e), 0)
    out = np.zeros(a.shape[:-1] + (4,), np.uint8)
    out[..., :3] = np.clip(a * sc[..., None], 0, 255).astype(np.uint8)
    out[..., 3] = np.where(m > 1e-32, e + 128, 0).astype(np.uint8)
    return out


OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "wb") as f:
    f.write(b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n" + f"-Y {H} +X {W}\n".encode())
    f.write(rgbe(img).tobytes())
print(OUT, img.mean(axis=(0, 1)), img.max())
