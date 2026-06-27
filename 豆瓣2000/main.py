import requests
from bs4 import BeautifulSoup
import time
import re
import random
import json
import sys
from urllib.parse import quote

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Referer": "https://movie.douban.com/explore",
}

# 豆瓣按标签浏览API（tag参数支持中文标签，翻页稳定）
SEARCH_SUBJECTS_URL = "https://movie.douban.com/j/search_subjects?type=movie&tag={tag}&sort=recommend&page_limit=20&page_start={start}"
# 豆瓣高级搜索API（备用，按评分排序）
NEW_SEARCH_URL = "https://movie.douban.com/j/new_search_subjects?sort=S&range=0,10&tags=电影&start={start}&genres={genre}&countries={country}"

MAX_RETRIES = 3
TARGET_COUNT = 2000

# 类型标签列表，每个类型可独立翻页获取不同电影
GENRE_TAGS = [
    "剧情", "喜剧", "动作", "爱情", "科幻", "悬疑", "惊悚", "恐怖",
    "犯罪", "战争", "动画", "奇幻", "冒险", "纪录片", "音乐", "历史",
    "传记", "运动", "家庭", "武侠", "古装", "灾难", "情色", "同性",
]

session = requests.Session()
session.headers.update(HEADERS)


def get_json(url, retries=0):
    """请求JSON API，带重试和反验证逻辑"""
    try:
        resp = session.get(url, timeout=15, allow_redirects=True)
        if "sec.douban.com" in resp.url or "verify" in resp.url:
            if retries < MAX_RETRIES:
                wait = 20 * (retries + 1) + random.uniform(3, 8)
                print(f"    触发验证页面，等待 {wait:.1f}s 后重试...")
                time.sleep(wait)
                return get_json(url, retries + 1)
            print(f"    多次重试仍触发验证，跳过")
            return None
        if resp.status_code == 404:
            return None
        if resp.status_code == 403:
            if retries < MAX_RETRIES:
                wait = 20 * (retries + 1) + random.uniform(3, 8)
                print(f"    触发403，等待 {wait:.1f}s 后重试...")
                time.sleep(wait)
                return get_json(url, retries + 1)
            print(f"    多次重试仍403，跳过")
            return None
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        if retries < MAX_RETRIES:
            wait = 20 * (retries + 1) + random.uniform(3, 8)
            print(f"    请求异常({type(e).__name__})，等待 {wait:.1f}s 后重试...")
            time.sleep(wait)
            return get_json(url, retries + 1)
        print(f"    多次重试仍失败，跳过")
        return None
    except (json.JSONDecodeError, ValueError) as e:
        print(f"    JSON解析失败: {e}")
        return None


def _extract_names(items):
    """从API返回的列表中提取名称，兼容字符串和字典两种格式"""
    names = []
    for item in items:
        if isinstance(item, dict):
            name = item.get("name", "")
        else:
            name = str(item) if item else ""
        if name:
            names.append(name)
    return names


def parse_new_search(data):
    """解析 new_search_subjects JSON API 返回的数据（更详细）"""
    movies = []
    subjects = data.get("data", [])
    for s in subjects:
        director_names = _extract_names(s.get("directors", []))
        cast_names = _extract_names(s.get("casts", []))
        countries = s.get("countries", [])
        genres = s.get("genres", [])
        movie = {
            "名称": s.get("title", ""),
            "链接": s.get("url", ""),
            "评分": s.get("rate", ""),
            "评分人数": str(s.get("vote_count", "")),
            "导演": ", ".join(director_names[:3]),
            "主演": ", ".join(cast_names[:5]),
            "上映年份": str(s.get("year", "")),
            "国家": " / ".join(countries),
            "类型": ", ".join(genres),
            "片长": "",
        }
        movies.append(movie)
    return movies


def parse_search_subjects(data, tag=""):
    """解析 search_subjects JSON API 返回的数据（tag参数稳定可用）"""
    movies = []
    subjects = data.get("subjects", [])
    for s in subjects:
        movie = {
            "名称": s.get("title", ""),
            "链接": s.get("url", ""),
            "评分": s.get("rate", ""),
            "评分人数": "",
            "导演": "",
            "主演": "",
            "上映年份": "",
            "国家": "",
            "类型": tag,
            "片长": "",
        }
        movies.append(movie)
    return movies


