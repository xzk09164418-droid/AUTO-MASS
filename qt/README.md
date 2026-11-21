# AUTO-MAS Qt 客户端

PySide6 + QML 重写的桌面前端，按「莱茵生命」PV 视觉组织。它只替代 Vue 前端：通过现有 HTTP 接口与 Python 后端通信，后端代码不改。

## 运行

```bash
uv pip install --python .venv/Scripts/python.exe -r qt/requirements.txt
.venv/Scripts/python.exe qt/main.py
```

| 参数 | 作用 |
| --- | --- |
| `--skip-boot` | 跳过启动动画 |
| `--no-backend` | 不探测、不拉起后端，只看界面 |
| `--section N` | 启动后直接进入第 N 个一级界面 |
| `--theme light/dark/system` | 主题，默认跟随系统 |
| `--motion reduced/standard/enhanced` | 动态效果挡位，默认沿用上次的选择；增强需要 3D 组件 |
| `--simulate-load N` | 不连后端，模拟一次耗时 N 秒的后端启动 |
| `--return-after MS` | 配合 `--section`，进入后 N 毫秒自动返回（自检用） |
| `--capture out.png --after 3000` | 定时截图后退出（自检用） |

## 动态效果挡位与 3D 增强组件

- **减少**：直接替换文字，无解密、呼吸、抽出等动效。
- **标准**（默认）：滚动文字、同步解密、页签下划线、确认弹窗、卡带呼吸与档案抽出。左下录像带串首尾相接循环（末张之后接第一张）：普通切换快速贴靠；越过首尾的那一步若是最后一步，用非线性减速 + 小回弹；滚轮每格排队走完，积压超过 2 步时加速追上；滑动期间暂停悬停抬起。
- **增强**使用原生 Qt Quick 3D 录像带。普通部门按标准版录像带的顺序排成一列，按 ↑/↓ 或 W/S 前后切换，Enter 读取，Esc 退出读取。
  托管管理按程序分列，←/→ 或 A/D 换程序。每列的录像带对应当前程序的实际分页（含逐个账号），↑/↓ 或 W/S 换页。读取时，点击右侧页签也会选中相应录像带。
  调度队列沿用多列阵列，横向换队列，纵向选队列项，读取后在表格中定位。两种多列阵列显示前后各 18 行、左右各 3 列。
  模型、灯光与镜头来自 `design/qt-demo/array.html` 的视觉基线。网格与预过滤环境光随客户端提供，模型或光照源更新后运行 `python qt/tools/bake_cassette.py` 重新生成。
  各部门复用同一个异步预热的场景。切换时外壳始终保留在实例表内，标签、玻璃与唱片跟随各自的录像带升起和落回。
  Windows x64 的 D3D11 首次启动使用与 Qt 版本匹配的预编译材质和字节码。材质或着色器更新后，在安装了增强组件的 Windows x64 环境运行 `python qt/tools/bake_array_shaders.py`，并更新 `qt/main.py` 中的缓存修订号。
  Qt Quick 3D 在 `PySide6-Addons` 里（下载约 161 MB，安装后约 420 MB），**默认不安装**：在设置里选「增强」时二次确认后下载（版本与 PySide6 一致）。
  切回其它挡位时不立即删除，只写入 `config/QtEnhancedRemove.flag`；退出程序、下次启动加载完毕并空闲后在后台删除；删除前切回增强则取消。
- 深色主题下增强阵列的录像带为炭黑色，只有选中抬起的那盒保持浅色；阵列上的文字区铺有柔边衬底。
- 托管管理、调度队列、调度中心的录像带唱片取所选脚本启动程序（exe）的图标；调度中心取任务当前运行（否则第一个）脚本。
- 选择的挡位保存在 `config/QtClient.json`，下次启动沿用（`--motion` 可临时指定）。

## 结构

| 文件 | 内容 |
| --- | --- |
| `main.py` | 入口，注入后端监督器 |
| `automas_qt/backend.py` | 探测 `/api/core/health`、校验 instanceId，必要时拉起 `main.py`，收集启动日志；`request()` 带实例标识调用后端接口 |
| `automas_qt/enhanced.py` | 3D 增强组件的下载、延后删除；动态效果挡位的保存 |
| `automas_qt/exeicon.py` | 从脚本启动程序（exe）取 256×256 图标，`image://exeicon/<路径>`；缓存到 `config/QtIconCache/`，取不到时用档案章占位 |
| `qml/Theme.qml` | PV 色板（浅色/深色） |
| `qml/BootSequence.qml` + `Tracks.js` | 启动动画，复刻 PV 0–27 秒段落；画面是 25fps 帧号的纯函数，便于逐帧校准 |
| `qml/DepartmentHub.qml` + `Departments.js` | 一级界面 01–10 部门索引，入场编排参考 PV 1:00–1:12 |
| `qml/SectionView.qml` | 二级界面：部门卡、录像带串、档案卡、铭牌、确认弹窗；方块与部门卡之间随机变形过渡 |
| `qml/ArchivePanel.qml` + `SectionData.js` | 档案卡：按功能分页的表单（`SectionData.js` 为未连后端时的演示数据） |
| `qml/Live.js` | 后端数据 → 档案卡条目；控件带配置键与保存目标，保存时只提交改过的字段 |
| `qml/CassetteChain.qml` | 录像带串：透视投影的半透明卡带，首尾相接循环 |
| `qml/RollText.qml` / `RollDigits.qml` | 滚动文字与逐位滚动 |
| `qml/ArchiveArray3D.qml` / `shaders/` / `IconDisc.qml` | 增强挡位的录像带阵列、实例材质和程序图标唱片 |
| `qml/BackendPanel.qml` | 后端启动中 / 失败面板 |
| `qml/Ledger.qml` | 底部刻度栏 |
| `WEB-PARITY.md` | 与网页版逐页的交互对照（含各控件的可用条件） |
| `qml/PageScale.qml` | 刻度翻页条：主页任务对象与各部门的长表格超出一页时用它翻页，不滚动 |
| `qml/SearchField.qml` | 二级界面右上的搜索框（Ctrl+F 聚焦）：托管管理按名称 / 账号筛选；其余部门匹配条目名、编号、账号、分页名与字段名，跳到对应卡片与分页，回车下一个、Shift+回车上一个 |
| `qml/RhineScrollBar.qml` | 统一滚动条：发丝轨道 + 方头滑块，悬停 / 拖动加粗转橙 |
| `assets/logos/` | 12 款默认标志（PNG / SVG）：录像带串里没有 exe 图标的卡带按部门显示 01–10，其余用 11 |
| `qml/MotionShift.qml` | 标准 ↔ 增强挡位切换过渡：定格画面模糊并压上挡位铭牌，等新画面就绪后斜线扫过揭开 |

## 一级界面

01 主页 · 02 托管管理 · 03 模拟器管理 · 04 调度队列 · 05 调度中心 · 06 本地控制 · 07 签到（含游戏社区） · 08 历史记录 · 09 游戏活动 · 10 设置

计划管理、资源商店不再提供。
