# 选牌奖励视觉识别样本报告

本报告覆盖当前最小视觉识别器在 `data/samples/card-reward/1.png` 到
`7.png` 上的表现。

当前识别器仍是验证工具，不是 UI 功能。它只读取截图，使用 Spire Codex
卡图缓存做模板匹配，并可把调试材料写入
`data/samples/card-reward/debug-runs`。

## 识别方案

- 暂不使用 OCR：本地没有稳定 OCR 后端。
- 暂不使用中文标题渲染匹配：游戏字体、描边、背景会让结果不稳定。
- 当前使用卡图模板匹配：卡图不受中英文语言影响。
- 优先从截图中的奖励卡色块判断 3 选 1 或 4 选 1。
- 低分或低 margin 会标记为 `uncertain`，不会为了通过样本硬调阈值。

## 样本结果

| 样本 | 真实卡牌 | 识别结果 | 置信度 | 不确定项 |
| --- | --- | --- | --- | --- |
| `1.png` | 玻璃工艺 / 热修复 / 子程序 | 玻璃工艺 `GLASSWORK` / 热修复 `HOTFIX` / 子程序 `SUBROUTINE` | 1.000 / 1.000 / 1.000 | 无 |
| `2.png` | 热修复+ / 球状闪电 / 压缩 | 热修复 `HOTFIX` / 球状闪电 `BALL_LIGHTNING` / 压缩 `COMPACT` | 1.000 / 1.000 / 0.774 | 无 |
| `3.png` | 趁势打击 / 雷暴 / 高速脱离 | 趁势打击 `MOMENTUM_STRIKE` / 雷暴 `STORM` / 高速脱离 `BOOST_AWAY` | 1.000 / 0.581 / 1.000 | 无 |
| `4.png` | 球状闪电 / 骚动 / 扫荡射线 | 球状闪电 `BALL_LIGHTNING` / 骚动 `UPROAR` / 扫荡射线 `SWEEPING_BEAM` | 0.967 / 0.521 / 1.000 | slot 1: low score 0.323 |
| `5.png` | 劫掠 / 何人僭越 / 隐秘藏品 | 劫掠 `PILLAGE` / 何人僭越 `KNOW_THY_PLACE` / 隐秘藏品 `HIDDEN_CACHE` | 0.684 / 1.000 / 1.000 | 无 |
| `6.png` | 高速脱离+ / 全息影像 / 飞跃+ / 右侧遮挡牌 | 高速脱离 `BOOST_AWAY` / 全息影像 `HOLOGRAM` / 飞跃 `LEAP` / 飞剑回旋镖 `SWORD_BOOMERANG` | 0.707 / 0.719 / 0.676 / 0.531 | slot 3: low score 0.319 |
| `7.png` | 压缩 / 球状闪电 / 寒流 | 压缩 `COMPACT` / 球状闪电 `BALL_LIGHTNING` / 寒流 `COLD_SNAP` | 0.691 / 0.810 / 1.000 | 无 |

## 调试材料

每个 debug run 目录包含：

- `manifest.json`：机器可读的识别摘要。
- `slot-N-crop.png`：该槽位实际用于匹配的截图裁剪图。
- `slot-N-match-<ID>.png`：命中模板的卡图裁剪。
- `slot-N-alt-RANK-<ID>.png`：top alternatives 的模板卡图裁剪。

已生成的样本 manifest：

- `data/samples/card-reward/debug-runs/1/manifest.json`
- `data/samples/card-reward/debug-runs/2/manifest.json`
- `data/samples/card-reward/debug-runs/3/manifest.json`
- `data/samples/card-reward/debug-runs/4/manifest.json`
- `data/samples/card-reward/debug-runs/5/manifest.json`
- `data/samples/card-reward/debug-runs/6/manifest.json`
- `data/samples/card-reward/debug-runs/7/manifest.json`

## Tooltip 与鼠标悬停处理

`6.png` 展示了当前对 tooltip/悬停干扰的处理策略。识别器可以判断这是
4 选 1，并正确识别前三张牌；右侧卡牌被 tooltip 局部遮挡，因此虽然有一个
best match，但分数偏低，会被标记为 `uncertain`。

后续接入 UI 时，任意奖励槽位出现 `uncertain`，都不应直接展示确定推荐。
更合适的状态是提示用户“请移开鼠标后重新识别”，然后等待下一帧或下一次截图。