def get_detail_info(link):
    """从详情页获取类型和更多信息"""
    try:
        resp = session.get(link, timeout=15, allow_redirects=True)
        if "sec.douban.com" in resp.url or "verify" in resp.url or resp.status_code != 200:
            return {}
        soup = BeautifulSoup(resp.text, "html.parser")
        info = {}
        genre_tags = soup.select("span[property='v:genre']")
        if genre_tags:
            info["类型"] = ", ".join([g.get_text(strip=True) for g in genre_tags])
        info_div = soup.select_one("#info")
        if info_div:
            text = info_div.get_text()
            country_match = re.search(r"制片国家/地区:\s*(.+)", text)
            if country_match:
                info["国家"] = country_match.group(1).strip()
        return info
    except Exception:
        return {}


def init_session():
    """初始化会话，获取Cookie"""
    print("=" * 60)
    print("  豆瓣电影爬虫 - 爬取2000部电影并筛选")
    print("=" * 60)
    print("\n正在初始化会话，获取Cookie...")
    try:
        resp = session.get("https://movie.douban.com/", timeout=15)
        time.sleep(random.uniform(2, 4))
        print(f"Cookie获取成功 (状态码: {resp.status_code})\n")
    except requests.exceptions.RequestException as e:
        print(f"Cookie获取失败: {e}，继续尝试...\n")


def crawl_top_movies(all_movies, seen_links, target=2000):
    """通过 search_subjects API 按类型标签逐个爬取，合并去重达到目标数量"""
    print(f"\n  正在通过标签API爬取Top {target} 部电影...")

    for tag in GENRE_TAGS:
        if len(all_movies) >= target:
            break

        start = 0
        empty_count = 0
        tag_new = 0
        print(f"\n  [{tag}] 开始爬取...")

        while len(all_movies) < target:
            url = SEARCH_SUBJECTS_URL.format(tag=quote(tag), start=start)
            data = get_json(url)
            if data is None:
                break

            movies = parse_search_subjects(data, tag=tag)
            if not movies:
                empty_count += 1
                if empty_count >= 2:
                    break
                start += 20
                time.sleep(random.uniform(4, 8))
                continue

            empty_count = 0
            new_count = 0
            for m in movies:
                link = m.get("链接", "")
                if link and link not in seen_links:
                    seen_links.add(link)
                    all_movies.append(m)
                    new_count += 1
                    tag_new += 1

            page = start // 20 + 1
            if new_count > 0:
                print(f"    第 {page} 页: 新增 {new_count} 部 (总计: {len(all_movies)})")

            # 本页全部重复或无新数据
            if new_count == 0:
                empty_count += 1
                if empty_count >= 2:
                    break

            start += 20
            time.sleep(random.uniform(3, 6))

        if tag_new > 0:
            print(f"  [{tag}] 新增 {tag_new} 部 (总计: {len(all_movies)})")

    print(f"\n  API爬取完成，共获取 {len(all_movies)} 部电影")


def enrich_details(movies):
    """对筛选后的电影补充详情（类型、国家等）"""
    need_enrich = [m for m in movies if not m.get("类型") or not m.get("国家")]
    if not need_enrich:
        return
    print(f"\n  正在为 {len(need_enrich)} 部筛选结果补充详情...")
    success = 0
    fail = 0
    for i, movie in enumerate(need_enrich):
        link = movie.get("链接", "")
        if not link:
            continue
        print(f"  详情 {i+1}/{len(need_enrich)}: {movie.get('名称', '未知')}")
        detail = get_detail_info(link)
        if detail:
            if "类型" in detail and detail["类型"]:
                movie["类型"] = detail["类型"]
            if "国家" in detail and detail["国家"]:
                movie["国家"] = detail["国家"]
            success += 1
        else:
            fail += 1
        time.sleep(random.uniform(1.5, 3.5))
    print(f"  详情补充完成: 成功 {success} 部, 失败 {fail} 部")


# 默认筛选参数（"我喜欢的电影"偏好设置）
DEFAULT_FILTERS = {
    "genre": "剧情,科幻,犯罪",
    "actor": "",
    "region": "",
    "min_rating": "8.0",
    "plot": "",
}


