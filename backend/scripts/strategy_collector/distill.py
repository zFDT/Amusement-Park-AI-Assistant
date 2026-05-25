"""
AI 攻略提炼模块
使用视觉模型对小红书图文攻略进行智能提炼，生成结构化摘要。

v2 更新（2026-05-21）：
- 乐园差异化 System Prompt（含项目白名单、园区分布、乐园特色）
- 新增 strategy_type（9 类）和 strategy_subtypes（场景标签）分类
- 项目名后处理校验（剔除不在白名单的名称）
- 兼容旧版 structured_summary（缺失字段默认值降级）
"""

import asyncio
import base64
import json
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import httpx

from app.core.config import settings

from app.core.logging import configure_logging

configure_logging()

logger = logging.getLogger("app.ai.distill")

# ── 攻略分类枚举 ────────────────────────────────────────────────────────────

STRATEGY_TYPES = [
    "route_plan",       # 路线/顺序规划类（含时间安排）
    "queue_tips",       # 排队/快速通行/时间管理技巧
    "food_dining",      # 餐饮推荐/避雷
    "photo_spot",       # 拍照打卡点/机位分享
    "family_kids",      # 亲子/带娃专项攻略
    "show_parade",      # 表演/烟花/巡游攻略
    "hidden_gem",       # 隐藏玩法/冷门项目/彩蛋
    "general_review",   # 综合性游记/体验分享
    "ticket_deal",      # 票务/优惠/年卡信息
]

STRATEGY_SUBTYPES = [
    "rainy_day", "summer_heat", "christmas", "halloween",  # 天气/节日
    "with_toddler", "with_elderly", "with_friends", "solo",  # 人群
    "first_time", "frequent",                                 # 经验
    "money_saving", "luxury",                                  # 预算
    "morning_rush", "evening_route",                           # 时段
]

# ── 乐园特色描述（注入提炼 Prompt 的差异化上下文）────────────────────────────

_PARK_CHARACTERISTICS = {
    "hongkong_disney": (
        "香港迪士尼乐园是全球最小的迪士尼乐园，共有 7 大园区："
        "美国小镇大街、幻想世界、探险世界、明日世界、反斗奇兵大本营、"
        "迷离庄园、灰熊山谷，以及 2023 年新开的魔雪奇缘世界（全球首个冰雪奇缘主题区）。"
        "乐园虽小但项目紧凑，步行 10 分钟内可达任意两个园区。"
        "明星项目包括：灰熊山极速矿车（独一无二的弹射+倒行过山车）、"
        "迷离大宅（电磁轨道黑暗骑乘）、星战极速穿梭（室内过山车）、"
        "魔雪奇幻之旅（冰雪奇缘水上 dark ride）。"
        "Duffy 家族（达菲、雪莉玫、星黛露、可琦安、奥乐米拉、玲娜贝儿）是香港特色 IP，"
        "限定商品和见面点主要集中在美国小镇大街和 Duffy 小屋。"
        "乐园无单人道，餐饮价格适中，推荐皇室宴会厅和大冒险家餐厅。"
    ),
    "shanghai_disney": (
        "上海迪士尼乐园是中国大陆唯一的迪士尼乐园，也是全球最大的迪士尼城堡所在地，"
        "共有 8 大园区：米奇大街、奇想花园、明日世界、梦幻世界、宝藏湾、"
        "探险岛、玩具总动员、疯狂动物城（2023 年新开）。"
        "乐园面积大，两个远端园区步行需 20-30 分钟。"
        "明星项目包括：创极速光轮（全球最快迪士尼过山车）、"
        "翱翔·飞越地平线（4D 飞行影院，常年排队 90 分钟+）、"
        "加勒比海盗——沉落宝藏之战（沉浸式水上 dark ride，全球独有）、"
        "疯狂动物城：热力追踪（无轨 dark ride）。"
        "乐园有单人通道和迪士尼尊享卡（付费快通），餐饮推荐巴波萨烧烤和米奇好伙伴美味集市。"
        "城堡为全球最大奇幻童话城堡，夜间烟花秀必看。"
    ),
}

# ── 提炼 JSON 输出模板 ───────────────────────────────────────────────────────

