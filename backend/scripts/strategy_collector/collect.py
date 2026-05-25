"""
香港/上海迪士尼乐园攻略采集器
基于 DrissionPage（Chrome 自动化），采集小红书图文攻略并入库。

核心改进（参考 xiaohongshu-mcp 项目）：
- 使用 window.__INITIAL_STATE__ 提取数据，比 DOM 选择器更稳定可靠
- 搜索结果直接从 JS 状态对象读取，包含 xsecToken
- 详情页通过 noteDetailMap 获取完整图片列表和互动数据

运行方式：
    python -m scripts.strategy_collector.collect --park hongkong_disney
    python -m scripts.strategy_collector.collect --park hongkong_disney --limit 30
    python -m scripts.strategy_collector.collect --park hongkong_disney --no-distill

依赖：
    pip install DrissionPage  （需要 Chrome 浏览器）
    数据库需已初始化（python -m scripts.init_db）
"""

import asyncio
import hashlib
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.database import AsyncSessionLocal
from app.models.park import Strategy
from scripts.strategy_collector.distill import distill_batch, resolve_distill_ai_config

logger = logging.getLogger(__name__)

try:
    from DrissionPage import ChromiumPage, ChromiumOptions
    DRISSION_AVAILABLE = True
except ImportError:
    DRISSION_AVAILABLE = False
    logger.warning("DrissionPage not installed. Run: pip install DrissionPage")

BROWSER_DATA_DIR = Path(__file__).parent.parent.parent / "browser_data" / "xhs"
XHS_PORT = 9521

# ── 关键词动态生成 ────────────────────────────────────────────────────────────

# 基础关键词（每个乐园必备）
_BASE_KEYWORDS = {
    "hongkong_disney": [
        "香港迪士尼攻略",
        "香港迪士尼游玩路线",
        "香港迪士尼必玩",
        "香港迪士尼一日游",
        "香港迪士尼排队技巧",
    ],
    "shanghai_disney": [
        "上海迪士尼攻略",
        "上海迪士尼游玩路线",
        "上海迪士尼必玩",
        "上海迪士尼一日游",
    ],
}

# 场景关键词模板（按 strategy_subtype 映射到搜索词）
_SCENE_KEYWORD_TEMPLATES = {
    "rainy_day": ["{park_short}迪士尼雨天攻略", "{park_short}迪士尼下雨怎么玩"],
    "summer_heat": ["{park_short}迪士尼夏天攻略", "{park_short}迪士尼暑期攻略"],
    "christmas": ["{park_short}迪士尼圣诞攻略", "{park_short}迪士尼圣诞节"],
    "halloween": ["{park_short}迪士尼万圣节攻略", "{park_short}迪士尼万圣"],
    "with_toddler": ["{park_short}迪士尼带娃攻略", "{park_short}迪士尼亲子攻略", "{park_short}迪士尼儿童"],
    "with_elderly": ["{park_short}迪士尼老人攻略", "{park_short}迪士尼长辈"],
    "with_friends": ["{park_short}迪士尼情侣攻略", "{park_short}迪士尼闺蜜"],
    "solo": ["{park_short}迪士尼一个人攻略"],
    "first_time": ["{park_short}迪士尼新手攻略", "{park_short}迪士尼首次"],
    "money_saving": ["{park_short}迪士尼省钱攻略", "{park_short}迪士尼性价比"],
    "morning_rush": ["{park_short}迪士尼早鸟攻略", "{park_short}迪士尼开园冲刺"],
    "evening_route": ["{park_short}迪士尼夜场攻略", "{park_short}迪士尼晚上"],
}

# 迪士尼乐园简称映射
_PARK_SHORT_NAMES = {
    "hongkong_disney": "香港",
    "shanghai_disney": "上海",
}

# 热门项目关键词模板
_ATTRACTION_KEYWORD_TEMPLATE = "{park_short}迪士尼 {attraction_name}"

# 每种范围允许的最大关键词数
_KEYWORD_SCOPE_LIMITS = {
    "basic": 6,
    "extended": 15,
    "full": 30,
}