def filter_movies(all_movies):
    """筛选电影，支持交互模式和默认模式"""
    print("\n" + "=" * 60)
    print("  电影筛选")
    print("=" * 60)

    if len(sys.argv) > 1:
        genre_filter = sys.argv[1] if len(sys.argv) > 1 else ""
        actor_filter = sys.argv[2] if len(sys.argv) > 2 else ""
        region_filter = sys.argv[3] if len(sys.argv) > 3 else ""
        min_rating = sys.argv[4] if len(sys.argv) > 4 else ""
        plot_filter = sys.argv[5] if len(sys.argv) > 5 else ""
        print("\n  [使用命令行参数进行筛选]")
    else:
        try:
            print("\n可用筛选条件（直接回车跳过该条件，输入 d 使用默认偏好）：")
            print(f"  默认偏好 -> 类型: {DEFAULT_FILTERS['genre']} | 最低评分: {DEFAULT_FILTERS['min_rating']}")
            print("  1. 电影类型（如：剧情, 喜剧, 动作, 科幻, 爱情, 犯罪, 动画 等）")
            print("  2. 主演（如：张国荣, 梁朝伟, 周星驰 等）")
            print("  3. 地区（如：美国, 日本, 中国大陆, 韩国, 英国 等）")
            print("  4. 最低评分（如：8.0）")
            print("  5. 剧情关键词（如：经典, 感人, 烧脑 等）")

            genre_filter = input("\n请输入电影类型（多个用逗号分隔，如 剧情,科幻）: ").strip()
            actor_filter = input("请输入主演关键词（如 周星驰）: ").strip()
            region_filter = input("请输入地区（如 美国,日本）: ").strip()
            min_rating = input("请输入最低评分（如 8.0）: ").strip()
            plot_filter = input("请输入剧情/名称关键词: ").strip()

            if genre_filter.lower() == 'd':
                genre_filter = DEFAULT_FILTERS['genre']
                actor_filter = DEFAULT_FILTERS['actor']
                region_filter = DEFAULT_FILTERS['region']
                min_rating = DEFAULT_FILTERS['min_rating']
                plot_filter = DEFAULT_FILTERS['plot']
                print("  已使用默认偏好设置")
        except EOFError:
            print("\n  [非交互模式，使用默认偏好筛选]")
            genre_filter = DEFAULT_FILTERS['genre']
            actor_filter = DEFAULT_FILTERS['actor']
            region_filter = DEFAULT_FILTERS['region']
            min_rating = DEFAULT_FILTERS['min_rating']
            plot_filter = DEFAULT_FILTERS['plot']

    results = all_movies[:]

    if genre_filter:
        keywords = [k.strip() for k in genre_filter.replace("，", ",").split(",") if k.strip()]
        results = [m for m in results if any(kw in m.get("类型", "") for kw in keywords)]
        print(f"  按类型[{genre_filter}]筛选后: {len(results)} 部")

    if actor_filter:
        results = [m for m in results if actor_filter in m.get("主演", "")]
        print(f"  按主演[{actor_filter}]筛选后: {len(results)} 部")

    if region_filter:
        keywords = [k.strip() for k in region_filter.replace("，", ",").split(",") if k.strip()]
        results = [m for m in results if any(kw in m.get("国家", "") for kw in keywords)]
        print(f"  按地区[{region_filter}]筛选后: {len(results)} 部")

    if min_rating:
        try:
            min_r = float(min_rating)
            results = [m for m in results if m.get("评分") and float(m["评分"]) >= min_r]
            print(f"  按评分>={min_r}筛选后: {len(results)} 部")
        except ValueError:
            print("  评分格式错误，跳过评分筛选")

    if plot_filter:
        results = [m for m in results if plot_filter in m.get("名称", "") or plot_filter in m.get("类型", "")]
        print(f"  按关键词[{plot_filter}]筛选后: {len(results)} 部")

    results.sort(key=lambda x: float(x.get("评分", "0")) if x.get("评分") else 0, reverse=True)
    return results


def display_movies(movies, limit=10):
    """展示电影列表"""
    print(f"\n{'=' * 80}")
    print(f"  筛选结果（共 {len(movies)} 部，展示前 {min(limit, len(movies))} 部）")
    print(f"{'=' * 80}")
    display_list = movies[:limit]
    for i, m in enumerate(display_list, 1):
        print(f"\n  【{i}】{m.get('名称', '未知')}")
        print(f"      评分: {m.get('评分', 'N/A')}  评分人数: {m.get('评分人数', 'N/A')}")
        print(f"      导演: {m.get('导演', 'N/A')}")
        print(f"      主演: {m.get('主演', 'N/A')}")
        print(f"      年份: {m.get('上映年份', 'N/A')}  地区: {m.get('国家', 'N/A')}")
        print(f"      类型: {m.get('类型', 'N/A')}")
        print(f"      片长: {m.get('片长', 'N/A')}")
        print(f"      链接: {m.get('链接', 'N/A')}")
    return display_list