_DISTILL_JSON_TEMPLATE = """\
{
  "is_useful": true,
  "strategy_type": "route_plan",
  "strategy_subtypes": ["first_time"],
  "mentioned_attractions": ["项目名1", "项目名2"],
  "suggested_route": "简短的游玩顺序/时间安排建议，1-2句话",
  "tips": "排队技巧、餐饮建议、闪电通道、身高限制等实用提示，1-3句话",
  "summary": "100字以内的整体摘要，涵盖核心亮点"
}\
"""

_DISTILL_FIELD_DESCRIPTIONS = """\
字段说明：
- is_useful: 该攻略是否包含实质性游园建议（纯晒图/无内容的设为 false）
- strategy_type: 攻略主类型，从以下选择最匹配的一个：
  route_plan(路线/顺序规划)、queue_tips(排队/快通技巧)、food_dining(餐饮推荐)、
  photo_spot(拍照打卡)、family_kids(亲子带娃)、show_parade(表演巡游)、
  hidden_gem(隐藏玩法)、general_review(综合游记)、ticket_deal(票务优惠)
- strategy_subtypes: 场景标签数组（可多选，没有则填空数组 []）：
  rainy_day(雨天)、summer_heat(夏季高温)、christmas(圣诞)、halloween(万圣)、
  with_toddler(带幼儿)、with_elderly(带老人)、with_friends(朋友出行)、solo(独自)、
  first_time(首次游园)、frequent(多次)、money_saving(省钱)、luxury(奢华)、
  morning_rush(早鸟冲刺)、evening_route(晚间路线)
- mentioned_attractions: 攻略中明确提到的游乐项目名称列表（中文名，最多8个），
  只能从上方「乐园项目名称列表」中选择，使用完全相同的名称
- suggested_route: 游玩顺序或时间安排，没有则填 null
- tips: 实用技巧，没有则填 null
- summary: 整体摘要，is_useful=false 时填 null

只输出 JSON，不要 markdown 代码块，不要解释。\
"""

# ── 项目名白名单加载 ──────────────────────────────────────────────────────────

# 缓存乐园数据
_park_data_cache: dict[str, dict] = {}


def _load_park_data(park_id: str) -> dict | None:
    """加载乐园 JSON 数据文件，返回 {park_id, park_name, areas: [{name, attractions: [{name, category}]}]}"""
    if park_id in _park_data_cache:
        return _park_data_cache[park_id]

    data_file = Path(__file__).parent.parent.parent / "app" / "data" / f"{park_id}.json"
    if not data_file.exists():
        logger.warning("乐园数据文件不存在: %s", data_file)
        return None
    try:
        data = json.loads(data_file.read_text(encoding="utf-8"))
        _park_data_cache[park_id] = data
        return data
    except Exception as e:
        logger.warning("加载乐园数据失败: %s", e)
        return None


def _get_attraction_whitelist(park_id: str) -> tuple[list[str], dict[str, str]]:
    """
    返回 (项目名列表, {项目名: 所属园区名})。
    项目名列表作为 AI 提炼时的白名单约束。
    """
    data = _load_park_data(park_id)
    if not data:
        return [], {}
    names: list[str] = []
    name_to_area: dict[str, str] = {}
    for area in data.get("areas", []):
        area_name = area.get("name", "")
        for attr in area.get("attractions", []):
            name = attr.get("name", "")
            if name:
                names.append(name)
                name_to_area[name] = area_name
    return names, name_to_area


def _validate_mentioned_attractions(
    mentioned: list[str],
    whitelist: list[str],
    name_to_area: dict[str, str],
    title: str = "",
) -> tuple[list[str], list[str]]:
    """
    校验 AI 输出的 mentioned_attractions，剔除不在白名单中的名称。
    返回 (有效列表, 被剔除列表)。
    """
    valid: list[str] = []
    removed: list[str] = []
    for name in mentioned:
        name_stripped = name.strip()
        if name_stripped in whitelist:
            if name_stripped not in valid:
                valid.append(name_stripped)
        else:
            removed.append(name_stripped)
            # 尝试模糊匹配
            matched = _fuzzy_match_attraction(name_stripped, whitelist)
            if matched and matched not in valid:
                valid.append(matched)
                logger.info(
                    "[distill] 项目名标准化: %r → %r (攻略: %s)",
                    name_stripped, matched, title[:40],
                )
            else:
                logger.warning(
                    "[distill] 项目名不在白名单中，已剔除: %r (攻略: %s)",
                    name_stripped, title[:40],
                )
    return valid, removed


