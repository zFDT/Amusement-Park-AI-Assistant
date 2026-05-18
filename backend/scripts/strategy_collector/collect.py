"""
香港/上海迪士尼乐园攻略采集器
基于 DrissionPage（Chrome 自动化），采集小红书图文攻略并入库。

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
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.park import Strategy

logger = logging.getLogger(__name__)

try:
    from DrissionPage import ChromiumPage, ChromiumOptions
    DRISSION_AVAILABLE = True
except ImportError:
    DRISSION_AVAILABLE = False
    logger.warning("DrissionPage not installed. Run: pip install DrissionPage")

BROWSER_DATA_DIR = Path(__file__).parent.parent.parent / "browser_data" / "xhs"
XHS_PORT = 9521

PARK_KEYWORDS = {
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

# 各乐园项目名称，用于从文本中提取提及的项目
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


def create_browser() -> "ChromiumPage":
    BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    co = ChromiumOptions()
    co.set_user_data_path(str(BROWSER_DATA_DIR))
    co.set_local_port(XHS_PORT)
    co.set_argument("--disable-blink-features=AutomationControlled")
    co.set_argument("--no-first-run")
    return ChromiumPage(co)


def wait_for_login(page: "ChromiumPage") -> None:
    page.get("https://www.xiaohongshu.com")
    time.sleep(3)
    avatar = page.ele("css:.user-avatar", timeout=3) or page.ele("css:[class*='avatar']", timeout=2)
    if avatar:
        logger.info("XHS: 已登录（复用上次 session）")
        return
    logger.info("XHS: 需要登录，请在浏览器中完成登录")
    input(">>> 小红书登录完成后，按回车继续...")


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


def _get_detail_by_click(page: "ChromiumPage", item) -> tuple[str, list[str], int, int]:
    """
    点击笔记卡片，进入详情弹窗，提取：
    - content: 正文文字
    - images: 图片 URL 列表（xhscdn 域名）
    - collects: 收藏数
    - comments: 评论数
    """
    content = ""
    images: list[str] = []
    collects = 0
    comments = 0

    try:
        item.click()
        time.sleep(2)

        # 正文
        desc_el = (
            page.ele("css:.note-content .desc", timeout=3)
            or page.ele("css:#detail-desc", timeout=2)
            or page.ele("css:[class*='note-text']", timeout=2)
        )
        if desc_el:
            content = desc_el.text

        # 图片：取所有 xhscdn 图片，去重保序
        seen: set[str] = set()
        for img in page.eles("css:.note-content img", timeout=2):
            src = img.attr("src") or ""
            if "xhscdn" in src and src not in seen:
                seen.add(src)
                images.append(src)
        # 备用：swiper 轮播图
        if not images:
            for img in page.eles("css:.swiper-slide img", timeout=1):
                src = img.attr("src") or ""
                if src and src not in seen:
                    seen.add(src)
                    images.append(src)

        # 互动数据（收藏、评论）
        collect_el = page.ele("css:[class*='collect'] [class*='count']", timeout=1)
        if collect_el:
            collects = _parse_count(collect_el.text)

        comment_el = page.ele("css:[class*='comment'] [class*='count']", timeout=1)
        if comment_el:
            comments = _parse_count(comment_el.text)

    except Exception as e:
        logger.debug(f"获取详情出错: {e}")
    finally:
        # 关闭详情弹窗
        try:
            close_btn = page.ele("css:[class*='close']", timeout=1)
            if close_btn:
                close_btn.click()
            else:
                page.actions.key_down("ESCAPE").key_up("ESCAPE")
        except Exception:
            pass
        time.sleep(0.5)

    return content, images, collects, comments


def search_xhs(page: "ChromiumPage", keyword: str, limit: int = 20) -> list[dict]:
    """搜索小红书，返回笔记列表（含图片 URL）"""
    results = []
    try:
        search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&type=51"
        page.get(search_url)
        time.sleep(3)

        for _ in range(15):
            sections = page.eles("css:.note-item", timeout=2)
            if sections:
                break
            time.sleep(1)

        note_items = page.eles("css:.note-item")
        logger.info(f"找到 {len(note_items)} 条笔记，关键词：{keyword}")

        for idx, item in enumerate(note_items[:limit]):
            try:
                title_el = item.ele("css:.title", timeout=1)
                title = title_el.text if title_el else ""

                author_el = item.ele("css:.author-wrapper .name", timeout=1)
                author = author_el.text if author_el else ""

                likes_el = item.ele("css:.like-wrapper .count", timeout=1)
                likes_text = likes_el.text if likes_el else "0"

                link_el = item.ele("css:a", timeout=1)
                href = link_el.attr("href") if link_el else ""
                note_url = href if href.startswith("http") else f"https://www.xiaohongshu.com{href}" if href else ""

                content, images, collects, comments = _get_detail_by_click(page, item)

                results.append({
                    "id": href.split("/")[-1] if href else "",
                    "title": title,
                    "content": content or title,
                    "author": author,
                    "likes": _parse_count(likes_text),
                    "collects": collects,
                    "comments": comments,
                    "source_url": note_url,
                    "images": images,
                })
            except Exception as e:
                logger.debug(f"解析笔记 {idx} 出错: {e}")
                continue

    except Exception as e:
        logger.error(f"搜索出错: {e}")

    return results


async def save_strategies(park_id: str, items: list[dict]) -> list[dict]:
    """
    将采集到的攻略保存到数据库，跳过已存在的。
    返回新入库的 item 列表（供后续 AI 提炼使用）。
    """
    new_items = []
    async with AsyncSessionLocal() as session:
        for item in items:
            source_url = item.get("source_url", "")
            if not source_url:
                continue

            strategy_id = hashlib.md5(source_url.encode()).hexdigest()
            item["id"] = strategy_id  # 回写 id，供提炼时使用

            existing = await session.get(Strategy, strategy_id)
            if existing:
                continue

            content = item.get("content", "")
            strategy = Strategy(
                id=strategy_id,
                park_id=park_id,
                platform="xhs",
                source_url=source_url,
                title=item.get("title", ""),
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

        await session.commit()
    return new_items


async def apply_ai_summaries(new_items: list[dict]) -> None:
    """对新入库的攻略批量调用 AI 提炼，将摘要写回数据库"""
    from scripts.strategy_collector.distill import distill_batch

    api_key = settings.anthropic_api_key
    if not api_key:
        logger.warning("未配置 ANTHROPIC_API_KEY，跳过 AI 提炼步骤")
        return

    logger.info(f"开始 AI 提炼，共 {len(new_items)} 条攻略…")
    summaries = await distill_batch(new_items, api_key=api_key)

    if not summaries:
        logger.info("AI 提炼无结果")
        return

    async with AsyncSessionLocal() as session:
        for strategy_id, summary in summaries.items():
            strategy = await session.get(Strategy, strategy_id)
            if strategy:
                strategy.ai_summary = summary
        await session.commit()

    logger.info(f"AI 提炼完成，成功提炼 {len(summaries)} 条")


async def collect(
    park_id: str = "hongkong_disney",
    limit_per_keyword: int = 20,
    enable_distill: bool = True,
):
    if not DRISSION_AVAILABLE:
        logger.error("DrissionPage 未安装，无法运行采集器")
        return

    keywords = PARK_KEYWORDS.get(park_id, [])
    if not keywords:
        logger.error(f"未找到乐园 {park_id} 的关键词配置")
        return

    logger.info(f"开始采集 {park_id} 攻略，关键词：{keywords}")
    page = create_browser()

    try:
        wait_for_login(page)

        all_items: list[dict] = []
        seen_urls: set[str] = set()

        for keyword in keywords:
            logger.info(f"搜索关键词：{keyword}")
            items = search_xhs(page, keyword, limit=limit_per_keyword)

            for item in items:
                url = item.get("source_url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_items.append(item)

            time.sleep(2)

        logger.info(f"共采集 {len(all_items)} 条去重后的攻略")

        new_items = await save_strategies(park_id, all_items)
        logger.info(f"新入库 {len(new_items)} 条攻略（跳过已存在的）")

        if enable_distill and new_items:
            await apply_ai_summaries(new_items)

    finally:
        page.quit()


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="迪士尼攻略采集器")
    parser.add_argument("--park", default="hongkong_disney", choices=list(PARK_KEYWORDS.keys()))
    parser.add_argument("--limit", type=int, default=20, help="每个关键词采集数量")
    parser.add_argument("--no-distill", action="store_true", help="跳过 AI 提炼步骤")
    args = parser.parse_args()

    asyncio.run(collect(
        park_id=args.park,
        limit_per_keyword=args.limit,
        enable_distill=not args.no_distill,
    ))