def _generate_search_keywords(park_id: str, scope: str = "extended") -> list[str]:
    """
    动态生成搜索关键词列表。

    scope:
    - basic: 仅基础关键词（4-5 个）
    - extended: 基础 + 场景关键词（~15 个）
    - full: 基础 + 场景 + 热门项目关键词（~30 个）
    """
    base = _BASE_KEYWORDS.get(park_id, [])
    if scope == "basic":
        return base

    park_short = _PARK_SHORT_NAMES.get(park_id, park_id)
    keywords = list(base)

    # 添加场景关键词
    for _subtype, templates in _SCENE_KEYWORD_TEMPLATES.items():
        for template in templates:
            kw = template.format(park_short=park_short)
            keywords.append(kw)

    # 添加热门项目关键词（仅 full 模式）
    if scope == "full":
        names, _ = _get_attraction_names_for_search(park_id)
        # 取前 10 个热门项目
        for name in names[:10]:
            kw = _ATTRACTION_KEYWORD_TEMPLATE.format(park_short=park_short, attraction_name=name)
            keywords.append(kw)

    limit = _KEYWORD_SCOPE_LIMITS.get(scope, 15)
    # 去重并限制数量
    seen = set()
    deduped = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            deduped.append(kw)
        if len(deduped) >= limit:
            break

    return deduped


def _get_attraction_names_for_search(park_id: str) -> tuple[list[str], dict]:
    """从乐园 JSON 加载热门项目名称（优先取 category != show 的项目）。"""
    try:
        data_path = Path(__file__).parent.parent.parent / "app" / "data" / f"{park_id}.json"
        if not data_path.exists():
            return [], {}
        data = json.loads(data_path.read_text(encoding="utf-8"))
        names = []
        name_to_area = {}
        for area in data.get("areas", []):
            for attr in area.get("attractions", []):
                name = attr.get("name", "")
                if name:
                    names.append(name)
                    name_to_area[name] = area.get("name", "")
        # 优先排列非 show 类项目
        thrill_names = [n for n in names if any(
            a.get("name") == n and a.get("category") not in ("show", "dining", "shopping")
            for area in data.get("areas", []) for a in area.get("attractions", [])
        )]
        return thrill_names or names, name_to_area
    except Exception:
        return [], {}

# 兼容旧版常量访问（内部转为函数调用）
PARK_KEYWORDS = {pid: _generate_search_keywords(pid, "basic") for pid in _BASE_KEYWORDS}

_ATTRACTIONS = {
    "hongkong_disney": [
        "迷离庄园", "大灰熊山谷", "超空间山峰", "钢铁侠", "蚁侠",
        "小小世界", "小熊维尼", "冰雪奇缘", "达菲", "灰姑娘",
        "森林河流", "泰山树屋", "RC飞车", "绿军人", "飞象",
        "米奇幻想曲", "幻想花园", "童话森林",
    ],
    "shanghai_disney": [
        "创极速光轮", "翱翔", "雷鸣山漂流", "加勒比海盗",
        "七个小矮人", "小飞侠", "疯狂动物城", "巴斯光年",
    ],
}

# 详情页之间的间隔，避免触发反爬（太短容易触发风控）
_DETAIL_INTERVAL = 2.5


def create_browser() -> "ChromiumPage":
    BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    co = ChromiumOptions()
    co.set_user_data_path(str(BROWSER_DATA_DIR))
    co.set_local_port(XHS_PORT)
    co.set_argument("--disable-blink-features=AutomationControlled")
    co.set_argument("--no-first-run")
    return ChromiumPage(co)


def wait_for_login(page: "ChromiumPage", force: bool = False) -> None:
    page.get("https://www.xiaohongshu.com")
    time.sleep(3)
    avatar = page.ele("css:.user-avatar", timeout=3) or page.ele("css:[class*='avatar']", timeout=2)
    if avatar and not force:
        logger.info("XHS: 已登录（复用上次 session）")
        return

    if force:
        logger.info("XHS: 已进入专门登录模式，请在浏览器中完成登录")
    else:
        logger.info("XHS: 需要登录，请在浏览器中完成登录")

    input(">>> 小红书登录完成后，按回车继续...")

    # 回车后再做一次轻量校验，便于确认登录态是否真的生效
    avatar = page.ele("css:.user-avatar", timeout=3) or page.ele("css:[class*='avatar']", timeout=2)
    if avatar:
        logger.info("XHS: 已确认登录态")
    else:
        logger.warning("XHS: 未检测到明确登录态，但将继续尝试采集（如仍无结果，可重新登录）")


