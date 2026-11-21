# 第三方来源与许可证

## AUTO-MAS

- 上游 https://github.com/AUTO-MAS-Project/AUTO-MAS
- 版权归 DLmaster361、AUTO-MAS Team 及其贡献者所有。
- 本仓库继承后端、原 Web 前端、调度、配置管理及相关工具代码。原始版权声明保留在文件头中。
- 许可证全文见根目录 LICENSE（GNU Affero General Public License v3）。源文件中含“v3 或更新版本”的条款按原声明保留。
- AUTO-MASS 0.1.0 为独立派生版本，改动包含 General 入口收敛、本地远程桌面、外部占用、热键控制与 Qt 界面。

## windows-script-scheduler

热键启停的设计参考了维护者的 [windows-script-scheduler](https://github.com/xzk09164418-droid/windows-script-scheduler) 项目。

## BetterGI

- 上游 https://github.com/babalae/better-genshin-impact
- Windows Child Session 部分参考或复用了 BetterGI 的本地远程桌面实现，相关代码位于 res/ChildSessionHost。
- 上游许可证为 GPL-3.0，全文保存于 licenses/BetterGI-GPL-3.0.txt。原文件中的声明与作者标注继续保留。

## RhineLabUI

- 上游 https://github.com/LBEILC/RhineLabUI
- Qt 增强阵列和相关模型参考该项目，资源位于 qt/assets3d 与 design/qt-demo/assets。
- Copyright (c) 2026 LBEILC，MIT 许可证全文分别保存在上述资源目录的 RhineLabUI-LICENSE.txt。

## MiSans

- 字体及分片信息见 design/qt-demo/vendor/misans/NOTICE.md，发行时应连同字体资源保留该声明。

各依赖库继续适用其自带许可证。作者同意 fork 的沟通不替代这些许可证和署名要求。发布构建时应同时提供与其对应的源代码和构建说明。

## 7-Zip 自解压封装

Qt 便携包使用 7-Zip 的 7z.sfx 自解压模块，Copyright (C) 1999-2026 Igor Pavlov。
许可证见 licenses/7-Zip-LICENSE.txt；上游源码与下载：https://www.7-zip.org/ 。自解压仅展开文件，不替用户修改系统设置。

### Three.js（Qt 美术参考页）

版本 0.184.0，MIT 许可证。所需模块位于 design/qt-demo/vendor/three，完整许可证见该目录 LICENSE。
