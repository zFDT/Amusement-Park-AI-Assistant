# 待办事项 / TODO

> 最后更新：2026-05-18

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

---

## 进行中 🚧

### 需求2：已完成项目标记（前端）
路线卡片每个项目增加勾选按钮，点击后标记为已完成，同步到 store 和后端 `PATCH /api/sessions/{id}`。

**涉及文件：**
- `frontend/src/components/chat/MessageBubble.tsx` — 路线卡片每行加勾选按钮
- `frontend/src/store/sessionStore.ts` — `markAttractionComplete` 已存在，需触发 API 同步
- `frontend/src/services/api.ts` — `updateSession` 已存在

---

## 待办 📋

### 需求1：拍照识别位置（前端）
后端 endpoint 已就绪，需要前端接入。

**实现方案：**
- 在 `ChatInput` 组件中增加相机图标按钮
- 点击后触发 `<input type="file" accept="image/*" capture="environment">` 调起摄像头
- 选图后压缩为 base64，调用 `POST /api/vision/locate`
- 识别结果（`label` + `area_name`）写入 `currentLocation` store
- 同时在输入框预填文字，如"我现在在幻想世界入口附近"

**涉及文件：**
- `frontend/src/components/chat/ChatInput.tsx` — 新增相机按钮
- `frontend/src/services/api.ts` — 新增 `visionLocate()` 函数
- `frontend/src/store/sessionStore.ts` — `setCurrentLocation` 已存在

---

### 需求4：区域标签显示（前端）
后端 `RouteItem` 已有 `area_name` 字段，前端需要显示。

**实现方案：**
- `frontend/src/types/index.ts` — `RouteItem` 新增 `areaName?: string`
- `frontend/src/components/chat/MessageBubble.tsx` — 路线卡片每行在项目名称下方显示区域标签（小字灰色，如 `📍 幻想世界`）
- `frontend/src/services/sse.ts` — 确认 `area_name` → `areaName` 字段转换

---

### 其他优化建议（低优先级）

- [ ] **当前位置显示**：header 区域显示当前位置标签（来自 `currentLocation` store），方便用户确认 AI 知道自己在哪
- [ ] **快捷提示词优化**：根据当前位置动态生成快捷提示，如"从[当前位置]出发，下一个去哪？"
- [ ] **路线项目完成进度条**：header 或路线卡片顶部显示已完成/总数进度
- [ ] **上海迪士尼支持**：目前仅香港迪士尼可用，上海迪士尼数据待补充
- [ ] **离线缓存**：排队时间数据本地缓存，网络断开时显示上次数据而非空白

---

## 技术债务

- [ ] `frontend/src/hooks/useChat.ts` 中 `updateLastMessage` 的 `isError` 参数传递方式可以用 store action 封装更清晰
- [ ] `backend/app/api/routes/vision.py` 中视觉 AI 调用逻辑与 `ai_service.py` 有重复，可考虑抽取公共函数
- [ ] 后端 `_normalize_messages` 在 vision 路由中未复用，可统一
