# STS2DEFECT

STS2DEFECT 是一个《杀戮尖塔 2》故障机器人选牌辅助面板。它读取推荐表、识别当前选牌奖励，并把牌组统计按推荐端口汇总出来，目标是帮助中文游戏环境下更快看懂“这张牌属于哪个端口、优先级是多少”。

当前项目是本地只读工具，不是自动游玩脚本。

## 功能

- **选牌推荐：** PySide6 置顶小面板显示奖励牌、英文 ID、置信度和推荐端口。
- **OCR 识别：** 实时截图模式优先使用 RapidOCR 识别中文卡名，再用推荐表里的中文名做模糊匹配；卡图模板匹配只作为备用方案。
- **STS2MCP 模式：** 保留只读读取 `card_reward` 的模式，适合已经安装 STS2MCP 且接口正常的环境。
- **牌组统计：** 读取本地 profile 下的 `saves/current_run.save`，每 2 秒刷新当前牌组数量、保存时间、未知牌、初始牌、诅咒牌和各推荐端口统计。
- **响应式 UI：** 普通置顶窗口，可缩放；不做透明覆盖层。

## 只读安全边界

这个项目的边界很明确：

- 只读取屏幕截图、STS2MCP 的本地 HTTP 状态、以及你选择的本地存档路径。
- 不会点击游戏、按键、拖拽或执行任何游戏操作。
- 不会修改存档、运行文件、配置文件或游戏目录。
- 实时截图识别默认不保存截图文件；只有手动运行带 `--debug-dir` 的 CLI 时才会输出调试材料。
- STS2MCP 模式只使用 `card_reward` 读取结果，不处理战斗、商店等已知不稳定状态。

## Windows 快速开始

要求：

- Windows 10/11。
- Python 3.12 或更新版本。
- 建议安装 Python 时勾选 `Add python.exe to PATH`。

首次安装：

```text
双击 install-windows.bat
```

日常启动：

```text
双击 run-panel.bat
```

启动后可以在 UI 中选择：

- 选牌推荐页：使用 OCR 截图识别，或切换到 STS2MCP 只读模式。
- 牌组统计页：选择你的 STS2 profile 目录，程序会记住上次路径。

更多 Windows 便携启动说明见 [docs/windows-portable.md](docs/windows-portable.md)。

## 手动命令

安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
```

启动面板：

```powershell
$env:PYTHONPATH = "src"
python -m sts2defect.cli run-panel data/recommendations/slay-the-spire-2-manual.json
```

校验推荐数据：

```powershell
$env:PYTHONPATH = "src"
python -m sts2defect.cli validate-data data/recommendations/slay-the-spire-2-manual.json
```

预览本地牌组快照：

```powershell
$env:PYTHONPATH = "src"
python -m sts2defect.cli preview-deck-snapshot "你的 STS2 profile 路径" data/recommendations/slay-the-spire-2-manual.json
```

运行测试：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## STS2 profile 路径

常见位置类似：

```text
C:\Users\<你的用户名>\AppData\Roaming\SlayTheSpire2\steam\<SteamID>\modded\profile1
```

是否使用 mod、Steam ID、profile 编号都会影响路径，所以应用里让用户自己选择，并记住上次选择。牌组统计只读取该目录下的 `saves/current_run.save`。

## STS2MCP

如果你安装了 STS2MCP，应用可以读取：

```text
http://localhost:15526/api/v1/singleplayer?format=json
```

当前只使用返回状态为 `card_reward` 的数据。由于 STS2MCP 在部分版本的战斗和商店界面可能报错，本项目不会依赖这些状态，也不会尝试调用任何写入或操作接口。

## OCR 识别说明

OCR 模式适合不想安装 mod 的情况。它会截取当前屏幕或标题包含 `Slay the Spire 2` 的窗口，识别选牌奖励卡名区域，再映射到推荐表中的卡牌 ID。

限制：

- 鼠标悬停 tooltip、遮挡、非选牌奖励页面会降低识别稳定性。
- 游戏语言建议使用中文，因为当前推荐表和 OCR 匹配以中文名为主。
- 首次 OCR 初始化会慢一些，之后会复用 session。

## 数据与发布卫生

仓库应保留源码、文档、测试 fixture 和正式推荐表；不要提交个人运行数据。

不要提交：

- 真实 STS2 profile、存档、回放和历史运行文件。
- 实时截图、微信长截图、OCR 裁剪图、debug 输出。
- 下载的卡图缓存或模板缓存。
- `.venv`、本地设置、日志、构建产物。

这些内容已经在 `.gitignore` 中屏蔽。当前本地已有样本不会被自动删除；发布前如果它们曾被加入 Git，需要先从索引中移除。

## 项目结构

```text
data/recommendations/      推荐数据 JSON
docs/                      设计、启动与识别说明
src/sts2defect/            Python 源码
tests/                     单元测试
tests/fixtures/            脱敏测试样本
```
