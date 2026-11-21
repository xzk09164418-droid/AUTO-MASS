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
- **增强**：托管管理与调度队列换成多列档案阵列（`ArchiveArray3D.qml`，以 `design/qt-demo/array.html` 为基线，按 LBEILC/RhineLabUI 移植，模型见 `assets3d/`，MIT）；
  点开方块后方块直接消失，阵列按原项目进出场的节奏（ArchiveScene.reveal）从画面右上方沿录像带长边滑入、向左下落位；返回时模糊淡出；
  换选中时原来抬起的那盒（带标签与完整外观）按自己的弹簧落回，再选回时接着它的高度；文字层的淡入、分隔线展开等时序取自原项目 style.css。读取档案时录像带抬起、玻璃变清晰，内部是印着启动程序图标的唱片（参考 Rhine Music Database 的封面录像带）。
  画面按演示基线：环境光照（RoomEnvironment + 半球光烘成的 `assets3d/room-env.hdr`，由 `tools/make_room_env.py` 生成）、主光与补光、软阴影、透射磨砂外壳与竖向渐变、雾与景深。
  阵列的波浪、呼吸、涟漪、悬停与飞入在顶点着色器（`qml/shaders/arraypart.vert`）里计算，CPU 每帧只更新弹簧、镜头和少量 uniform。
  后台预加载限流：只在索引页、用户停止操作 2.5 秒后才开始，分「解析阵列 → 索引之下预渲染 → 解析选中的那盒」三步，每步都要再等空闲 1 秒，
  有操作就顺延；3D 相关 DLL 在启动时由后台线程预先映射，渲染管线缓存存到 `config/QtPipelineCache.bin`。其它部门的录像带串与标准挡位相同。
  实例范围与演示相同（左右各 3 列、前后各 18 行），以阵列当前滑到的位置为中心：切换行列时边缘随平移移出后才卸下。
  Qt Quick 3D 在 `PySide6-Addons` 里（下载约 161 MB，安装后约 420 MB），**默认不安装**：在设置里选「增强」时二次确认后下载（版本与 PySide6 一致）。
  切回其它挡位时不立即删除，只写入 `config/QtEnhancedRemove.flag`；退出程序、下次启动加载完毕并空闲后在后台删除；删除前切回增强则取消。
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
| `qml/ArchiveArray3D.qml` / `shaders/` / `IconDisc.qml` | 增强挡位的多列档案阵列（托管管理、调度队列）；阵列部件着色器；程序图标唱片 |
| `qml/BackendPanel.qml` | 后端启动中 / 失败面板 |
| `qml/Ledger.qml` | 底部刻度栏 |
| `WEB-PARITY.md` | 与网页版逐页的交互对照（含各控件的可用条件） |
| `qml/PageScale.qml` | 刻度翻页条：主页任务对象与各部门的长表格超出一页时用它翻页，不滚动 |

## 一级界面

01 主页 · 02 托管管理 · 03 模拟器管理 · 04 调度队列 · 05 调度中心 · 06 本地控制 · 07 签到（含游戏社区） · 08 历史记录 · 09 游戏活动 · 10 设置

计划管理、资源商店不再提供。