def _fuzzy_match_attraction(name: str, whitelist: list[str]) -> str | None:
    """模糊匹配项目名，处理常见别名和简写。"""
    # 去掉常见后缀
    simplified = name.replace("过山车", "").replace("项目", "").replace("游乐设施", "").strip()
    # 精确匹配别名表
    ALIASES: dict[str, str] = {
        "灰熊山谷": "灰熊山极速矿车",
        "灰熊山": "灰熊山极速矿车",
        "灰熊矿车": "灰熊山极速矿车",
        "极速矿车": "灰熊山极速矿车",
        "迷离庄园": "迷离大宅",
        "迷离": "迷离大宅",
        "星战": "星战极速穿梭",
        "星际极速穿梭": "星战极速穿梭",
        "钢铁侠": "铁甲奇侠飞行之旅",
        "铁甲奇侠": "铁甲奇侠飞行之旅",
        "蚁侠": "蚁侠与黄蜂女：击战特攻",
        "蚁人": "蚁侠与黄蜂女：击战特攻",
        "冰雪奇缘": "魔雪奇幻之旅",
        "elsa": "魔雪奇幻之旅",
        "魔雪": "魔雪奇幻之旅",
        "维尼": "小熊维尼历险之旅",
        "小熊维尼": "小熊维尼历险之旅",
        "飞象": "小飞象旋转世界",
        "小飞象": "小飞象旋转世界",
        "rc飞车": "RC 飞车",
        "创极速": "创极速光轮",
        "tron": "创极速光轮",
        "翱翔": "翱翔·飞越地平线",
        "飞越地平线": "翱翔·飞越地平线",
        "加勒比": "加勒比海盗——沉落宝藏之战",
        "加勒比海盗": "加勒比海盗——沉落宝藏之战",
        "小矮人": "七个小矮人矿山车",
        "七个小矮人": "七个小矮人矿山车",
        "小飞侠": "小飞侠天空奇遇",
        "动物城": "疯狂动物城：热力追踪",
        "疯狂动物城": "疯狂动物城：热力追踪",
        "热力追踪": "疯狂动物城：热力追踪",
        "巴斯": "巴斯光年星际营救",
        "巴斯光年": "巴斯光年星际营救",
        "矿山车": "七个小矮人矿山车",
        "雷鸣山": "雷鸣山漂流",
        "漂流": "雷鸣山漂流",
    }
    if name in ALIASES:
        return ALIASES[name]
    if simplified in ALIASES:
        return ALIASES[simplified]
    return None


def _build_distill_system_prompt(park_id: str) -> str:
    """
    构建乐园差异化 System Prompt，包含：
    - 乐园特色与规模
    - 园区列表
    - 项目名白名单（AI 只能从这里选）
    - 分类输出指令
    """
    park_name = "迪士尼乐园"
    characteristics = ""
    area_list_str = ""
    whitelist_str = ""

    if park_id in _PARK_CHARACTERISTICS:
        data = _load_park_data(park_id)
        if data:
            park_name = data.get("park_name", park_name)
            characteristics = _PARK_CHARACTERISTICS.get(park_id, "")
            areas = [area.get("name", "") for area in data.get("areas", [])]
            area_list_str = "、".join(areas) if areas else "暂无"
            names, _ = _get_attraction_whitelist(park_id)
            if names:
                whitelist_lines = [f"- {n}" for n in names]
                whitelist_str = "\n".join(whitelist_lines)

    return f"""\
你是一个迪士尼乐园游园助理，专门从小红书攻略中提炼实用信息。

## 当前乐园：{park_name}

{characteristics}

园区分布：{area_list_str}

## 乐园项目名称列表（mentioned_attractions 只能从以下选择，使用完全相同的名称）
{whitelist_str}

> 如果正文提到的项目名不完全匹配（如简称、别名），请标准化为上述列表中的名称。
> 如果无法确定对应哪个项目，不要编造，不要加入 mentioned_attractions。

请分析以下攻略（含正文和图片），严格按照下面的 JSON 格式输出：

{_DISTILL_JSON_TEMPLATE}

{_DISTILL_FIELD_DESCRIPTIONS}\
"""

