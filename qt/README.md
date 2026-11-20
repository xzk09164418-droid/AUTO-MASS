# AUTO-MAS Qt 客户端

PySide6 + QML 重写的桌面前端，按「莱茵生命」PV 视觉组织。它只替代 Vue 前端：通过现有 HTTP 接口与 Python 后端通信，后端代码不改。

## 运行

```bash
.venv/Scripts/python.exe -m pip install -r qt/requirements.txt
.venv/Scripts/python.exe qt/main.py
```

| 参数 | 作用 |
| --- | --- |
| `--skip-boot` | 跳过启动动画 |
| `--no-backend` | 不探测、不拉起后端，只看界面 |
| `--section N` | 启动后直接进入第 N 个一级界面 |
| `--theme light/dark/system` | 主题，默认跟随系统 |
| `--motion reduced/standard/enhanced` | 动态效果挡位，默认标准；增强需要 3D 组件 |
| `--simulate-load N` | 不连后端，模拟一次耗时 N 秒的后端启动 |
| `--return-after MS` | 配合 `--section`，进入后 N 毫秒自动返回（自检用） |
| `--capture out.png --after 3000` | 定时截图后退出（自检用） |

## 动态效果挡位与 3D 增强组件

- **减少**：直接替换文字，无解密、呼吸、抽出等动效。
- **标准**（默认）：滚动文字、同步解密、页签下划线、确认弹窗、卡带呼吸与档案抽出。
- **增强**：录像带串改用 Qt Quick 3D 绘制实体卡带。Qt Quick 3D 在 `PySide6-Addons` 里（下载约 161 MB，安装后约 420 MB），**默认不安装**：
  在设置里选「增强」时二次确认后下载（版本与 PySide6 一致）；切回其它挡位时直接删除。
  本次运行已加载过 3D 模块时文件被占用，会写入 `config/QtEnhancedRemove.flag`，下次启动加载 Qt 之前补删。

## 结构

| 文件 | 内容 |
| --- | --- |
| `main.py` | 入口，注入后端监督器 |
| `automas_qt/backend.py` | 探测 `/api/core/health`、校验 instanceId，必要时拉起 `main.py`，收集启动日志；`request()` 带实例标识调用后端接口 |
| `automas_qt/enhanced.py` | 3D 增强组件的下载、删除与启动补删 |
| `qml/Theme.qml` | PV 色板（浅色/深色） |
| `qml/BootSequence.qml` + `Tracks.js` | 启动动画，复刻 PV 0–27 秒段落；画面是 25fps 帧号的纯函数，便于逐帧校准 |
| `qml/DepartmentHub.qml` + `Departments.js` | 一级界面 01–10 部门索引，入场编排参考 PV 1:00–1:12 |
| `qml/SectionView.qml` | 二级界面：部门卡、录像带串、档案卡、铭牌、确认弹窗；方块与部门卡之间随机变形过渡 |
| `qml/ArchivePanel.qml` + `SectionData.js` | 档案卡：按功能分页的表单，字段对齐后端配置；托管管理已读取实时数据（暂只读） |
| `qml/CassetteChain.qml` / `Chain3D.qml` | 录像带串：标准挡位为透视投影的 2D 卡带，增强挡位为 Qt Quick 3D 实体卡带 |
| `qml/RollText.qml` / `RollDigits.qml` | 滚动文字与逐位滚动 |
| `qml/BackendPanel.qml` | 后端启动中 / 失败面板 |
| `qml/Ledger.qml` | 底部刻度栏 |

## 一级界面

01 主页 · 02 托管管理 · 03 模拟器管理 · 04 调度队列 · 05 调度中心 · 06 本地控制 · 07 签到（含游戏社区） · 08 历史记录 · 09 游戏活动 · 10 设置

计划管理、资源商店不再提供。
