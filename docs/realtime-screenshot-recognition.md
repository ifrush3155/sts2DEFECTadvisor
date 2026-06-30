# 实时截图识别最小验证

本功能用于把“样本图片识别”推进到“当前屏幕截图识别”。它只读取屏幕像素，
不会接入 UI，不会覆盖游戏画面，也不会对游戏执行任何操作。

## 命令

全屏截图并识别：

```powershell
$env:PYTHONPATH="src"
python -m sts2defect.cli recognize-card-reward-screen `
  --cache-dir data\samples\card-reward\debug-cache `
  --screenshot-dir data\samples\card-reward\live-screens `
  --debug-dir data\samples\card-reward\debug-runs
```

按窗口标题截图并识别：

```powershell
$env:PYTHONPATH="src"
python -m sts2defect.cli recognize-card-reward-screen `
  --window-title "Slay the Spire 2" `
  --cache-dir data\samples\card-reward\debug-cache `
  --screenshot-dir data\samples\card-reward\live-screens `
  --debug-dir data\samples\card-reward\debug-runs
```

输出包括：

- 截图保存路径。
- 识别到的卡牌中文名。
- 英文 ID。
- confidence、score、margin。
- `uncertain` 项。
- 可选 debug manifest 路径。

## 限制

- `--window-title` 目前只支持 Windows。
- 窗口标题是“包含匹配”，例如 `Slay the Spire 2` 可以匹配完整窗口标题。
- 窗口截图读取的是当前屏幕像素，游戏窗口需要可见。
- 如果窗口最小化、被其他窗口遮挡、鼠标悬停 tooltip 遮挡卡面，识别可能会变成
  `uncertain`。
- 如果当前画面不是选牌奖励页，识别器仍可能输出低分候选，但这些候选应全部视为
  `uncertain`，不能作为推荐依据。
- 当前仍是最小验证 CLI，不适合直接作为 UI 推荐来源；接 UI 前应先收集更多实时
  截图样本。

## 建议测试方式

1. 进入游戏选牌奖励页面。
2. 移开鼠标，避免 tooltip 遮挡卡面。
3. 运行窗口截图命令。
4. 检查输出和 `debug-runs` 中的槽位裁剪图。
5. 如果出现 `uncertain`，优先检查裁剪图是否被 tooltip、鼠标悬停放大或窗口遮挡影响。

## Benchmark

可以用 benchmark 命令区分冷启动耗时和热路径耗时：

```powershell
$env:PYTHONPATH="src"
python -m sts2defect.cli benchmark-card-reward-recognition `
  --image data\samples\card-reward\7.png `
  --cache-dir data\samples\card-reward\debug-cache `
  --runs 3
```

也可以不传 `--image`，让命令先截图再 benchmark：

```powershell
$env:PYTHONPATH="src"
python -m sts2defect.cli benchmark-card-reward-recognition `
  --window-title "Slay the Spire 2" `
  --cache-dir data\samples\card-reward\debug-cache `
  --screenshot-dir data\samples\card-reward\live-screens `
  --runs 3
```

输出字段含义：

- `screenshot`：截图耗时。
- `metadata`：从 Spire Codex 获取卡牌 metadata 的耗时。
- `ensure_templates`：确认本地卡图模板缓存的耗时。
- `preload_features`：把模板卡图预处理成特征的耗时。
- `single_hot_recognition`：模板已预加载后，第一次识别耗时。
- `hot_recognition_average`：模板已预加载后，多次识别平均耗时。

当前样本 `7.png` 的一次实测结果：

- `metadata`: 3.811s
- `ensure_templates`: 0.092s
- `preload_features`: 4.420s
- `single_hot_recognition`: 0.819s
- `hot_recognition_average`: 0.792s over 5 runs

因此，冷启动 CLI 仍是秒级；未来 UI/后台常驻模式应复用 `RecognitionSession`，
避免每次重新读取 576 张模板图。热路径目标是接近 1 秒以内，目前样本已达到。