def _parse_count(text: str) -> int:
    text = str(text).strip()
    if not text:
        return 0
    try:
        if "万" in text:
            return int(float(text.replace("万", "")) * 10000)
        return int(text.replace("+", "").replace(",", ""))
    except (ValueError, TypeError):
        return 0


def _extract_mentioned_attractions(content: str, park_id: str) -> list[str]:
    keywords = _ATTRACTIONS.get(park_id, [])
    return [kw for kw in keywords if kw in content]


def _wait_initial_state(page: "ChromiumPage", timeout: int = 10) -> bool:
    """等待 window.__INITIAL_STATE__ 加载完成"""
    for _ in range(timeout * 2):
        try:
            ready = page.run_js("return typeof window.__INITIAL_STATE__ !== 'undefined'")
            if ready:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _run_js(page: "ChromiumPage", js: str):
    """执行 JS，返回解析后的 Python 对象；失败返回 None"""
    try:
        raw = page.run_js(js)
        if raw is None or raw == "null" or raw == "undefined":
            return None
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception as e:
        logger.debug(f"JS 执行失败: {e}")
        return None


def _detect_anticrawl(page: "ChromiumPage", feed_id: str) -> str | None:
    """
    检测当前页面是否被反爬/风控拦截。
    返回拦截原因字符串；如果页面正常则返回 None。
    """
    try:
        current_url = page.url or ""
        # 被重定向到登录页
        if "login" in current_url.lower() or "signin" in current_url.lower():
            return "被重定向到登录页"
        # 页面标题包含典型拦截提示
        title = page.run_js("return document.title || ''")
        if title:
            title_lower = title.lower()
            anti_patterns = [
                "扫码", "登录查看", "not found", "抱歉", "不存在",
                "captcha", "verify", "验证", "风控",
            ]
            for pat in anti_patterns:
                if pat in title_lower:
                    return f"页面标题含反爬关键词: '{pat}'"
    except Exception:
        pass

    # 检查 __INITIAL_STATE__ 中是否有 noteDetailMap
    try:
        has_note_map = page.run_js(
            "return !!(window.__INITIAL_STATE__?.note?.noteDetailMap)"
        )
        if not has_note_map:
            return "noteDetailMap 缺失（笔记可能不存在/需App查看）"
    except Exception:
        return "__INITIAL_STATE__ 不可访问"

    # 检查该 feed_id 对应的 note 是否存在
    safe_id = feed_id.replace("'", "").replace('"', "")
    try:
        has_note = page.run_js(
            f"return !!window.__INITIAL_STATE__?.note?.noteDetailMap?.['{safe_id}']?.note"
        )
        if not has_note:
            return f"笔记 {feed_id[:12]}... 在 noteDetailMap 中缺失（被删除/仅App可见）"
    except Exception:
        return "noteDetailMap 条目访问失败"

    return None


def _get_detail(page: "ChromiumPage", feed_id: str, xsec_token: str) -> tuple[str, list[str], int, int]:
    """
    导航到笔记详情页，从 __INITIAL_STATE__.note.noteDetailMap 提取：
    - content: 正文（desc 字段）
    - images: 图片 URL 列表（imageList[].urlDefault）
    - collects: 收藏数
    - comments: 评论数

    参考 xiaohongshu-mcp feed_detail.go 的 URL 格式和数据提取方式。
    """
    content = ""
    images: list[str] = []
    collects = 0
    comments = 0

    try:
        detail_url = (
            f"https://www.xiaohongshu.com/explore/{feed_id}"
            f"?xsec_token={xsec_token}&xsec_source=pc_feed"
        )
        page.get(detail_url)
        time.sleep(2)

        # 反爬检测
        anticrawl_reason = _detect_anticrawl(page, feed_id)
        if anticrawl_reason:
            logger.warning(f"⚠ 反爬/风控: {anticrawl_reason}")
            return content, images, collects, comments

        if not _wait_initial_state(page):
            logger.warning(f"详情页 __INITIAL_STATE__ 未加载: {feed_id}")
            return content, images, collects, comments

        # 安全地访问嵌套属性，避免 JS 注入（feed_id 来自 XHS 自身数据）
        safe_id = feed_id.replace("'", "").replace('"', "")
        detail = _run_js(page, f"""
            return JSON.stringify((() => {{
                const state = window.__INITIAL_STATE__;
                const noteMap = state?.note?.noteDetailMap;
                if (!noteMap) return null;
                const entry = noteMap['{safe_id}'];
                return entry?.note || null;
            }})())
        """)

        if not detail:
            return content, images, collects, comments

        content = detail.get("desc", "")

        # 提取所有图片（urlDefault 优先，fallback urlPre）
        for img in detail.get("imageList", []):
            url = img.get("urlDefault") or img.get("urlPre", "")
            if url:
                images.append(url)

        interact = detail.get("interactInfo", {})
        collects = _parse_count(interact.get("collectedCount", "0"))
        comments = _parse_count(interact.get("commentCount", "0"))

    except Exception as e:
        logger.debug(f"获取详情出错 {feed_id}: {e}")

    return content, images, collects, comments


