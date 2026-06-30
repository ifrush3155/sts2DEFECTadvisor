# Windows 便携启动

这个方案不做单文件 exe。它把运行环境放在项目目录下的 `.venv`，以后双击 `run-panel.bat` 启动 PySide UI。

## 第一次安装

1. 安装 Python 3.12 或更新版本，并勾选 `Add python.exe to PATH`。
2. 在项目根目录双击 `install-windows.bat`。
3. 安装结束后，双击 `run-panel.bat` 启动。

也可以手动执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
```

## 日常启动

双击：

```text
run-panel.bat
```

脚本会执行等价命令：

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m sts2defect.cli run-panel data\recommendations\slay-the-spire-2-manual.json
```

如果 `.venv` 不存在，脚本会尝试使用系统 `python`，但推荐先运行 `install-windows.bat`。

## 功能边界

- 只读读取本地存档和 STS2MCP card_reward。
- OCR 截图识别不点击游戏、不写游戏文件。
- UI 是普通置顶窗口，不做透明覆盖层。
- 实时截图识别默认不保存截图文件。

## 常见报错

### Python was not found

没有安装 Python，或没有加入 PATH。安装 Python 3.12+ 后重新运行 `install-windows.bat`。

### PySide6 is not installed

依赖没有装完整。重新运行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
```

### rapidocr_onnxruntime is not installed

OCR 依赖没有装完整。重新运行 `install-windows.bat`。如果网络慢，可以换国内镜像源后再装。

### onnxruntime 或 DLL 加载失败

通常是 Windows 运行库缺失。安装 Microsoft Visual C++ Redistributable 后重试。

### window not found: Slay the Spire 2

截图来源选择了窗口标题，但游戏窗口标题没有匹配到。可以切到全屏截图，或确认窗口标题里包含 `Slay the Spire 2`。

### 第一次 OCR 较慢

第一次会初始化 OCR 模型，后续热路径会复用同一个 OCR session。

## 测试启动命令

不打开 UI，只检查 bat 是否能进入 CLI：

```powershell
cmd /c run-panel.bat --help
```
