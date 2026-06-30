# 项目骨架实现计划

> 面向 AI 代理的工作者：按 TDD 小步执行。每个任务先写测试并确认失败，再写最小实现让测试通过。

**目标：** 建立《杀戮尖塔 2》辅助工具的最小 Python 项目骨架，让推荐数据校验、查询和卡牌库统计先可运行、可测试。

**架构：** 第一版只实现纯 Python 核心，不依赖 OpenCV 或 PySide。截图识别、页面识别和叠加层作为清晰接口保留，后续接入真实图像能力。

**技术栈：** Python 3.12、标准库 `unittest`、本地 JSON 数据。

---

## 文件结构

- `pyproject.toml`：项目元数据和包发现配置。
- `README.md`：当前阶段运行说明。
- `src/sts2defect/models.py`：共享数据模型。
- `src/sts2defect/recommendations.py`：推荐数据加载、校验、查询和统计。
- `src/sts2defect/cli.py`：最小命令行入口。
- `src/sts2defect/capture/`：截图模块接口。
- `src/sts2defect/recognition/`：页面和卡牌识别接口。
- `src/sts2defect/overlay/`：叠加层接口。
- `data/recommendations/slay-the-spire-2-manual.example.json`：推荐数据示例。
- `tests/test_recommendations.py`：推荐数据核心行为测试。

## 任务 1：推荐数据测试

- [ ] 创建 `tests/test_recommendations.py`。
- [ ] 测试有效推荐数据可以按卡牌名称查询类型和推荐指数。
- [ ] 测试同一卡牌重复出现时，卡牌库统计会保留重复推荐指数。
- [ ] 测试 `total` 与类型卡牌总数不一致时抛出数据校验错误。
- [ ] 运行 `python -m unittest discover -s tests -v`，确认因模块缺失失败。

## 任务 2：推荐数据核心实现

- [ ] 创建 `src/sts2defect/models.py`。
- [ ] 创建 `src/sts2defect/recommendations.py`。
- [ ] 实现 `RecommendationStore.from_file()`、`lookup()`、`summarize_cards()`。
- [ ] 运行 `python -m unittest discover -s tests -v`，确认测试通过。

## 任务 3：项目骨架和 CLI

- [ ] 创建 `pyproject.toml` 和 `README.md`。
- [ ] 创建模块接口目录：`capture`、`recognition`、`overlay`。
- [ ] 创建 `src/sts2defect/cli.py`，支持 `validate-data`。
- [ ] 创建推荐数据示例文件。
- [ ] 运行 CLI 校验示例 JSON。

## 验证

- [ ] `python -m unittest discover -s tests -v`
- [ ] `python -m sts2defect.cli validate-data data/recommendations/slay-the-spire-2-manual.example.json`