def search_xhs(
    page: "ChromiumPage",
    keyword: str,
    limit: int = 20,
    sort_type: str = "general",
    note_type: int = 0,
    note_time: int = 0,
) -> list[dict]:
    """
    搜索小红书，从 window.__INITIAL_STATE__.search.feeds 提取结果。
    参考 xiaohongshu-mcp search.go 的数据提取逻辑。

    sort_type: general(综合) / time_descending(最新) / popularity_descending(最热)
    note_type: 0=不限, 1=视频, 2=图文
    note_time: 0=不限, 1=一天内, 2=一周内, 3=半年内
    """
    results = []

    # 构建搜索 URL，追加支持的查询参数
    query_parts = [f"keyword={keyword}", "source=web_explore_feed"]
    if sort_type and sort_type != "general":
        query_parts.append(f"sort={sort_type}")
    # note_type 和 note_time 在 XHS web 搜索页可能通过 URL 参数生效
    if note_type and note_type > 0:
        query_parts.append(f"note_type={note_type}")
    if note_time and note_time > 0:
        query_parts.append(f"note_time={note_time}")
    search_url = f"https://www.xiaohongshu.com/search_result?{'&'.join(query_parts)}"

    logger.info(
        "搜索: keyword=%s sort=%s note_type=%s note_time=%s",
        keyword, sort_type, note_type, note_time,
    )
    try:
        page.get(search_url)
        time.sleep(3)

        if not _wait_initial_state(page):
            logger.warning(f"搜索页 __INITIAL_STATE__ 未加载，关键词：{keyword}")
            return results

        # 兼容 .value 和 ._value 两种属性名（参考 xiaohongshu-mcp feeds.go）
        feeds = _run_js(page, """
            return JSON.stringify((() => {
                const state = window.__INITIAL_STATE__;
                if (!state?.search?.feeds) return null;
                const f = state.search.feeds;
                return f.value !== undefined ? f.value : f._value;
            })())
        """)

        if not feeds:
            logger.warning(f"未找到搜索结果，关键词：{keyword}")
            return results

        logger.info(f"找到 {len(feeds)} 条笔记，关键词：{keyword}")

        for feed in feeds[:limit]:
            try:
                feed_id = feed.get("id", "")
                xsec_token = feed.get("xsecToken", "")
                if not feed_id:
                    continue

                note_card = feed.get("noteCard", {})
                title = note_card.get("displayTitle", "")
                user = note_card.get("user", {})
                author = user.get("nickname", "") or user.get("nickName", "")
                interact = note_card.get("interactInfo", {})
                likes = _parse_count(interact.get("likedCount", "0"))
                source_url = f"https://www.xiaohongshu.com/explore/{feed_id}"

                content, images, collects, comments = _get_detail(page, feed_id, xsec_token)
                time.sleep(_DETAIL_INTERVAL)

                results.append({
                    "id": feed_id,
                    "title": title,
                    "content": content or title,
                    "author": author,
                    "likes": likes,
                    "collects": collects,
                    "comments": comments,
                    "source_url": source_url,
                    "images": images,
                })
            except Exception as e:
                logger.debug(f"解析 feed 出错: {e}")
                continue

    except Exception as e:
        logger.error(f"搜索出错: {e}")

    return results


# 入库批次大小：每 N 条 commit 一次，避免单次失败全部回滚
_SAVE_BATCH_SIZE = 20

# 采集结果备份目录
_BACKUP_DIR = Path(__file__).parent.parent.parent / "data" / "collect_backups"