# 兼容旧版：保留无参数的 _SYSTEM 作为降级（旧调用未传 park_id 时使用）
_SYSTEM_FALLBACK = """\
你是一个迪士尼乐园游园助理，专门从小红书攻略中提炼实用信息。

请分析以下攻略（含正文和图片），严格按照下面的 JSON 格式输出，不要输出任何其他内容：

{
  "is_useful": true,
  "strategy_type": "general_review",
  "strategy_subtypes": [],
  "mentioned_attractions": ["项目名1", "项目名2"],
  "suggested_route": "简短的游玩顺序/时间安排建议，1-2句话",
  "tips": "排队技巧、餐饮建议、闪电通道、身高限制等实用提示，1-3句话",
  "summary": "100字以内的整体摘要，涵盖核心亮点"
}

字段说明：
- is_useful: 该攻略是否包含实质性游园建议（纯晒图/无内容的设为 false）
- strategy_type: 攻略主类型，从以下选择：route_plan/queue_tips/food_dining/photo_spot/family_kids/show_parade/hidden_gem/general_review/ticket_deal
- strategy_subtypes: 场景标签数组（可多选）：rainy_day/summer_heat/christmas/halloween/with_toddler/with_elderly/with_friends/solo/first_time/frequent/money_saving/luxury/morning_rush/evening_route
- mentioned_attractions: 攻略中明确提到的游乐项目名称列表（中文名，最多8个）
- suggested_route: 游玩顺序或时间安排，没有则填 null
- tips: 实用技巧，没有则填 null
- summary: 整体摘要，is_useful=false 时填 null

只输出 JSON，不要 markdown 代码块，不要解释。\
"""