def show_resource_guide(movies):
    """展示电影资源寻找指南"""
    print(f"\n{'=' * 80}")
    print(f"  电影播放源 / 资源寻找指南")
    print(f"{'=' * 80}")
    print("""
  ┌─────────────────────────────────────────────────────────────────┐
  │                    免费合法观影渠道推荐                          │
  ├─────────────────────────────────────────────────────────────────┤
  │                                                                 │
  │  1. 主流视频平台（免费/会员）                                    │
  │     - 哔哩哔哩 (bilibili.com)                                   │
  │       大量免费正版电影，尤其是经典老片和纪录片                    │
  │     - 优酷 (youku.com) / 爱奇艺 (iqiyi.com)                     │
  │       / 腾讯视频 (v.qq.com)                                     │
  │       三大视频平台，部分电影免费，VIP可看更多                    │
  │     - 西瓜视频 (ixigua.com)                                     │
  │       免费电影资源较多                                           │
  │                                                                 │
  │  2. 豆瓣链接直达                                                 │
  │     每部电影的豆瓣页面通常有"在哪里看"的入口                      │
  │     可以直接跳转到可播放的平台                                   │
  │                                                                 │
  │  3. 搜索引擎技巧                                                 │
  │     - 搜索格式: "电影名 + 在线观看 / 免费观看"                   │
  │     - 搜索格式: "电影名 + 播放源"                                │
  │     - 使用搜索引擎搜索电影名 + "在线观看"                        │
  │       通常会在右侧出现播放源链接                                 │
  │                                                                 │
  │  4. 资源聚合搜索                                                 │
  │     - 茶杯狐 (cupfox.app) - 影视资源聚合搜索                    │
  │     - 片库网 (pianku.net) - 影视资源索引                        │
  │     - 低端影视 (ddys.pro) - 高质量在线观影                      │
  │     - 注意：以上网站为非官方聚合，请注意甄别安全性                │
  │                                                                 │
  │  5. 资源寻找过程说明                                             │
  │     a. 首先在豆瓣页面查看"可播放平台"                            │
  │     b. 在B站搜索电影名，看是否有免费资源                         │
  │     c. 使用茶杯狐等聚合搜索工具搜索                              │
  │     d. 在主流平台（优爱腾）搜索确认是否有资源                    │
  │     e. 如果以上都没有，可通过搜索引擎查找                        │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘
""")
    if movies:
        print("  以下为筛选出的电影快速搜索链接：\n")
        for i, m in enumerate(movies, 1):
            name = m.get("名称", "未知")
            douban_link = m.get("链接", "")
            search_url = f"https://www.baidu.com/s?wd={name}+在线观看"
            print(f"  {i}. {name}")
            print(f"     豆瓣: {douban_link}")
            print(f"     百度搜索: {search_url}")
            print()


def main():
    init_session()
    all_movies = []
    seen_links = set()

    try:
        crawl_top_movies(all_movies, seen_links, target=TARGET_COUNT)

    except KeyboardInterrupt:
        print(f"\n\n{'=' * 60}")
        print(f"  用户中断爬取，已获取 {len(all_movies)} 部电影")
        print(f"{'=' * 60}")
        if not all_movies:
            print("未获取到任何电影数据，请重新运行。")
            return

    print(f"\n{'=' * 60}")
    print(f"  爬取完成！共获取 {len(all_movies)} 部不重复的电影")
    print(f"{'=' * 60}")

    if not all_movies:
        print("未获取到任何电影数据，请检查网络连接后重试。")
        return

    # 按评分排序
    all_movies.sort(key=lambda x: float(x.get("评分", "0")) if x.get("评分") else 0, reverse=True)

    # 交互式筛选
    filtered = filter_movies(all_movies)

    if not filtered:
        print("\n未筛选到符合条件的电影，显示评分最高的10部：")
        filtered = all_movies[:10]

    # 只对筛选出的电影补充详情
    enrich_details(filtered)
    filtered.sort(key=lambda x: float(x.get("评分", "0")) if x.get("评分") else 0, reverse=True)

    # 展示结果
    display_list = display_movies(filtered, limit=10)

    # 资源寻找指南
    show_resource_guide(display_list)

    # 统计信息
    print(f"\n{'=' * 60}")
    print(f"  统计信息")
    print(f"{'=' * 60}")
    print(f"  总共爬取电影: {len(all_movies)} 部")
    print(f"  筛选后电影: {len(filtered)} 部")

    rating_dist = {"9+": 0, "8-9": 0, "7-8": 0, "6-7": 0, "<6": 0}
    for m in all_movies:
        try:
            r = float(m.get("评分", "0"))
            if r >= 9: rating_dist["9+"] += 1
            elif r >= 8: rating_dist["8-9"] += 1
            elif r >= 7: rating_dist["7-8"] += 1
            elif r >= 6: rating_dist["6-7"] += 1
            else: rating_dist["<6"] += 1
        except ValueError:
            pass
    print(f"\n  评分分布:")
    for k, v in rating_dist.items():
        print(f"    {k}分: {v} 部")

    print(f"\n运行完成！")


if __name__ == "__main__":
    main()