def _get_backup_path(park_id: str) -> Path:
    """获取采集备份文件路径"""
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return _BACKUP_DIR / f"backup_{park_id}.json"


async def save_strategies(
    park_id: str,
    items: list[dict],
    existing_strategy_ids: set[str] | None = None,
    batch_size: int = _SAVE_BATCH_SIZE,
) -> list[dict]:
    """
    将采集到的攻略分批保存到数据库，跳过已存在的。
    每 batch_size 条 commit 一次，避免全部失败回滚。
    返回新入库的 item 列表（供后续 AI 提炼使用）。

    自动跳过空内容条目（反爬拦截/已删除笔记）。
    """
    new_items = []
    known_ids = set(existing_strategy_ids or set())
    skipped_empty = 0
    batch: list[dict] = []

    async with AsyncSessionLocal() as session:
        for item in items:
            source_url = item.get("source_url", "")
            if not source_url:
                continue

            strategy_id = hashlib.md5(source_url.encode()).hexdigest()
            item["id"] = strategy_id

            if strategy_id in known_ids:
                continue

            content = item.get("content", "")
            title = item.get("title", "")

            # 跳过空内容条目（反爬拦截/已删除笔记/仅App可见）
            if not title and not content:
                skipped_empty += 1
                logger.debug(f"跳过空内容条目: {source_url}")
                continue

            strategy = Strategy(
                id=strategy_id,
                park_id=park_id,
                platform="xhs",
                source_url=source_url,
                title=title,
                content=content,
                author=item.get("author", ""),
                likes=item.get("likes", 0),
                collects=item.get("collects", 0),
                comments=item.get("comments", 0),
                tags=[],
                mentioned_attractions=_extract_mentioned_attractions(content, park_id),
                image_urls=item.get("images", []),
            )
            session.add(strategy)
            new_items.append(item)
            batch.append(item)
            known_ids.add(strategy_id)

            # 分批提交，避免全部丢失
            if len(batch) >= batch_size:
                await session.commit()
                logger.debug(f"已提交批次 {len(batch)} 条（累计 {len(new_items)} 条）")
                batch.clear()

        # 提交剩余批次
        if batch:
            await session.commit()
            logger.debug(f"已提交最后批次 {len(batch)} 条（累计 {len(new_items)} 条）")

        if skipped_empty > 0:
            logger.info(f"跳过 {skipped_empty} 条空内容条目（反爬拦截/已删除/需App查看）")
    return new_items


async def load_existing_strategy_ids(park_id: str, platform: str = "xhs") -> set[str]:
    """加载指定乐园下已入库攻略的 ID，用于采集前去重。"""
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Strategy.id).where(Strategy.park_id == park_id, Strategy.platform == platform)
        )
        return set(result.scalars().all())


async def apply_ai_summaries(new_items: list[dict], park_id: str = "") -> None:
    """对新入库的攻略批量调用 AI 提炼，将摘要写回数据库"""
    ai_config = resolve_distill_ai_config()
    if not ai_config:
        logger.warning("未配置可用的 AI 提炼配置，跳过 AI 提炼步骤")
        return

    logger.info(
        "开始 AI 提炼，共 %d 条攻略…（api_mode=%s, code=%s, park_id=%s）",
        len(new_items),
        ai_config["api_mode"],
        ai_config.get("code", ""),
        park_id,
    )
    results = await distill_batch(
        new_items,
        api_key=ai_config["api_key"],
        base_url=ai_config.get("base_url") or None,
        api_mode=ai_config.get("api_mode", "anthropic"),
        model=ai_config.get("model", ""),
        park_id=park_id,
    )

    if not results:
        logger.info("AI 提炼无结果")
        return

    async with AsyncSessionLocal() as session:
        for strategy_id, data in results.items():
            strategy = await session.get(Strategy, strategy_id)
            if strategy:
                if data.get("ai_summary"):
                    strategy.ai_summary = data["ai_summary"]
                if data.get("structured"):
                    strategy.structured_summary = data["structured"]
        await session.commit()

    logger.info(f"AI 提炼完成，成功提炼 {len(results)} 条")