# XHS CDN 图片下载时需要带 Referer，否则 403
_XHS_HEADERS = {
    "Referer": "https://www.xiaohongshu.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def convert_to_nowatermark_url(img_url: str) -> str:
    """
    将小红书 CDN 图片 URL 转换为无水印地址（ci.xiaohongshu.com），供前端直接展示。
    参考 Spider_XHS 的 get_note_no_water_img() 逻辑，
    处理 notes_pre_post / spectrum / jpg 等多种 URL 模式。
    转换失败时降级返回原始 URL。
    """
    try:
        if "notes_pre_post/" in img_url:
            # 新版图片资源，保留 notes_pre_post token
            token = "notes_pre_post/" + img_url.split("notes_pre_post/", 1)[1].split("!", 1)[0].split("?", 1)[0]
            return f"https://ci.xiaohongshu.com/{token}?imageView2/format/jpeg"
        elif "spectrum" in img_url:
            # spectrum 格式图片
            token = "/".join(img_url.split("/")[-2:]).split("!", 1)[0].split("?", 1)[0]
            return f"https://ci.xiaohongshu.com/{token}?imageView2/format/jpeg"
        elif ".jpg" in img_url.lower() or ".png" in img_url.lower() or ".webp" in img_url.lower():
            # 标准图片格式
            token = "/".join([s for s in img_url.split("/")[-3:]]).split("!", 1)[0].split("?", 1)[0]
            return f"https://ci.xiaohongshu.com/{token}?imageView2/format/jpeg"
        else:
            # 其他格式，取最后一段路径
            token = img_url.split("/")[-1].split("!", 1)[0].split("?", 1)[0]
            return f"https://ci.xiaohongshu.com/{token}?imageView2/format/jpeg"
    except Exception:
        logger.debug("无水印 URL 转换失败，降级使用原始 URL: %s", img_url[:80])
        return img_url

SUPPORTED_DISTILL_API_MODES = {"openai", "openai-responses", "anthropic", "gemini", "deepseek"}


def _profile_to_distill_config(profile: Any) -> dict[str, str]:
    api_mode = getattr(profile, "api_mode", "anthropic") or "anthropic"
    base_url = getattr(profile, "base_url", "") or ""
    # openai 模式但 base_url 指向 DeepSeek 时自动切换，避免传错模型名和图片格式
    # if api_mode == "openai" and "deepseek" in base_url.lower():
    #     api_mode = "deepseek"
    if api_mode not in SUPPORTED_DISTILL_API_MODES:
        api_mode = "anthropic"
    return {
        "code": getattr(profile, "code", ""),
        "api_mode": api_mode,
        "base_url": base_url,
        "api_key": getattr(profile, "api_key", "") or "",
        "model": getattr(profile, "model_id", "") or "",
    }


def resolve_distill_ai_config() -> dict[str, str] | None:
    """Resolve strategy-distill AI config from env profiles.

    Priority:
    1) AI_INTERNAL_PROFILES + AI_DISTILL_PROFILE_CODE
    2) Single AI_INTERNAL_PROFILES entry
    3) Legacy ANTHROPIC_API_KEY fallback
    """
    profiles = getattr(settings, "ai_internal_profiles", []) or []
    preferred_code = (getattr(settings, "ai_distill_profile_code", "") or "").strip()

    if profiles:
        if preferred_code:
            matched = next((p for p in profiles if getattr(p, "code", "") == preferred_code), None)
            if matched is not None:
                cfg = _profile_to_distill_config(matched)
                logger.info("AI 提炼将使用内测配置 code=%s, api_mode=%s", cfg["code"], cfg["api_mode"])
                return cfg
            logger.warning("未找到 AI_DISTILL_PROFILE_CODE=%s 对应的配置，将尝试自动选择", preferred_code)

        if len(profiles) == 1:
            cfg = _profile_to_distill_config(profiles[0])
            logger.info("AI 提炼将使用唯一内测配置 code=%s, api_mode=%s", cfg["code"], cfg["api_mode"])
            return cfg

        # 兜底：优先选择 Anthropic 相关配置，其次选择第一个有 key 的配置
        candidates = [p for p in profiles if getattr(p, "api_key", "")]
        anthropic_candidate = next((p for p in candidates if (getattr(p, "api_mode", "") or "").lower() == "anthropic"), None)
        chosen = anthropic_candidate or (candidates[0] if candidates else None)
        if chosen is not None:
            cfg = _profile_to_distill_config(chosen)
            logger.info("AI 提炼自动选择内测配置 code=%s, api_mode=%s", cfg["code"], cfg["api_mode"])
            return cfg

    legacy_api_key = getattr(settings, "anthropic_api_key", "") or ""
    if legacy_api_key:
        logger.info("AI 提炼将使用 legacy ANTHROPIC_API_KEY")
        return {
            "code": "legacy",
            "api_mode": "anthropic",
            "base_url": "https://api.anthropic.com",
            "api_key": legacy_api_key,
            "model": getattr(settings, "claude_model", "claude-sonnet-4-6"),
        }

    return None


async def _fetch_image_b64(url: str, client: httpx.AsyncClient) -> tuple[str, str] | None:
    """下载图片并返回 (media_type, base64_data)，失败返回 None"""
    try:
        resp = await client.get(url, timeout=15, follow_redirects=True)
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            if not ct.startswith("image/"):
                ct = "image/jpeg"
            return ct, base64.standard_b64encode(resp.content).decode()
    except Exception as e:
        logger.debug(f"图片下载失败 {url[:60]}: {e}")
    return None


def _build_text_body(title: str, content: str) -> str:
    return f"标题：{title or '（无标题）'}\n\n正文：{content or '（无文字，请从图片中提取信息）'}"


def _build_image_parts_for_anthropic(images: list[tuple[str, str]]) -> list[dict[str, Any]]:
    return [
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}}
        for media_type, b64 in images
    ]


def _build_image_parts_for_openai(images: list[tuple[str, str]]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for media_type, b64 in images:
        parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:{media_type};base64,{b64}"},
        })
    return parts


