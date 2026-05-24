import json
from datetime import datetime, date, time
from app.schemas import PlanningInfo, RouteItem


PREFERENCE_LABELS = {
    "thrill_rides": "刺激项目（过山车等）",
    "family_rides": "亲子项目",
    "shows": "表演/演出",
    "character_meet": "角色见面",
    "photography": "拍照打卡",
    "dining": "特色餐饮",
    "parades": "花车巡游",
}

EXPERIENCE_LABELS = {
    "first_time": "首次游览",
    "visited_before": "去过 1-2 次",
    "frequent": "多次游览",
}

FITNESS_LABELS = {1: "很弱", 2: "较弱", 3: "一般", 4: "较好", 5: "很好"}

PARK_NAMES = {
    "shanghai_disney": "上海迪士尼乐园",
    "hongkong_disney": "香港迪士尼乐园",
}


def _describe_party(planning: PlanningInfo) -> str:
    adults = sum(1 for m in planning.party if m.type == "adult")
    children = [m for m in planning.party if m.type == "child"]
    elderly = sum(1 for m in planning.party if m.type == "elderly")
    parts = []
    if adults:
        parts.append(f"{adults} 名成人")
    if children:
        ages = "、".join(str(c.age) for c in children if c.age)
        parts.append(f"{len(children)} 名儿童" + (f"（{ages}岁）" if ages else ""))
    if elderly:
        parts.append(f"{elderly} 名老人")
    return "、".join(parts) or "未指定"


def build_system_prompt(
    planning: PlanningInfo,
    wait_times_json: str,
    current_time: str,
    completed_attractions: list[str],
    current_location: dict | None,
    strategy_snippets: list[str] | None = None,
) -> str:
    park_name = PARK_NAMES.get(planning.park_id, planning.park_id)
    prefs = "、".join(PREFERENCE_LABELS.get(p, p) for p in planning.preferences) or "无特别偏好"
    must_do = "、".join(planning.must_do_attractions) or "无"
    fitness = FITNESS_LABELS.get(planning.fitness_level, "一般")
    experience = EXPERIENCE_LABELS.get(planning.experience_level, "未知")
    party_desc = _describe_party(planning)
    completed_str = "、".join(completed_attractions) if completed_attractions else "无"
    location_str = json.dumps(current_location, ensure_ascii=False) if current_location else "未知"

    # ── 日期上下文处理 ─────────────────────────────────────────────────
    real_today = date.today()
    try:
        visit_date = date.fromisoformat(planning.visit_date)
    except (ValueError, TypeError):
        visit_date = real_today

    # 计算 AI 应该使用的"参考时间"
    if visit_date == real_today:
        # 同日游园：使用真实当前时间
        context_time = current_time
        date_context = ""
    else:
        # 未来/过去游园：使用游园日入场时间作为参考
        entry_time = planning.entry_time or "09:00"
        context_time = f"{planning.visit_date}T{entry_time}"
        days_diff = (visit_date - real_today).days
        if days_diff > 0:
            date_context = (
                f"\n> ⚠️ 今天是 {real_today.isoformat()}，用户计划 {days_diff} 天后（{planning.visit_date}）游园。"
                f"以下排队数据为当前实时数据，{days_diff} 天后实际情况可能有变化，请据此给出参考建议。"
            )
        elif days_diff < 0:
            date_context = f"\n> ⚠️ 用户游园日期 {planning.visit_date} 已过，请按历史回顾方式回复。"
        else:
            date_context = ""

    # 计算剩余游玩时间（基于 context_time）
    try:
        ref_dt = datetime.fromisoformat(context_time)
        exit_dt = datetime.combine(visit_date, time.fromisoformat(planning.exit_time or "21:00"))
        remaining_minutes = max(0, int((exit_dt - ref_dt).total_seconds() / 60))
        remaining_str = f"{remaining_minutes // 60} 小时 {remaining_minutes % 60} 分钟"
    except Exception:
        remaining_str = "计算失败"

    if strategy_snippets:
        strategy_items = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(strategy_snippets[:5]))
        strategy_section = f"""共 {len(strategy_snippets[:5])} 条相关攻略：
{strategy_items}

> 以上攻略按类型和相关性排序。在回复中，如果攻略中的建议适用于用户当前情况，可以直接引用（如"根据其他游客的经验..."），增强建议的可信度。"""
    else:
        strategy_section = "暂无相关攻略数据"

    return f"""你是一个专业的迪士尼乐园游园助理，帮助游客规划最优游园路线，减少排队时间，提升游园体验。

## 当前乐园信息
乐园：{park_name}
参考时间：{context_time}
游园日期：{planning.visit_date}{date_context}

## 用户信息
人员构成：{party_desc}
游园时间：{planning.entry_time} - {planning.exit_time}（剩余约 {remaining_str}）
兴趣偏好：{prefs}
必玩项目：{must_do}
体力水平：{fitness}（{planning.fitness_level}/5）
游园经验：{experience}
特殊需求：{planning.special_notes or "无"}

## 当前实时排队数据（单位：分钟，null 表示关闭/未知）
{wait_times_json}

## 已完成项目（不再推荐这些项目）
{completed_str}

## 当前位置
{location_str}

## 游客攻略参考（来自小红书，仅供参考）
{strategy_section}

## 规划原则
1. 优先安排排队时间短的热门项目（开园前30分钟冲刺热门项目）
2. 按地理位置聚类，减少无效步行，同一区域的项目连续安排
3. 将高体力/刺激项目安排在上午，下午安排轻松项目
4. 为餐饮预留时间（建议避开 12:00-13:00 高峰，选择 11:30 或 13:30）
5. 必玩项目必须纳入规划，优先安排
6. 考虑儿童/老人的体力限制和身高要求
7. 关闭或故障的项目不纳入路线
8. 已完成的项目不再推荐
9. {"香港迪士尼面积小（步行10分钟可跨园区），可灵活跨区安排" if planning.park_id == "hongkong_disney" else "上海迪士尼面积大（跨园区需20-30分钟），建议按区域集中安排，减少来回奔波"}
10. 如果攻略中有与用户情况匹配的实用建议，请引用并标注来源（如"根据攻略《xxx》的建议..."）

## 回复要求
- 用中文回复，语气友好专业
- 回复简洁，重点突出
- **当用户询问下一步去哪、重新规划或路线建议时，必须给出 2-3 个方案供选择**，每个方案标注推荐理由（如"距离最近""排队最短""综合最优"），让用户自主选择
- 每个方案的推荐理由要具体，例如"当前排队仅5分钟""步行约3分钟可到达""适合现在的体力状态"
- 如果涉及路线规划，在回复末尾附上结构化路线（JSON格式，用 ```route 代码块包裹）：
```route
[{{"time": "09:00", "attraction_id": "attraction_id", "attraction_name": "项目名称", "estimated_wait": 30, "note": "备注", "type": "attraction", "area_name": "幻想世界"}}]
```
- type 字段可选值：attraction（游乐项目）、dining（餐饮）、show（表演）、break（休息）
- area_name 字段必须填写该项目所在的园区/区域名称（如"幻想世界"、"明日世界"、"探险世界"等），方便用户导航
- 如果只是回答问题而不需要更新路线，则不需要附加 route 代码块"""