async def collect(
    park_id: str = "hongkong_disney",
    limit_per_keyword: int = 20,
    enable_distill: bool = True,
    force_login: bool = False,
    login_only: bool = False,
    offset: int = 0,
    max_total: int | None = None,
    keyword_scope: str = "extended",
    resume: bool = False,
    sort_type: str = "general",
    note_type: int = 0,
    note_time: int = 0,
):
    """采集主流程。

    如果 resume=True，跳过浏览器采集阶段，直接从本地备份文件加载数据入库。

    sort_type: general(综合) / time_descending(最新) / popularity_descending(最热)
    note_type: 0=不限, 1=视频, 2=图文
    note_time: 0=不限, 1=一天内, 2=一周内, 3=半年内
    """
    # ── resume 模式：从本地备份恢复 ──
    if resume:
        backup_path = _get_backup_path(park_id)
        if not backup_path.exists():
            logger.error(f"备份文件不存在: {backup_path}")
            return

        logger.info(f"从备份文件恢复: {backup_path}")
        all_items = json.loads(backup_path.read_text(encoding="utf-8"))
        logger.info(f"加载 {len(all_items)} 条备份数据")

        existing_strategy_ids = await load_existing_strategy_ids(park_id)

        # 过滤掉已入库的
        pending = []
        skipped = 0
        for item in all_items:
            sid = hashlib.md5(item.get("source_url", "").encode()).hexdigest()
            if sid in existing_strategy_ids:
                skipped += 1
            else:
                pending.append(item)

        if skipped:
            logger.info(f"跳过 {skipped} 条已入库的")

        if not pending:
            logger.info("所有备份数据已入库，删除备份文件")
            backup_path.unlink()
            return

        logger.info(f"待入库 {len(pending)} 条")
        new_items = await save_strategies(park_id, pending, existing_strategy_ids)

        # 入库成功，删除备份；失败则保留供下次重试
        if new_items:
            logger.info(f"从备份恢复入库 {len(new_items)} 条")
            # 重新读取备份，移除已入库的，保留未入库的
            remaining = [i for i in all_items
                         if hashlib.md5(i.get("source_url", "").encode()).hexdigest()
                         not in existing_strategy_ids
                         and hashlib.md5(i.get("source_url", "").encode()).hexdigest()
                         not in {hashlib.md5(n.get("source_url", "").encode()).hexdigest() for n in new_items}]
            if remaining:
                backup_path.write_text(json.dumps(remaining, ensure_ascii=False, indent=2), encoding="utf-8")
                logger.warning(f"仍有 {len(remaining)} 条未入库，备份已更新")
            else:
                backup_path.unlink()
                logger.info("所有备份数据已入库，备份文件已删除")

        if enable_distill and new_items:
            await apply_ai_summaries(new_items, park_id=park_id)
        return

    # ── 正常采集模式 ──
    if not DRISSION_AVAILABLE:
        logger.error("DrissionPage 未安装，无法运行采集器")
        return

    keywords = _generate_search_keywords(park_id, scope=keyword_scope)
    if not keywords:
        logger.error(f"未找到乐园 {park_id} 的关键词配置")
        return

    logger.info(f"开始采集 {park_id} 攻略，关键词范围={keyword_scope}，共 {len(keywords)} 个关键词：{keywords}")
    page = create_browser()

    try:
        wait_for_login(page, force=force_login or login_only)

        if login_only:
            logger.info("XHS: 登录模式完成，按需退出采集器")
            return

        all_items: list[dict] = []
        seen_urls: set[str] = set()
        existing_strategy_ids = await load_existing_strategy_ids(park_id)
        skipped_existing = 0
        skipped_duplicate = 0
        skipped_offset = 0
        skipped_max_total = 0
        item_counter = 0

        for keyword in keywords:
            if max_total is not None and len(all_items) >= max_total:
                logger.info(f"已达到最大采集数 {max_total}，停止采集")
                break

            logger.info(f"搜索关键词：{keyword}")
            items = search_xhs(
                page, keyword,
                limit=limit_per_keyword,
                sort_type=sort_type,
                note_type=note_type,
                note_time=note_time,
            )

            for item in items:
                item_counter += 1

                if item_counter <= offset:
                    skipped_offset += 1
                    continue

                if max_total is not None and len(all_items) >= max_total:
                    skipped_max_total += 1
                    continue

                url = item.get("source_url", "")
                if not url:
                    continue

                if url in seen_urls:
                    skipped_duplicate += 1
                    continue

                strategy_id = hashlib.md5(url.encode()).hexdigest()
                item["id"] = strategy_id

                if strategy_id in existing_strategy_ids:
                    skipped_existing += 1
                    continue

                seen_urls.add(url)
                all_items.append(item)

            time.sleep(2)

        logger.info(
            "共采集 %d 条去重后的攻略（本轮内重复 %d 条，数据库已存在 %d 条，offset 跳过 %d 条，max_total 截断 %d 条）",
            len(all_items),
            skipped_duplicate,
            skipped_existing,
            skipped_offset,
            skipped_max_total,
        )

        # ═══ 先落本地备份，再入库 ═══
        backup_path = _get_backup_path(park_id)
        backup_path.write_text(
            json.dumps(all_items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"采集结果已保存到本地备份: {backup_path}")

        new_items = await save_strategies(park_id, all_items, existing_strategy_ids=existing_strategy_ids)
        logger.info(f"新入库 {len(new_items)} 条攻略")

        # 入库成功，清理本地备份
        if new_items:
            # 检查是否还有未入库的（如空内容被跳过的）
            saved_ids = {hashlib.md5(item.get("source_url", "").encode()).hexdigest() for item in new_items}
            all_ids = {hashlib.md5(item.get("source_url", "").encode()).hexdigest() for item in all_items}
            unsaved_ids = all_ids - saved_ids
            if unsaved_ids:
                remaining = [i for i in all_items
                             if hashlib.md5(i.get("source_url", "").encode()).hexdigest() in unsaved_ids]
                backup_path.write_text(json.dumps(remaining, ensure_ascii=False, indent=2), encoding="utf-8")
                logger.info(f"备份已更新：{len(remaining)} 条未入库（空内容/反爬），可用 --resume 重试")
            else:
                backup_path.unlink()
                logger.info("所有条目已入库，备份文件已删除")

        if enable_distill and new_items:
            await apply_ai_summaries(new_items, park_id=park_id)

    finally:
        page.quit()


if __name__ == "__main__":
    import argparse
    configure_logging()
    logging.getLogger(__name__).setLevel(logging.INFO)

    parser = argparse.ArgumentParser(description="迪士尼攻略采集器")
    parser.add_argument("--park", default="hongkong_disney", choices=list(_BASE_KEYWORDS.keys()))
    parser.add_argument("--limit", type=int, default=20, help="每个关键词采集数量")
    parser.add_argument("--offset", type=int, default=0, help="跳过前 N 条搜索结果（用于续采或避免重复采集热门笔记）")
    parser.add_argument("--max-total", type=int, default=None, help="限制本次采集的总条数上限（不含数据库已有）")
    parser.add_argument("--no-distill", action="store_true", help="跳过 AI 提炼步骤")
    parser.add_argument("--force-login", action="store_true", help="忽略已保存登录态，强制重新登录")
    parser.add_argument("--login-only", action="store_true", help="仅执行登录，不开始采集")
    parser.add_argument("--keyword-scope", default="extended", choices=["basic", "extended", "full"],
                       help="关键词范围：basic(基础4-5个) / extended(基础+场景~15个) / full(全部~30个)")
    parser.add_argument("--resume", action="store_true",
                       help="从本地备份文件恢复入库（跳过浏览器采集，仅执行 DB 写入+提炼）")
    parser.add_argument("--sort", default="general",
                       choices=["general", "time_descending", "popularity_descending"],
                       help="搜索排序方式：general(综合,默认) / time_descending(最新) / popularity_descending(最热)")
    parser.add_argument("--note-type", type=int, default=0, choices=[0, 1, 2],
                       help="笔记类型过滤：0=不限, 1=视频, 2=图文")
    parser.add_argument("--note-time", type=int, default=0, choices=[0, 1, 2, 3],
                       help="笔记时间过滤：0=不限, 1=一天内, 2=一周内, 3=半年内")
    args = parser.parse_args()

    asyncio.run(collect(
        park_id=args.park,
        limit_per_keyword=args.limit,
        enable_distill=not args.no_distill,
        force_login=args.force_login,
        login_only=args.login_only,
        offset=args.offset,
        max_total=args.max_total,
        keyword_scope=args.keyword_scope,
        resume=args.resume,
        sort_type=args.sort,
        note_type=args.note_type,
        note_time=args.note_time,
    ))