def _build_image_parts_for_gemini(images: list[tuple[str, str]]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for media_type, b64 in images:
        parts.append({"inline_data": {"mime_type": media_type, "data": b64}})
    return parts


async def distill_strategy(
    title: str,
    content: str,
    image_urls: list[str],
    api_key: str,
    base_url: str | None = None,
    model: str = "",
    api_mode: str = "anthropic",
    park_id: str = "",
) -> tuple[str | None, dict | None]:
    """
    调用视觉模型提炼攻略。
    返回 (ai_summary文本降级, structured_summary字典)，失败时均为 None。

    park_id: 乐园 ID（如 hongkong_disney / shanghai_disney），
             用于加载项目白名单和乐园差异化 Prompt。为空时使用通用降级 Prompt。
    """
    if not api_key:
        logger.warning("未配置 API Key，跳过 AI 提炼")
        return None, None

    api_mode = api_mode if api_mode in SUPPORTED_DISTILL_API_MODES else "anthropic"

    # 选择 System Prompt：优先乐园差异化 Prompt，降级到通用 Prompt
    system_prompt = _build_distill_system_prompt(park_id) if park_id else _SYSTEM_FALLBACK

    # 加载项目白名单（用于后处理校验）
    whitelist, name_to_area = _get_attraction_whitelist(park_id) if park_id else ([], {})

    text_body = _build_text_body(title, content)
    image_payloads: list[tuple[str, str]] = []

    urls_to_fetch = image_urls[:4]
    if urls_to_fetch:
        # 先转换为无水印 URL，提升 AI 视觉提炼的图片质量
        nowatermark_urls = [convert_to_nowatermark_url(u) for u in urls_to_fetch]
        if any(nw != orig for nw, orig in zip(nowatermark_urls, urls_to_fetch)):
            logger.debug(
                "[distill] 转换无水印 URL: %d/%d 张图片",
                sum(1 for nw, orig in zip(nowatermark_urls, urls_to_fetch) if nw != orig),
                len(urls_to_fetch),
            )
        async with httpx.AsyncClient(headers=_XHS_HEADERS) as http:
            results = await asyncio.gather(
                *[_fetch_image_b64(u, http) for u in nowatermark_urls],
                return_exceptions=True,
            )
        for result in results:
            if isinstance(result, tuple):
                image_payloads.append(result)

    raw_text: str | None = None
    try:
        if api_mode in {"openai", "openai-responses"}:
            url = f"{(base_url or 'https://api.openai.com/v1').rstrip('/')}/chat/completions"
            payload = {
                "model": model,
                "max_tokens": 500,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [{"type": "text", "text": text_body}, *_build_image_parts_for_openai(image_payloads)]},
                ],
            }
            logger.info("[distill] request %s", json.dumps({"provider": api_mode, "url": url, "model": model, "title": title, "park_id": park_id, "image_count": len(image_payloads)}, ensure_ascii=False))
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"})
                response.raise_for_status()
                data = response.json()
                raw_text = data["choices"][0]["message"]["content"].strip()
                logger.info("[distill] response %s", json.dumps({"provider": api_mode, "status_code": response.status_code, "raw": raw_text}, ensure_ascii=False))
        elif api_mode == "gemini":
            base = (base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
            url = f"{base}/models/{model}:generateContent"
            payload = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{
                    "role": "user",
                    "parts": [{"text": text_body}, *_build_image_parts_for_gemini(image_payloads)],
                }],
                "generationConfig": {"maxOutputTokens": 500},
            }
            logger.info("[distill] request %s", json.dumps({"provider": api_mode, "url": url, "model": model, "title": title, "park_id": park_id, "image_count": len(image_payloads)}, ensure_ascii=False))
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, json=payload, headers={"x-goog-api-key": api_key})
                response.raise_for_status()
                data = response.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                logger.info("[distill] response %s", json.dumps({"provider": api_mode, "status_code": response.status_code, "raw": raw_text}, ensure_ascii=False))
        elif api_mode == "deepseek":
            # DeepSeek 不支持图片输入，只传文本
            url = f"{(base_url or 'https://api.deepseek.com').rstrip('/')}/chat/completions"
            payload = {
                "model": model or "deepseek-v4-flash",
                "max_tokens": 500,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [{"type": "text", "text": text_body}]},
                ],
                "response_format": {"type": "json_object"},
            }
            logger.info("[distill] request %s", json.dumps({"provider": "deepseek", "url": url, "model": model, "title": title, "park_id": park_id}, ensure_ascii=False))
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"})
                response.raise_for_status()
                data = response.json()
                raw_text = data["choices"][0]["message"]["content"].strip()
                logger.info("[distill] response %s", json.dumps({"provider": "deepseek", "status_code": response.status_code, "raw": raw_text[:200]}, ensure_ascii=False))
        else:
            base = (base_url or "https://api.anthropic.com").rstrip("/")
            url = f"{base}/v1/messages"
            payload = {
                "model": model,
                "max_tokens": 500,
                "system": system_prompt,
                "messages": [{
                    "role": "user",
                    "content": [{"type": "text", "text": text_body}, *_build_image_parts_for_anthropic(image_payloads)],
                }],
            }
            req_headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
            logger.info("[distill] request %s", json.dumps({"provider": api_mode, "url": url, "model": model, "title": title, "park_id": park_id, "image_count": len(image_payloads)}, ensure_ascii=False))
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, json=payload, headers=req_headers)
                response.raise_for_status()
                data = response.json()
                raw_text = data["content"][0]["text"].strip()
                logger.info("[distill] response %s", json.dumps({"provider": api_mode, "status_code": response.status_code, "raw": raw_text}, ensure_ascii=False))

    except httpx.HTTPStatusError as e:
        logger.error(f"AI 提炼 HTTP 错误: {e.response.status_code} - {e.response.text}")
        return None, None
    except Exception as e:
        logger.error(f"AI 提炼异常: {e}")
        return None, None

    if not raw_text:
        return None, None

    # 解析结构化 JSON
    structured: dict | None = None
    try:
        # 兼容模型偶尔包裹 ```json ... ``` 的情况
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()
        structured = json.loads(cleaned)
    except Exception:
        logger.warning("[distill] JSON 解析失败，原始输出: %s", raw_text[:200])

    # ── 后处理校验 ──────────────────────────────────────────────────────────
    if structured:
        # 校验 strategy_type 是否为合法值
        strategy_type = structured.get("strategy_type", "")
        if strategy_type not in STRATEGY_TYPES:
            structured["strategy_type"] = "general_review"
            logger.info("[distill] strategy_type 非法值 %r，已修正为 general_review", strategy_type)

        # 校验 strategy_subtypes
        subtypes = structured.get("strategy_subtypes")
        if not isinstance(subtypes, list):
            structured["strategy_subtypes"] = []
        else:
            structured["strategy_subtypes"] = [s for s in subtypes if s in STRATEGY_SUBTYPES]

        # 校验 mentioned_attractions —— 白名单过滤
        mentioned = structured.get("mentioned_attractions")
        if isinstance(mentioned, list) and whitelist:
            valid_mentioned, removed = _validate_mentioned_attractions(mentioned, whitelist, name_to_area, title)
            structured["mentioned_attractions"] = valid_mentioned
        elif not isinstance(mentioned, list):
            structured["mentioned_attractions"] = []

    # ai_summary 降级文本：优先从结构化摘要拼接，否则用原始输出截取
    ai_summary: str | None = None
    if structured:
        parts = []
        if structured.get("summary"):
            parts.append(structured["summary"])
        if structured.get("tips"):
            parts.append(structured["tips"])
        ai_summary = " ".join(parts) if parts else None
    if not ai_summary:
        ai_summary = raw_text[:300]

    logger.info("[distill] done title=%r is_useful=%s type=%s summary_len=%d",
                title[:40],
                structured.get("is_useful") if structured else "?",
                structured.get("strategy_type", "") if structured else "",
                len(ai_summary or ""))
    return ai_summary, structured


async def distill_batch(
    strategies: list[dict],
    api_key: str,
    base_url: str | None = None,
    api_mode: str = "anthropic",
    model: str = "",
    concurrency: int = 3,
    park_id: str = "",
) -> dict[str, dict]:
    """
    批量提炼多条攻略，返回 {strategy_id: {"ai_summary": str, "structured": dict}} 字典。
    使用信号量控制并发，避免 API 限速。

    park_id: 乐园 ID，用于加载项目白名单和乐园差异化 Prompt。
    """
    sem = asyncio.Semaphore(concurrency)
    results: dict[str, dict] = {}

    async def _one(s: dict) -> None:
        async with sem:
            sid = s["id"]
            ai_summary, structured = await distill_strategy(
                title=s.get("title", ""),
                content=s.get("content", ""),
                image_urls=s.get("images", []),
                api_key=api_key,
                base_url=base_url,
                api_mode=api_mode,
                model=model,
                park_id=park_id,
            )
            if ai_summary or structured:
                results[sid] = {"ai_summary": ai_summary, "structured": structured}

    await asyncio.gather(*[_one(s) for s in strategies])
    return results
