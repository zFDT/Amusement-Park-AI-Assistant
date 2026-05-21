# 游园AI助手 - 攻略采集与AI分析体系优化 PRD

> 版本：v1.0 | 日期：2026-05-21 | 作者：产品 & 技术团队

---

## 目录

1. [问题诊断](#一问题诊断)
2. [优化方案设计](#二优化方案设计)
3. [AI Prompt 优化详情](#三ai-prompt-优化详情)
4. [数据库变更](#四数据库变更)
5. [实施步骤](#五实施步骤)
6. [验证清单](#六验证清单)

---

## 一、问题诊断

通过分析 `distill.py → strategy_service.py → prompt_builder.py → ai_service.py` 完整链路，发现 **5 个核心瓶颈**：

### 1.1 攻略分类维度单一

**现状**：`structured_summary` 仅含 `is_useful` 布尔值，无法区分攻略类型。

**影响**：AI 规划时注入的 5 条攻略可能全部是"纯晒图"，对规划无帮助。用户无法按类型筛选攻略。

**根因**：`distill.py` 的 System Prompt 未要求 AI 输出攻略类型标签。

### 1.2 项目关联不可靠

**现状**：`mentioned_attractions` 依赖 AI 自由发挥，`collect.py` 的 `_extract_mentioned_attractions` 仅做简单字符串匹配。

**影响**：AI 可能编造不存在的项目名（"灰熊山谷"≠"灰熊山极速矿车"），攻略与实际项目无法对齐。

**根因**：AI 提炼时缺少项目名标准化约束，无白名单校验。

### 1.3 攻略注入策略粗糙

**现状**：`strategy_service.py` 按点赞数排序取前 5 条，仅过滤 `is_useful=false`。

**影响**：缺少多样性保障（5 条全同类型）、缺少时效性权重、未与用户偏好关联。

**根因**：注入策略是"一刀切"的静态排序，缺少上下文感知。

### 1.4 提炼 Prompt 无乐园差异化

**现状**：`distill.py` 的 System Prompt 是通用迪士尼提示。

**影响**：AI 提炼的建议不适用于特定乐园（香港迪士尼比上海小得多，路线策略不同）。

**根因**：提炼 Prompt 缺少乐园规模、园区分布、明星项目列表等差异化上下文。

### 1.5 采集关键词固定

**现状**：每个乐园仅 4-5 个固定搜索关键词。

**影响**：漏掉大量长尾攻略（雨天攻略、亲子攻略、节日攻略等），覆盖率不足。

**根因**：关键词列表硬编码，无动态扩展机制。

---

## 二、优化方案设计

### 2.1 攻略多维分类体系

在 `structured_summary` JSON 中新增两个字段：

```json
{
  "is_useful": true,
  "strategy_type": "route_plan",
  "strategy_subtypes": ["first_time", "morning_rush"],
  "mentioned_attractions": ["星战极速穿梭", "小小世界"],
  "suggested_route": "...",
  "tips": "...",
  "summary": "..."
}
```

**`strategy_type` 枚举**（9 类）：

| 值 | 中文标签 | 说明 |
|---|---------|------|
| `route_plan` | 路线规划 | 含时间安排的游玩顺序 |
| `queue_tips` | 排队技巧 | 排队/快通/时间管理 |
| `food_dining` | 餐饮推荐 | 餐厅推荐/避雷 |
| `photo_spot` | 拍照打卡 | 机位分享/拍照点 |
| `family_kids` | 亲子攻略 | 带娃专项 |
| `show_parade` | 表演巡游 | 烟花/巡游/剧场 |
| `hidden_gem` | 隐藏玩法 | 冷门项目/彩蛋 |
| `general_review` | 游园分享 | 综合性游记 |
| `ticket_deal` | 票务优惠 | 票务/年卡信息 |

**`strategy_subtypes` 场景标签**（可多选）：

| 维度 | 标签 |
|------|------|
| 天气/节日 | `rainy_day`, `summer_heat`, `christmas`, `halloween` |
| 人群适配 | `with_toddler`, `with_elderly`, `with_friends`, `solo` |
| 经验层级 | `first_time`, `frequent` |
| 预算倾向 | `money_saving`, `luxury` |
| 时段策略 | `morning_rush`, `evening_route` |

### 2.2 项目名标准化与白名单约束

**实现方案**：
1. `distill.py` 加载对应乐园的 `app/data/{park_id}.json`，提取所有 `attractions[].name` 作为白名单
2. System Prompt 中注入完整项目列表和约束指令
3. AI 输出后，`_validate_mentioned_attractions()` 校验并剔除不在白名单的名称
4. 内置别名映射表（如"灰熊山谷"→"灰熊山极速矿车"）

### 2.3 上下文感知的攻略注入策略

**多路召回 + 重排序架构**：

```
路 1（热门）: 点赞 Top 10 ─────────→ 权重 0.30
路 2（多样）: 每种 type Top 2 ──────→ 权重 0.30
路 3（偏好）: 用户偏好匹配 ─────────→ 权重 0.25
路 4（时效）: 最近 60 天 ──────────→ 权重 0.15
                                       ↓
                              去重 + 多样性保障
                              （至少 3 种 type）
                                       ↓
                              格式化输出 Top 5
```

**用户偏好 → 攻略类型映射**：

| 用户偏好 | 匹配的攻略类型 |
|---------|-------------|
| `thrill_rides` | `queue_tips`, `route_plan` |
| `family_rides` | `family_kids`, `route_plan` |
| `shows` | `show_parade` |
| `character_meet` | `photo_spot`, `hidden_gem` |
| `photography` | `photo_spot` |
| `dining` | `food_dining` |
| `parades` | `show_parade` |

### 2.4 攻略采集关键词动态生成

**三级关键词体系**：

| 级别 | 来源 | 数量 | 示例 |
|------|------|------|------|
| 基础 | `_BASE_KEYWORDS` | 4-5 | "香港迪士尼攻略" |
| 场景 | `_SCENE_KEYWORD_TEMPLATES` | 10-12 | "香港迪士尼雨天攻略" |
| 项目 | 乐园 JSON Top 10 项目 | 10 | "香港迪士尼 灰熊山极速矿车" |

**CLI 参数**：`--keyword-scope` 支持 `basic` / `extended` / `full`

### 2.5 System Prompt 攻略段格式化增强

**旧格式**：
```
- 《标题》：摘要文本...
```

**新格式**：
```
共 5 条相关攻略：
  1. [路线规划]《一日游完美路线》 | 涉及项目：星战极速穿梭、小小世界 | 路线：上午明日世界→下午幻想世界 | 技巧：上午10点前星战排队最短
  2. [排队技巧]《暑期高效排队心得》 | 涉及项目：灰熊山极速矿车、迷离大宅 | 技巧：单人通道可节省50%时间
  ...
```

引导 AI 在回复中引用攻略：*"根据其他游客的经验，上午 10 点前星战极速穿梭排队最短..."*

---

## 三、AI Prompt 优化详情

### 3.1 提炼 Prompt（distill.py）

**优化前**：通用迪士尼提示，无乐园上下文。

**优化后**：包含以下差异化信息：
- 🏰 乐园规模与特色（香港小而精致、上海大而丰富）
- 🗺️ 园区列表（如香港 7 大园区名称）
- 🎢 项目名白名单（完整列表，AI 只能从中选择）
- 🏷️ 分类输出指令（strategy_type + strategy_subtypes）
- ⚠️ 约束指令（不要编造项目名，无法确定则留空）

### 3.2 规划 System Prompt（prompt_builder.py）

**新增原则**：
- 原则 9：乐园差异化原则（香港可跨区 / 上海需按区域集中）
- 原则 10：引用攻略建议（如果适用，标注来源）

**攻略段格式**：从无序列表 → 序号列表 + 引导语

### 3.3 对话上下文（chat.py）

**变更**：`get_strategy_snippets()` 调用时传入 `preferences` 参数，启用偏好匹配召回。

---

## 四、数据库变更

| 变更 | 表 | 说明 |
|------|---|------|
| 新增列 | `strategies.search_vector` | `TSVECTOR` 类型，全文搜索 |
| GIN 索引 | `strategies` | `ix_strategies_search_vector` |
| 复合索引 | `strategies` | `ix_strategies_park_active_likes` |
| 复合索引 | `strategies` | `ix_strategies_park_active_date` |
| 触发器 | `strategies` | INSERT/UPDATE 时自动更新 `search_vector` |
| 连接池 | PostgreSQL | `pool_size=10, max_overflow=20` |

> 注：`strategy_type` 和 `strategy_subtypes` 存储在现有 `structured_summary` JSON 列中，无需新增列。旧数据缺失字段时，代码做默认值降级（`strategy_type` → `general_review`）。

---

## 五、实施步骤

### Phase 0：攻略体系核心优化 ✅ 已完成

| # | 步骤 | 文件 | 状态 |
|---|------|------|------|
| A1 | 乐园差异化 Prompt + 项目白名单 | `distill.py` | ✅ |
| A2 | 分类体系扩展（strategy_type + subtypes） | `distill.py` | ✅ |
| A3 | 多路召回 + 重排序 | `strategy_service.py` | ✅ |
| A4 | 关键词动态扩展 | `collect.py` | ✅ |
| A5 | DB TSVECTOR + 索引 + 迁移脚本 | `models/park.py`, `migrate_phase1.py` | ✅ |
| A6 | prompt_builder 攻略段结构化 | `prompt_builder.py` | ✅ |

### Phase 1：基础设施优化 ✅ 已完成

| # | 步骤 | 文件 | 状态 |
|---|------|------|------|
| B1 | 前端三态统一组件 | `StateWrapper.tsx` | ✅ |
| B2 | 路由懒加载 | `App.tsx`（已有） | ✅ |
| B3 | Store 版本号 + 迁移 | `sessionStore.ts` | ✅ |
| B4 | Redis AOF 持久化 | `docker-compose.yml` | ✅ |
| B5 | PG 连接池配置 | `database.py` | ✅ |
| B6 | JSON 格式化日志 | `logging.py` | ✅ |

### Phase 2：产品功能增强

| # | 步骤 | 文件 | 状态 |
|---|------|------|------|
| C1 | 攻略 API 增加类型/项目筛选 | `routes/strategies.py` | 📋 |
| C2 | 智能重规划（进度变化检测） | `chat.py` | 📋 |
| C3 | 双园对比 API | 新建 `routes/compare.py` | 📋 |
| C4 | 可视化路线地图 | 新建 `components/map/` | 📋 |
| C5 | 排队推送通知 | `waittime_service.py` + 前端 | 📋 |

---

## 六、验证清单

### 攻略体系
- [ ] 运行 `python -m scripts.strategy_collector.collect --park hongkong_disney --limit 5`，检查 `strategy_type` 非空
- [ ] 运行 `python -m scripts.strategy_collector.redist --park hongkong_disney --force --limit 5`，验证旧攻略重新提炼后字段完整
- [ ] 查询 `SELECT structured_summary->'strategy_type' FROM strategies WHERE park_id='hongkong_disney' LIMIT 5`
- [ ] 调用 `POST /api/sessions`，检查 AI 回复是否引用攻略内容

### 基础设施
- [ ] `docker compose down && docker compose up -d` 后 Redis 数据仍在（AOF）
- [ ] `LOG_FORMAT=json` 启动后端，日志输出为 JSON 格式
- [ ] 前端断网后打开攻略页，显示 Error 状态 + 重试按钮

### 数据库
- [ ] 运行 `python -m scripts.migrate_phase1`，无错误
- [ ] `SELECT count(*) FROM strategies WHERE search_vector IS NOT NULL` 返回 > 0
