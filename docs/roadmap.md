# 游园助理 - 后续规划与建议

**更新日期**：2026-05-18

---

## 当前状态（MVP 已完成）

- [x] 香港迪士尼乐园支持（50 个项目数据）
- [x] 游前规划表单（日期/人员/偏好/体力）
- [x] 对话式 AI 路线推荐（Claude API，SSE 流式输出）
- [x] 实时排队时间（queue-times.com，5 分钟缓存）
- [x] 用户自定义 AI Key + 代理地址
- [x] 小红书攻略采集器（注入 AI 上下文）
- [x] 数据库模型（Park / Attraction / Strategy）
- [x] Session 管理（Redis，24 小时有效）

---

## Phase 2 — 体验完善（建议 2-4 周）

### P0 必做

- [ ] **前端 TypeScript 编译验证**：运行 `yarn build` 确认无类型错误，修复潜在问题
- [ ] **端到端联调**：Docker Compose 启动后完整走一遍规划→对话→排队时间刷新流程
- [ ] **错误处理完善**：AI Key 无效时给出友好提示；queue-times.com 不可用时降级到历史均值
- [ ] **移动端适配验证**：在真实手机浏览器上测试，修复布局问题（游园场景主要用手机）

### P1 重要

- [ ] **地图可视化**：在对话界面嵌入香港迪士尼园区地图，标注各项目位置和当前推荐路线
  - 方案：使用乐园公开地图图片 + SVG 标注层，点击项目气泡查看排队时间
- [ ] **WaitTimePanel 显示中文名**：目前排队面板显示的是 queue-times.com 的英文 ID，需要映射到中文名
  - 实现：在 `Attraction` 表中存储 `queue_times_ride_id`，前端请求时一并返回中文名
- [ ] **路线完成标记**：用户可以标记某个项目已完成，AI 后续规划自动排除
- [ ] **快捷问题优化**：ChatInput 的快捷提问按钮根据当前时间和已完成项目动态生成

### P2 锦上添花

- [ ] **表演/巡游时间提醒**：在路线中插入花车巡游、烟花秀等固定时间节目，提前提醒
- [ ] **餐厅推荐**：整合园内餐厅信息，AI 可推荐适合当前位置和人员构成的餐厅
- [ ] **天气集成**：接入天气 API，雨天自动优先推荐室内项目
- [ ] **用户手动上报排队时间**：允许用户修正实时数据，提升准确性

---

## Phase 3 — 扩展（建议 1-2 个月后）

- [ ] **上海迪士尼乐园支持**：数据已有，主要是 queue-times.com park_id=30 验证和中文名映射
- [ ] **PWA 支持**：添加 `manifest.json` 和 Service Worker，让用户可以"安装"到手机桌面，离线访问基础功能
- [ ] **用户账号系统**：可选注册，保存历史游园记录，跨设备同步
- [ ] **更多乐园**：环球影城（北京/上海）、海昌海洋公园等，queue-times.com 均有数据

---

## Phase 4 — 商业化（长期）

- [ ] **景区合作版**：为景区提供定制化版本，对接官方实时数据 API，品牌定制
- [ ] **会员订阅**：高级功能（历史数据分析、多设备同步、优先 AI 响应）
- [ ] **APP 开发**：React Native 或 Flutter，支持离线地图、GPS 定位、推送提醒

---

## 技术建议

### 近期优先处理

**1. WaitTimePanel 中英文映射**

目前排队面板显示的是 queue-times.com 的数字 ID（如 `3822`），用户看不懂。
解决方案：在 `hongkong_disney.json` 中已有 `queue_times_ride_id` 字段，后端 `/api/waittimes/{park_id}` 接口返回时 JOIN 一下 `attractions` 表，把 `attraction_id` 替换为中文名。

**2. 前端构建验证**

```bash
cd frontend && yarn build
```

目前代码未经过完整 TypeScript 编译检查，可能有类型错误。建议在联调前先跑一遍 build，修复所有 TS 错误。

**3. AI 响应格式稳定性**

当前 route 解析依赖 AI 输出固定的 ` ```route ``` ` 代码块格式，偶尔 AI 可能不输出或格式略有偏差。
建议：在 `prompt_builder.py` 中加强格式约束，或在解析失败时给前端发送一个 `route_parse_failed` 事件，前端保持上一次路线不变。

**4. 攻略采集定期化**

小红书攻略数据是提升 AI 推荐质量的关键。建议：
- 服务器上用 cron 每周执行一次采集脚本
- 采集前检查数据库中已有条数，避免重复采集
- 可以加一个简单的管理接口 `GET /api/admin/strategies/count` 查看当前数据量

**5. 考虑 Prompt Caching**

当前每次对话都重新构建完整 System Prompt（含排队数据 JSON），token 消耗较大。
Anthropic 支持 Prompt Caching，对 System Prompt 中不变的部分（乐园信息、规划原则）加 `cache_control` 标记，可以节省 90% 的 token 费用。
参考：[Anthropic Prompt Caching 文档](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)

### 架构层面

**6. 考虑引入 Background Task 处理排队数据**

目前排队数据是用户请求时按需拉取（有 Redis 缓存）。更好的方案是后台定时任务主动刷新，用户请求时直接读缓存，响应更快。
FastAPI 内置 `BackgroundTasks`，或用 APScheduler 实现定时刷新。

**7. 日志和监控**

上线前建议加上：
- 结构化日志（`structlog` 或 Python `logging` + JSON formatter）
- 请求耗时记录（特别是 AI 首字符响应时间）
- 简单的错误告警（可以用 Telegram Bot 发送异常通知，成本极低）

---

## 已知问题和风险

| 问题 | 风险等级 | 说明 |
| --- | --- | --- |
| queue-times.com 数据延迟 | 中 | 数据有 5-15 分钟延迟，非官方来源，可能不准确 |
| AI 路线格式不稳定 | 中 | 偶尔 AI 不输出 route 代码块，前端路线不更新 |
| 小红书采集依赖登录状态 | 低 | Cookie 过期需重新登录，影响定期采集 |
| npm 在当前机器损坏 | 低 | 已用 yarn 绕过，但新成员需注意 |
| 香港迪士尼地图版权 | 低 | 使用官方公开地图图片需注意版权，建议自绘 SVG |
