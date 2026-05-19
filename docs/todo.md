# 待办事项 / TODO

> 最后更新：2026-05-19

---

## 已完成 ✅

### 交互优化（2026-05-18）
- [x] **SSE error chunk 处理**：后端返回 `error` 类型 chunk 时，前端显示红色错误气泡，不再静默丢弃
- [x] **中止流式时空消息清理**：用户点击停止时，若无内容则移除空占位消息；有内容则保留已接收部分
- [x] **错误消息视觉区分**：错误气泡使用红色背景（`bg-red-50 border-red-200`），与正常灰色气泡明显区分
- [x] **分享失败反馈**：分享失败不再静默，显示红色错误提示
- [x] **排队时间面板状态**：区分加载中（spinner）/ 错误（amber 警告条）/ 空数据三种状态，刷新按钮加载中禁用并旋转

### 新功能（后端，2026-05-18）
- [x] **拍照识别位置（后端）**：新增 `POST /api/vision/locate` 端点，接收 base64 图片，调用视觉 AI 识别所在园区/景点，支持 anthropic/gemini/openai 三种模式
- [x] **区域标签字段**：`RouteItem` schema 新增 `area_name` 字段，prompt 要求 AI 必须填写每个项目所在园区名称
- [x] **多方案推荐（prompt）**：AI 在路线建议时给出 2-3 个方案，每个方案标注具体推荐理由（距离最近/排队最短/综合最优）
- [x] **已完成项目过滤（prompt）**：已完成项目明确标注不再推荐，规划原则第 8 条约束

### 基础设施 + 前端需求实现（2026-05-19）
- [x] **TypeScript 构建验证**：`yarn build`（`tsc -b && vite build`）零错误通过
- [x] **RouteItem 类型补全 areaName**：`types/index.ts` 新增 `areaName?: string`，SSE 做 `area_name` → `areaName` 转换
- [x] **路线卡片区域标签显示**：`MessageBubble.tsx` 每行项目名称下方显示 `📍 幻想世界`
- [x] **拍照识别位置（前端接入）**：`ChatInput.tsx` 新增相机按钮，Canvas 压缩图片，调用 `visionLocate` API，结果写入 `currentLocation` store 并预填输入框
- [x] **已完成项目标记**：`MessageBubble.tsx` 路线每行新增勾选按钮（`Circle`/`CheckCircle`），已完成项目显示删除线+灰色，`markAttractionComplete` 异步同步 `updateSession` API
- [x] **路线完成进度条**：路线卡片 header 显示 `3/8 已完成` + 蓝色进度条
- [x] **当前位置显示（Header）**：`AssistantPage.tsx` header 显示 `📍 当前位置` 蓝色标签
- [x] **快捷提示词动态化**：`ChatInput` 根据 `currentLocation` 和 `completedAttractions` 动态生成提示按钮
- [x] **WaitTimePanel 中文名验证**：全部 50 个项目均有 `queue_times_ride_id` 映射

- [ ] 后端 `_normalize_messages` 在 vision 路由中未复用，可统一
