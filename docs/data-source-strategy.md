# 数据源策略

## 1. 结论

Spire Codex 可以作为项目的卡牌基础数据来源，用来补充：

- 稳定卡牌 ID。
- 英文卡名。
- 中文卡名。
- 卡牌类型、稀有度、费用等基础字段。
- 标准卡图 URL。

用户提供的推荐表仍然是推荐指数的唯一来源。推荐表决定卡牌属于哪一种自定义类型，以及在该类型中的排序位置。

## 2. 为什么需要 Spire Codex

当前输入存在语言差异：

- 推荐表使用英文卡图。
- 实际游戏通常使用中文。

如果只按卡牌名称匹配，英文推荐表中的 `Beam Cell` 很难直接匹配中文游戏截图中的「光束射线」。Spire Codex API 提供稳定的 `id` 字段，可以把英文名和中文名归一到同一张卡牌。

建议内部统一使用：

```text
cardId -> 推荐数据
```

名称只作为别名：

```text
Beam Cell -> BEAM_CELL
光束射线 -> BEAM_CELL
```

## 3. API 参考

开发者页面：

```text
https://spire-codex.com/zhs/developers
```

基础接口：

```text
GET https://spire-codex.com/api/cards
```

Defect 卡牌示例：

```text
GET https://spire-codex.com/api/cards?color=defect&lang=eng
GET https://spire-codex.com/api/cards?color=defect&lang=zhs
```

开发者页说明该 API 无需鉴权，限频为 60 requests/minute，并支持多语言参数。

常用字段：

| 字段 | 用途 |
| --- | --- |
| `id` | 稳定卡牌 ID，推荐作为内部主键 |
| `name` | 当前语言下的卡牌名称 |
| `type_key` | 英文类型键，例如 `Attack`、`Skill`、`Power` |
| `rarity_key` | 英文稀有度键 |
| `cost` | 费用 |
| `image_url_card` | 标准完整卡图 |
| `image_url_card_upg` | 升级后标准完整卡图 |

## 4. 推荐数据格式调整

推荐数据应支持以下字段：

```json
{
  "id": "BEAM_CELL",
  "name": "Beam Cell",
  "names": {
    "eng": "Beam Cell",
    "zhs": "光束射线"
  },
  "aliases": ["Beam Cell", "光束射线"],
  "rank": 1,
  "total": 8,
  "recommendIndex": "1/8"
}
```

兼容策略：

- 旧格式只有 `name` 时仍然可用。
- 新格式优先使用 `id` 作为主键。
- `name`、`names.*`、`aliases.*` 都注册为可查询别名。

## 5. 使用边界

Spire Codex 不应替代用户推荐表，因为它只提供卡牌资料，不知道用户自定义的「攻击接口」「防御接口」「零费接口」等分类和排序。

它适合用于：

- 建立中英文名称映射。
- 下载或缓存标准卡图。
- 辅助人工录入推荐表。
- 给 OCR 结果做名称纠错。

它暂时不用于：

- 自动生成推荐指数。
- 替代用户提供的排序图。
- 实时联网识别游戏画面。
