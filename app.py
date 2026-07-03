import streamlit as st
import feedparser
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
from datetime import datetime, timezone, timedelta
import json
import os
import threading
from urllib.parse import urljoin
from typing import List, Dict, Optional
import time

# ============================================================
# 页面配置与样式
# ============================================================
st.set_page_config(
    page_title="行业情报系统 | Industry Intelligence",
    page_icon="🛰",
    layout="wide",
    initial_sidebar_state="expanded"
)

modern_css = """
<style>
:root {
    --ink: #1a1a1a;
    --paper: #EEEAE3;
    --hair: #ddd6ca;
    --muted: #8a8172;
    --accent: #0f766e;
    --serif: Georgia, 'Times New Roman', 'Noto Serif SC', 'Songti SC', 'SimSun', serif;
}
* { box-sizing: border-box; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
.stDeployButton { display: none; }
header { visibility: hidden; }
html { scroll-behavior: smooth; }

/* ---- 顶部编辑刊物式导航条 ---- */
.masthead {
    background: #1a1a1a;
    border-radius: 10px;
    padding: 16px 22px;
    margin-bottom: 22px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
}
.masthead-brand {
    font-family: var(--serif);
    font-size: 24px;
    font-weight: 600;
    letter-spacing: 1px;
    color: #ffffff;
    line-height: 1;
}
.masthead-tag {
    font-size: 12px;
    color: #b5b5b5;
    letter-spacing: 0.3px;
}

/* ---- 栏目大标题 ---- */
.section-title {
    font-family: var(--serif);
    font-size: 27px;
    font-weight: 600;
    letter-spacing: 0.5px;
    color: var(--ink);
    margin: 6px 0 16px;
}

/* ---- 资讯卡片（编辑风：衬线标题 + 署名） ---- */
.article-card {
    background: #ffffff;
    border: 0.5px solid var(--hair);
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 14px;
    transition: box-shadow 0.2s ease;
}
.article-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); }
.article-title {
    font-family: var(--serif);
    font-size: 19px;
    font-weight: 600;
    margin-bottom: 8px;
    color: var(--ink);
    line-height: 1.4;
}
.article-title a { text-decoration: none; color: inherit; }
.article-title a:hover { color: var(--accent); }
.article-summary { font-size: 13.5px; color: #55503f; margin-bottom: 12px; line-height: 1.65; }
.article-meta {
    display: flex; justify-content: space-between; align-items: center;
    flex-wrap: wrap; gap: 8px; font-size: 12px; color: var(--muted);
    border-top: 0.5px solid var(--hair); padding-top: 10px;
}
.byline { font-size: 12px; color: var(--muted); letter-spacing: 0.2px; }
.badge { display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; }
.badge-source { background: #efece4; color: #55503f; }

/* ---- 作者/交流卡 ---- */
.author-card {
    padding: 4px 2px; font-size: 12.5px; color: #55503f; line-height: 1.7;
}
.author-card b { color: var(--ink); font-weight: 600; }
.author-card a { color: var(--accent); text-decoration: none; }

/* ---- Tab 微调 ---- */
.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stTabs [data-baseweb="tab"] { font-size: 14px; }

.analysis-box {
    background: #ffffff; border: 0.5px solid var(--hair);
    border-radius: 12px; padding: 20px; margin-bottom: 16px;
    white-space: pre-wrap; line-height: 1.8; font-size: 14px; color: var(--ink);
}
</style>
"""
st.markdown(modern_css, unsafe_allow_html=True)

# ============================================================
# 数据源配置
# ============================================================
def load_data_sources():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

# ============================================================
# 存储与缓存管理
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORE_DIR = os.path.join(BASE_DIR, ".intel_store")
CACHE_DIR = os.path.join(BASE_DIR, ".intel_cache")
os.makedirs(STORE_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

MEDIA_STORE = os.path.join(STORE_DIR, "media.json")
ASSOC_STORE = os.path.join(STORE_DIR, "assoc.json")
DISCOVERY_STORE = os.path.join(STORE_DIR, "discovery.json")
UPDATE_STATE = os.path.join(STORE_DIR, "update_state.json")

def store_read(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def store_write(path: str, articles: List[Dict]):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
    except:
        pass

def get_update_state() -> Dict:
    if not os.path.exists(UPDATE_STATE):
        return {}
    try:
        with open(UPDATE_STATE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def set_update_state(key: str, value):
    state = get_update_state()
    state[key] = value
    try:
        with open(UPDATE_STATE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except:
        pass

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = BeautifulSoup(text, "html.parser").get_text(separator=" ").strip()
    return " ".join(text.split())

# ============================================================
# 抓取引擎
# ============================================================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

import re as _date_re
_YEAR_RE = _date_re.compile(r"\b(19|20)\d{2}\b")

def guess_date_from_text(text: str) -> Optional[str]:
    """当 RSS/网页条目没有可靠发布时间时，尝试从标题/摘要里找出年份
    （如“2015年会员更新”），避免把陈旧的历史存档内容误判为最新动态。
    找到年份则返回该年 1月1日 作为保守估算时间；找不到返回 None。"""
    if not text:
        return None
    m = _YEAR_RE.search(text)
    if not m:
        return None
    year = int(m.group())
    if year < 1990 or year > datetime.now().year:
        return None
    try:
        return datetime(year, 1, 1, tzinfo=timezone.utc).isoformat()
    except Exception:
        return None

def load_rss(name: str, url: str) -> List[Dict]:
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": HEADERS["User-Agent"]})
        for idx, entry in enumerate(feed.entries):
            dt = None
            for f in ['published_parsed', 'updated_parsed']:
                if hasattr(entry, f) and getattr(entry, f):
                    try:
                        dt = datetime(*getattr(entry, f)[:6], tzinfo=timezone.utc).isoformat()
                    except:
                        pass
                    break
            title = getattr(entry, 'title', '').strip()
            link = getattr(entry, 'link', '').strip()
            raw_summary = clean_text(getattr(entry, 'summary', ''))
            if not dt:
                # feed 没给真实日期：先尝试从文本里猜年份，猜不到再用抓取时间兜底
                # （并用微小递减偏移避免同批次时间完全相同导致排序扎堆）
                dt = guess_date_from_text(f"{title} {raw_summary}") or \
                     (datetime.now(timezone.utc) - timedelta(seconds=idx)).isoformat()
            # 过滤超过2年的旧内容
            age = datetime.now(timezone.utc) - datetime.fromisoformat(dt)
            if age.days > 730:
                continue
            if not title or not link:
                continue
            if is_marketing_content(title, link):
                continue
            articles.append({
                "title": title,
                "link": link,
                "source": name,
                "dt": dt,
                "raw_summary": raw_summary,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as e:
        print(f"RSS error {name}: {e}")
    return articles

# 行业媒体只需要新闻/资讯/发布类内容，过滤掉营销/传播/广告类页面
MARKETING_EXCLUDE_PATTERNS = [
    "marketing", "campaign", "sponsored", "advertorial", "advertising", "brand-voice",
    "/ads/", "promo", "rebranding-campaign", "influencer",
    "广告", "营销", "宣传", "代言", "联名营销", "推广合作", "软文",
]

def is_marketing_content(title: str, href: str) -> bool:
    blob = f"{title} {href}".lower()
    return any(p in blob for p in MARKETING_EXCLUDE_PATTERNS)

_DATE_YMD_RE = _date_re.compile(r"(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})")        # 2026-06-26 / 2026/07/01
_DATE_DMY_RE = _date_re.compile(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](20\d{2})\b")   # 26.06.2026 / 26-06-2026
_DATE_CJK_RE = _date_re.compile(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")  # 2026年7月1日

def _mk_date(year, month, day) -> Optional[str]:
    try:
        if 2000 <= year <= datetime.now(timezone.utc).year + 1 and 1 <= month <= 12 and 1 <= day <= 31:
            return datetime(year, month, day, tzinfo=timezone.utc).isoformat()
    except Exception:
        pass
    return None

def parse_date_string(raw: str) -> Optional[str]:
    """从一段文本中解析日期，返回 UTC ISO 字符串。
    支持 ISO、YYYY-MM-DD / YYYY/MM/DD、德式/欧式 DD.MM.YYYY、日式 2026年7月1日。"""
    if not raw:
        return None
    raw = raw.strip()
    # 先试 ISO（多用于 <time datetime="..."> 属性）
    try:
        d = datetime.fromisoformat(raw.replace("Z", "+00:00")[:25])
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc).isoformat()
    except Exception:
        pass
    m = _DATE_YMD_RE.search(raw)
    if m:
        r = _mk_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if r:
            return r
    m = _DATE_CJK_RE.search(raw)
    if m:
        r = _mk_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if r:
            return r
    m = _DATE_DMY_RE.search(raw)
    if m:
        r = _mk_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if r:
            return r
    return None

_ITEM_TAGS = ("li", "article")
_ITEM_CLASS_HINTS = ("item", "post", "article", "news", "entry", "noticia", "card", "story")

def _is_item_container(node) -> bool:
    name = getattr(node, "name", "") or ""
    classes = " ".join(node.get("class", [])).lower() if hasattr(node, "get") else ""
    return name in _ITEM_TAGS or any(h in classes for h in _ITEM_CLASS_HINTS)

def _nearest_item_scope(item):
    """找到"单条文章"的容器（li/article 或带 item/post/news 类名的块），
    避免把包含全部文章的列表容器（ul）当作日期范围——否则会把最新一条的日期套给所有条目。
    先看 item 自身（字典格式传入的就是容器），再逐级向上找。"""
    if _is_item_container(item):
        return item
    node = item
    for _ in range(6):
        node = getattr(node, "parent", None)
        if node is None:
            break
        if _is_item_container(node):
            return node
    # 找不到语义容器时，退回 item 的直接父级（仍比爬到列表级安全）
    return getattr(item, "parent", None) or item

def extract_item_date(item, date_sel: Optional[str] = None) -> Optional[str]:
    """在"单条文章容器"范围内提取真实发布时间，返回 UTC ISO。
    顺序：指定选择器 → <time> → 常见日期类 → 容器纯文本正则兜底。"""
    scope = _nearest_item_scope(item)
    if scope is None:
        return None

    candidates = []
    if date_sel:
        candidates.append(scope.select_one(date_sel))
    candidates.append(scope.select_one("time[datetime]"))
    candidates.append(scope.select_one("time"))
    candidates.append(scope.select_one(".date, .post-date, .entry-date, .meta-date, .fecha, .datetime"))
    for el in candidates:
        if not el:
            continue
        raw = el.get("datetime") or el.get_text(" ", strip=True)
        parsed = parse_date_string(raw)
        if parsed:
            return parsed

    # 纯文本兜底：仅在本条目容器文本中找日期（日式/YMD/欧式）
    return parse_date_string(scope.get_text(" ", strip=True))

def scrape_site(name: str, config_data) -> List[Dict]:
    """
    支持两种格式：
    - 列表格式 ["url", "css_selector"]  => 简单链接抓取
    - 字典格式 {"url":..., "item":..., "title":..., "news_section":...}  => 精准新闻抓取
    """
    articles = []
    try:
        if isinstance(config_data, list):
            url = config_data[0]
            selector = config_data[1]
            news_url = config_data[2] if len(config_data) > 2 else None
            target_url = news_url or url
            res = requests.get(target_url, timeout=15, headers=HEADERS)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")
            seen = set()
            for idx, element in enumerate(soup.select(selector)):
                a = element if element.name == 'a' else element.find('a')
                if not a:
                    continue
                title = a.get_text(strip=True)
                href = a.get("href", "")
                if not href or not title or len(title) < 8:
                    continue
                # 过滤导航/footer/social链接
                skip_patterns = ['privacy', 'contact', 'about', 'login', 'register',
                                  'home', 'terms', 'cookie', 'sitemap', '#', 'javascript',
                                  'facebook', 'twitter', 'linkedin', 'instagram']
                if any(p in href.lower() or p in title.lower() for p in skip_patterns):
                    continue
                # 跳过“阅读更多/Read more”等非标题链接（常与正文标题指向同一篇）
                read_more = ['weiterlesen', 'mehr lesen', 'read more', 'lire la suite',
                             'leer más', 'continue reading', '阅读更多', '查看详情', '更多']
                if any(title.lower().startswith(p) or title.lower() == p for p in read_more):
                    continue
                if is_marketing_content(title, href):
                    continue
                link = urljoin(target_url, href)
                key = title[:60]
                if key not in seen:
                    item_dt = (extract_item_date(element) or guess_date_from_text(title) or
                               (datetime.now(timezone.utc) - timedelta(seconds=idx)).isoformat())
                    articles.append({
                        "title": title, "link": link, "source": name,
                        "dt": item_dt,
                        "raw_summary": "",
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    })
                    seen.add(key)
                if len(articles) >= 30:
                    break
        elif isinstance(config_data, dict):
            url = config_data.get("url")
            news_url = config_data.get("news_url", url)
            item_sel = config_data.get("item")
            title_sel = config_data.get("title")
            sum_sel = config_data.get("summary")
            res = requests.get(news_url, timeout=15, headers=HEADERS)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")
            seen = set()
            for idx, item in enumerate(soup.select(item_sel)):
                t_el = item.select_one(title_sel)
                if not t_el:
                    continue
                a_el = t_el if t_el.name == 'a' else t_el.find('a')
                title = t_el.get_text(strip=True)
                href = (a_el.get("href", "") if a_el else "")
                if not title or len(title) < 8:
                    continue
                if is_marketing_content(title, href):
                    continue
                link = urljoin(news_url, href) if href else news_url
                summary = ""
                if sum_sel:
                    s_el = item.select_one(sum_sel)
                    summary = s_el.get_text(strip=True) if s_el else ""
                key = title[:60]
                if key not in seen:
                    item_dt = (extract_item_date(item, config_data.get("date")) or
                               guess_date_from_text(title) or
                               (datetime.now(timezone.utc) - timedelta(seconds=idx)).isoformat())
                    articles.append({
                        "title": title, "link": link, "source": name,
                        "dt": item_dt,
                        "raw_summary": clean_text(summary),
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    })
                    seen.add(key)
                if len(articles) >= 30:
                    break
    except Exception as e:
        print(f"Scrape error {name}: {e}")
    return articles

def search_discovery(keywords: List[str]) -> List[Dict]:
    """全网情报发现。原用 DuckDuckGo / 必应网页抓取均已被反爬或改版挡住，
    改用 Google News RSS：返回规范的标题+链接+真实发布日期，稳定不被反爬。
    注：Google News 在境外服务器（如 Streamlit Cloud）可正常访问；
    若日后自建服务器部署在中国大陆，此源不可达，需改用可访问的搜索后端或代理。"""
    import random
    from urllib.parse import quote
    articles = []
    selected_kws = random.sample(keywords, min(len(keywords), 6))
    # 行业限定词：覆盖卫浴/厨房/家电/暖通/建材五大板块，过滤掉手机/电视等无关新闻
    industry_ctx = ("(bathroom OR kitchen OR sanitary OR faucet OR HVAC OR \"heat pump\" "
                    "OR appliance OR heating OR cooling OR ceramic OR tile OR plumbing "
                    "OR flooring OR cabinet OR \"building material\")")
    for kw in selected_kws:
        try:
            query = quote(f'"{kw}" {industry_ctx} when:180d')
            url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(url, request_headers={"User-Agent": HEADERS["User-Agent"]})
            for e in feed.entries[:8]:
                title = getattr(e, "title", "").strip()
                link = getattr(e, "link", "").strip()
                if not title or not link or len(title) < 10:
                    continue
                dt = None
                for f in ("published_parsed", "updated_parsed"):
                    if getattr(e, f, None):
                        try:
                            dt = datetime(*getattr(e, f)[:6], tzinfo=timezone.utc).isoformat()
                        except Exception:
                            pass
                        break
                articles.append({
                    "title": f"✨ {title}",
                    "link": link,
                    "source": f"情报发现: {kw}",
                    "dt": dt or datetime.now(timezone.utc).isoformat(),
                    "raw_summary": clean_text(getattr(e, "summary", "")),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                })
        except Exception as ex:
            print(f"Discovery error {kw}: {ex}")
    return articles

# ============================================================
# 后台更新
# ============================================================
def merge_articles(existing: List[Dict], fresh: List[Dict]) -> List[Dict]:
    seen = {f"{a['title'][:50]}_{a['link']}" for a in existing}
    new_only = [a for a in fresh if f"{a['title'][:50]}_{a['link']}" not in seen]
    return new_only + existing

def _bg_update(store_path, rss_dict, scrape_dict, state_key, keywords=None):
    try:
        fresh = []
        if rss_dict:
            for name, url in rss_dict.items():
                fresh.extend(load_rss(name, url))
        if scrape_dict:
            for name, config in scrape_dict.items():
                fresh.extend(scrape_site(name, config))
        if keywords and state_key == "discovery":
            fresh.extend(search_discovery(keywords))
        existing = store_read(store_path)
        merged = merge_articles(existing, fresh)
        # 只保留最近2年内的文章，并最多保留800条
        cutoff = (datetime.now(timezone.utc) - timedelta(days=730)).isoformat()
        merged = [a for a in merged if a.get('dt', '') >= cutoff or a.get('dt', '') == '']
        merged = merged[:800]
        store_write(store_path, merged)
        set_update_state(state_key, datetime.now(timezone.utc).isoformat())
        # 抓取完成后顺带预热翻译缓存：用户打开页面时直接命中，无需等待联网翻译
        try:
            warm_texts = []
            for a in merged[:300]:
                warm_texts.append(a.get("title", ""))
                warm_texts.append(a.get("raw_summary", ""))
            warm_translations(warm_texts)
        except Exception as te:
            print(f"warm translate error: {te}")
    except Exception as e:
        print(f"BG update error: {e}")

def trigger_bg_update(store_path, rss_dict, scrape_dict, state_key, interval_minutes=30, keywords=None):
    state = get_update_state()
    last = state.get(state_key)
    if last and interval_minutes > 0:
        diff = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
        if diff < interval_minutes * 60:
            return
    threading.Thread(target=_bg_update, args=(store_path, rss_dict, scrape_dict, state_key, keywords), daemon=True).start()

# ============================================================
# AI 分析功能
# ============================================================
# OpenRouter 免费模型（按优先级；免费模型常过载，用多个自动回退）
OPENROUTER_FREE_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "google/gemma-4-31b-it:free",
]

def call_openrouter(prompt: str, api_key: str, max_tokens: int = 2000) -> str:
    """调用 OpenRouter。利用其原生 models 回退：某个免费模型过载/报错时自动换下一个。"""
    api_key = (api_key or "").strip()
    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://kitchbathintel.streamlit.app",
                "X-Title": "KitchBath Intel Dashboard",
            },
            json={
                "models": OPENROUTER_FREE_MODELS,   # 依次回退
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.2,   # 降低随机度，减少编造
            },
            timeout=120,
        )
        try:
            data = res.json()
        except Exception:
            return f"OpenRouter 返回非 JSON（HTTP {res.status_code}）：{res.text[:300]}"
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"]
        err = data.get("error", {})
        msg = err.get("message", str(data)) if isinstance(err, dict) else str(err)
        hint = ""
        if "rate" in msg.lower() or res.status_code == 429:
            hint = "（免费额度/频率受限，稍后再试或换 DeepSeek）"
        elif res.status_code in (401, 403):
            hint = "（API Key 无效）"
        return f"OpenRouter 返回错误 HTTP {res.status_code}{hint}：{msg}"
    except Exception as e:
        return f"OpenRouter 调用出错：{str(e)}"

def call_cloudflare_ai(prompt: str, api_key: str, max_tokens: int = 2000) -> str:
    """调用 Cloudflare Workers AI 免费模型。
    api_key 格式要求为 "account_id:api_token"（在 Cloudflare Dashboard -> Workers AI 获取）。"""
    api_key = (api_key or "").strip()
    if ":" not in api_key:
        return "Cloudflare Key 格式错误，请填写 \"账户ID:API令牌\"（用英文冒号分隔），可在 Cloudflare Dashboard 的 Workers AI 页面获取。"
    account_id, token = api_key.split(":", 1)
    account_id, token = account_id.strip(), token.strip()
    model = "@cf/meta/llama-3.1-8b-instruct"
    try:
        res = requests.post(
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 0.2},
            timeout=90
        )
        try:
            data = res.json()
        except Exception:
            return f"Cloudflare AI 返回非 JSON（HTTP {res.status_code}）：{res.text[:300]}"
        if data.get("success"):
            return data["result"]["response"]
        # 明确报错信息，便于排查（如账户ID错、令牌无 Workers AI 权限等）
        errs = data.get("errors") or data.get("messages") or data
        hint = ""
        if res.status_code in (401, 403):
            hint = "（令牌无效或缺少 Workers AI 权限：请用 Account API Token 且授予 'Workers AI - Read/Run'）"
        elif res.status_code == 404:
            hint = "（账户ID或模型路径错误：确认冒号前是 Account ID）"
        elif res.status_code == 400:
            hint = "（请求参数问题）"
        return f"Cloudflare AI 报错 HTTP {res.status_code}{hint}：{errs}"
    except Exception as e:
        return f"Cloudflare AI 调用出错：{str(e)}"

def _build_reference_list(result_text: str, sample: List[Dict]) -> str:
    """扫描报告里出现的 [#N] 编号，在末尾生成对应的「参考来源」清单（可点击原文），
    让读者能核对每条结论的依据。只列出确实被引用到的编号。"""
    import re as _re
    nums = set()
    for m in _re.findall(r'#\s*(\d+)', result_text or ""):
        try:
            n = int(m)
            if 1 <= n <= len(sample):
                nums.add(n)
        except Exception:
            pass
    if not nums:
        return ""
    lines = ["\n\n---\n#### 📎 参考来源（点击查看原文）"]
    for n in sorted(nums):
        a = sample[n - 1]
        title = (a.get("title") or "").replace("\n", " ").strip()
        src = a.get("source", "")
        link = a.get("link", "")
        dt = (a.get("dt", "") or "")[:10]
        if link:
            lines.append(f"- **[#{n}]** [{title}]({link}) · {src} · {dt}")
        else:
            lines.append(f"- **[#{n}]** {title} · {src} · {dt}")
    return "\n".join(lines)

def analyze_with_ai(articles: List[Dict], api_key: str, provider: str = "openai", months: int = 6) -> str:
    """用外部大模型对指定月数内文章进行行业分析"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30 * months)
    recent = [a for a in articles if a.get('dt', '') >= cutoff.isoformat()]
    if not recent:
        return f"暂无近 {months} 个月的数据可分析，请先刷新数据或扩大时间范围。"

    total_recent = len(recent)
    # 最新优先
    recent.sort(key=lambda a: a.get('dt', '') or '', reverse=True)
    # 按来源均衡取样：避免单一高产源（如 Moebelkultur 近300条）淹没样本、带偏话题
    per_source_cap = 18
    cnt = {}
    sample = []
    for a in recent:
        s = a.get('source', '')
        if cnt.get(s, 0) >= per_source_cap:
            continue
        cnt[s] = cnt.get(s, 0) + 1
        sample.append(a)
        if len(sample) >= 180:
            break

    # 收集来源名称，供模型排除（这些是媒体平台，不是企业）
    all_sources = sorted(set(a.get('source', '') for a in sample if a.get('source')))
    sources_note = "、".join(all_sources[:40])

    # 提取标题摘要（带编号，格式：序号. [来源] 标题（摘要））
    titles_text = "\n".join([
        f"{i+1}. [{a['source']}] {a['title']}" + (f"（{a['raw_summary'][:120]}）" if a.get('raw_summary') else "")
        for i, a in enumerate(sample)
    ])

    period_label = f"{cutoff.strftime('%Y年%m月')} 至今（约 {months} 个月）"

    prompt = f"""你是一位严谨的全球卫浴、厨房和建材行业分析师。近 {months} 个月共抓取 {total_recent} 条资讯，
以下是按来源均衡抽取的 {len(sample)} 条样本，每条格式为「序号. [来源平台] 标题（摘要）」：

{titles_text}

=== 铁律（必须遵守，违反视为失败）===
1. **只能依据上面这些资讯**。严禁编造任何未出现的企业名、人名、职位、数字、金额、并购或产品事件——宁可少写，绝不杜撰。
2. **每条结论后必须标注真实依据编号** [#序号]，且该编号对应的资讯内容必须真的支持这句话（不要随便凑一个邻近编号）。
3. **严禁模板化套话与复读**：不得在不同小节/不同地区重复同一句话；不得写"正在经历快速增长，尤其在智能家居和可持续性方面"这类空话；不要凭空塞"智能家居/可持续/数字化"，除非至少有 2 条资讯确实在讲它并列出编号。
4. 方括号内是【来源平台】（KBB Review、Moebelmarkt、Dezeen 等），不是企业。真正企业是 Kohler、Hansgrohe、TOTO、Grohe、Duravit、Roca、LIXIL、FGI Industries 等。
5. 本系统聚焦**卫浴、厨房、建材/卫生陶瓷**；家具/地板等只在与之相关时才纳入。

=== 输出结构（以"真实事件"为主，不要空泛评论）===

## 一、重点事件速览（最重要）
把资讯中**确实发生**的具体事件按类别列出，每条一句话写清"主体 + 事件 + [#编号]"；某类无则写"暂无"：
- 👔 人事变动　- 🤝 并购与合作　- 🚀 新品与技术　- 📈 财务与市场　- 🏭 运营变动（工厂/产能）

## 二、可归纳的趋势
**只写能被 ≥2 条资讯支撑的真实共性**，每条附上多个编号（如 [#3,#28,#57]）。若样本里看不出清晰共性，直接写"样本中未见明显共性趋势"。不要为凑数硬编趋势。

## 三、地区分布
根据来源国别/内容，客观说明本期资讯主要集中在哪些地区（可给大致条数）。一句话即可，不要每个地区复读同一句。

## 四、值得关注（简短）
基于上面有编号的事件，指出最值得关注的 2-3 件事（每件附编号）+ 一句谨慎判断。没把握就写"数据不足以判断"。

要求：专业、克制、可核对；宁可短，不可编。"""

    try:
        if provider == "openai" or provider == "deepseek":
            base_url = "https://api.openai.com/v1" if provider == "openai" else "https://api.deepseek.com/v1"
            model = "gpt-4o-mini" if provider == "openai" else "deepseek-chat"
            res = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 2000, "temperature": 0.2},
                timeout=60
            )
            data = res.json()
            result_text = data["choices"][0]["message"]["content"]
        elif provider == "anthropic":
            res = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                json={"model": "claude-haiku-4-5-20251001", "max_tokens": 2000, "temperature": 0.2, "messages": [{"role": "user", "content": prompt}]},
                timeout=60
            )
            data = res.json()
            result_text = data["content"][0]["text"]
        elif provider == "qwen" or provider == "tongyi":
            res = requests.post(
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": "qwen-turbo", "input": {"messages": [{"role": "user", "content": prompt}]}, "parameters": {"temperature": 0.2}},
                timeout=60
            )
            data = res.json()
            result_text = data["output"]["text"]
        elif provider == "openrouter":
            result_text = call_openrouter(prompt, api_key, max_tokens=2000)
        elif provider == "cloudflare":
            result_text = call_cloudflare_ai(prompt, api_key, max_tokens=2000)
        else:
            return "不支持的 AI 提供商，请选择 OpenRouter / Cloudflare / OpenAI / DeepSeek / Anthropic / 通义千问。"
        # 在报告末尾附上被引用编号对应的真实来源清单（可点击原文）
        return result_text + _build_reference_list(result_text, sample)
    except Exception as e:
        return f"AI 分析出错：{str(e)}\n\n请检查 API Key 是否正确，以及网络连接是否正常。"


# ============================================================
# 舆情监督功能 v2 — 精准复合匹配 + 可选 AI 二次筛选
# ============================================================

# ---- 主题定义：采用「必须命中 + 加分词」双层逻辑 ----
SENTIMENT_THEMES = {
    "高管人事变动": {
        # strong：含义明确、单独命中即可判定为人事变动
        "strong_any_zh": ["离职", "辞职", "卸任", "退休", "任命为", "升任为", "接替"],
        "strong_any_en": ["resign", "steps down", "step down", "appointed as", "named as",
                          "new CEO", "new president", "successor to", "replaces", "takes over as",
                          "promoted to", "fired", "ousted", "to retire",
                          # 德/法/西/意 高频人事词（本项目来源多为这些语种）
                          "neu besetzt", "ernennung", "nachfolge", "ernennt", "geht in den ruhestand",
                          "nomination", "nommé", "nommée", "nombrado", "nuovo amministratore"],
        # weak：较泛化，需要有角色/职位词(boost)佐证才算
        "must_any_zh": ["接任", "就任", "出任", "新任", "上任", "履新", "加入", "任命"],
        "must_any_en": ["departure", "joins as", "hired", "appoint", "appointed", "named",
                        "manager", "management", "leadership", "managment",
                        "wechsel", "verstärkt", "übernimmt die leitung", "rejoint"],
        "boost_zh": ["CEO", "总裁", "董事长", "总经理", "首席", "主席", "负责人", "高管", "管理人员", "总监"],
        "boost_en": ["CEO", "CFO", "CTO", "president", "chairman", "chief", "executive", "VP",
                    "director", "head of", "managing director", "country manager",
                    "geschäftsführer", "vorstand", "leiter", "leitung", "directeur", "ressort"],
        "exclude_if_en": ["award", "conference", "exhibition", "show", "fair", "product",
                          "collection", "store opening"],
        "color": "#ef4444",
        "icon": "\U0001f454"
    },
    "并购与战略合作": {
        "strong_any_zh": ["收购", "并购", "合并", "入股", "控股", "股权转让", "联合成立", "战略合作"],
        "strong_any_en": ["acquires", "acquired", "acquisition", "merger", "merges", "takeover",
                         "joint venture", "strategic partnership", "equity stake", "buys stake",
                         "übernimmt", "übernahme"],
        "must_any_zh": ["合作", "投资", "携手", "联手"],
        "must_any_en": ["buys", "purchased", "stakes in", "invest in", "investment in", "partners with"],
        "boost_zh": ["亿", "万", "股权", "交易"],
        "boost_en": ["deal", "billion", "million", "agreement", "stake"],
        "exclude_if_en": ["award", "conference", "exhibition"],
        "color": "#f59e0b",
        "icon": "\U0001f91d"
    },
    "新品与技术发布": {
        "strong_any_zh": ["发布新", "推出新", "新品上市", "首发", "专利获批", "技术突破", "新系列"],
        "strong_any_en": ["launches", "unveiled", "unveils", "introduces", "new product", "new collection",
                         "debut", "patent granted", "breakthrough", "new range", "new line"],
        "must_any_zh": ["发布", "推出", "上市", "新品", "全新"],
        "must_any_en": ["released", "announcing", "presents", "showcases"],
        "boost_zh": ["创新", "智能", "节水", "系列", "产品"],
        "boost_en": ["design", "smart", "IoT", "sustainable", "product", "collection", "series"],
        "exclude_if_en": [],
        "color": "#10b981",
        "icon": "\U0001f680"
    },
    "财务与市场变化": {
        "strong_any_zh": ["裁员", "亏损", "破产", "重组", "营收下滑", "盈利增长", "季报", "年报"],
        "strong_any_en": ["layoffs", "job cuts", "bankruptcy", "insolvency", "restructuring",
                         "revenue decline", "profit warning", "quarterly results", "annual report",
                         "record revenue", "earnings", "sales drop"],
        "must_any_zh": ["市场份额", "营收", "销售额", "业绩"],
        "must_any_en": ["market share", "turnover", "sales rose", "sales fell", "revenue"],
        "boost_zh": ["亿", "万", "增长", "下滑", "百分"],
        "boost_en": ["billion", "million", "percent", "growth", "decline", "%"],
        "exclude_if_en": ["award", "exhibition", "conference"],
        "color": "#6366f1",
        "icon": "\U0001f4c8"
    }
}


def match_sentiment_theme(article: Dict, theme_config: Dict, companies: Optional[List[str]] = None) -> tuple:
    """分层匹配：
    - 命中「强词(strong)」→ 含义明确，直接判定（高置信）。
    - 仅命中「弱词(weak/泛化词)」→ 必须同时有角色/金额/企业名等 boost 词佐证才算（普通置信）。
    既避免单独泛化词造成误判，又不漏掉没有明显职位词以外的真实动态。
    支持两种配置写法：分语言键(strong_any_zh/en…) 或统一列表键(strong/weak/boost/exclude)。
    若条目命中重点企业(companies)，额外加分并提升置信。
    返回 (matched: bool, confidence: int)"""
    title = article.get("title", "") or ""
    summary = article.get("raw_summary", "") or ""
    text = (title + " " + summary).lower()

    strong = (theme_config.get("strong", [])
              + theme_config.get("strong_any_zh", []) + theme_config.get("strong_any_en", []))
    weak = (theme_config.get("weak", [])
            + theme_config.get("must_any_zh", []) + theme_config.get("must_any_en", []))
    boost = (theme_config.get("boost", [])
             + theme_config.get("boost_zh", []) + theme_config.get("boost_en", []))
    excludes = theme_config.get("exclude", []) + theme_config.get("exclude_if_en", [])

    hit_strong = any(kw.lower() in text for kw in strong)
    hit_weak = any(kw.lower() in text for kw in weak)
    boost_score = sum(1 for kw in boost if kw.lower() in text)
    hit_exclude = any(kw.lower() in text for kw in excludes) if excludes else False

    # 重点企业命中：算作一个强 boost
    hit_company = False
    if companies:
        hit_company = any(c.lower() in text for c in companies if c)
        if hit_company:
            boost_score += 1

    if hit_strong:
        # 强词命中：除非命中排除词且毫无 boost 支撑，否则判定为匹配
        if hit_exclude and boost_score == 0:
            return False, 0
        return True, 2
    if hit_weak and boost_score >= 1:
        if hit_exclude:
            return False, 0
        # 命中重点企业的弱匹配也提升为高置信
        return True, 2 if hit_company else 1
    return False, 0


def get_sentiment_articles(all_articles: List[Dict], theme_name: str, days: int,
                           themes: Optional[Dict] = None, companies: Optional[List[str]] = None) -> List[Dict]:
    """获取指定主题、指定天数内的匹配文章，按置信度+时间排序"""
    themes = themes or SENTIMENT_THEMES
    theme_config = themes.get(theme_name, {})
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    matched = []
    for a in all_articles:
        if (a.get("dt", "") or "") < cutoff:
            continue
        hit, conf = match_sentiment_theme(a, theme_config, companies)
        if hit:
            matched.append({**a, "_confidence": conf})
    matched.sort(key=lambda x: (x.get("_confidence", 0), x.get("dt", "")), reverse=True)
    return matched


def ai_classify_sentiment(articles: List[Dict], theme_name: str, api_key: str, provider: str) -> List[Dict]:
    """用大模型对候选文章做二次精准分类"""
    if not articles or not api_key:
        return articles
    batch = articles[:30]
    items_text = "\n".join([
        f"{i+1}. [{a.get('source','')}] {a.get('title','')}（{a.get('raw_summary','')[:80]}）"
        for i, a in enumerate(batch)
    ])
    prompt = f"""你是行业分析助手。以下是 {len(batch)} 条卫浴/厨房/建材行业资讯：

{items_text}

主题：**{theme_name}**

判断每条是否真正属于该主题（仅会议/展会/奖项/设计趋势不算）。
来源名称（方括号内）是媒体平台，不是企业，忽略之。

只返回 JSON 数组：
[{{"id": 1, "relevant": true, "reason": "原因"}}, ...]"""

    try:
        result_text = ""
        if provider in ("openai", "deepseek"):
            base_url = "https://api.openai.com/v1" if provider == "openai" else "https://api.deepseek.com/v1"
            model = "gpt-4o-mini" if provider == "openai" else "deepseek-chat"
            res = requests.post(f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1500},
                timeout=60)
            result_text = res.json()["choices"][0]["message"]["content"]
        elif provider == "openrouter":
            result_text = call_openrouter(prompt, api_key, max_tokens=1500)
        elif provider == "anthropic":
            res = requests.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                json={"model": "claude-haiku-4-5-20251001", "max_tokens": 1500,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=60)
            result_text = res.json()["content"][0]["text"]
        elif provider in ("qwen", "tongyi"):
            res = requests.post(
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": "qwen-turbo", "input": {"messages": [{"role": "user", "content": prompt}]}},
                timeout=60)
            result_text = res.json()["output"]["text"]
        elif provider == "cloudflare":
            result_text = call_cloudflare_ai(prompt, api_key, max_tokens=1500)

        import re as _re
        json_match = _re.search(r'\[.*?\]', result_text, _re.DOTALL)
        if json_match:
            classifications = json.loads(json_match.group())
            class_map = {item["id"]: item for item in classifications}
            for i, a in enumerate(batch):
                cls = class_map.get(i + 1, {})
                a["_ai_relevant"] = cls.get("relevant", True)
                a["_ai_reason"] = cls.get("reason", "")
        return articles
    except Exception as e:
        print(f"AI 分类出错: {e}")
        return articles


def render_sentiment_tab(all_articles: List[Dict], enable_translate: bool,
                         themes: Optional[Dict] = None, companies: Optional[List[str]] = None):
    """渲染舆情监督 Tab"""
    themes = themes or SENTIMENT_THEMES
    companies = companies or []
    st.markdown("### 📡 舆情监督中心")
    st.caption("精准追踪行业关键动态：人事变动、并购、财务、运营变动、战略举措（重点企业自动加分）")

    if not all_articles:
        st.info("⏳ 暂无数据，请先在媒体/协会页点击「强制刷新」")
        return

    # ---- 顶部控制区：自定义关键词 + AI 设置（放在主区域而非 expander，避免 state 丢失）----
    sent_col1, sent_col2 = st.columns([3, 2])
    with sent_col1:
        st.markdown("**🔍 自定义关键词追踪**")
        custom_kw_input = st.text_input(
            "关键词",
            placeholder="例如: Kohler CEO resign, Hansgrohe merger",
            key="custom_sentiment_kw",
            label_visibility="collapsed"
        )
        custom_days = st.select_slider(
            "追踪时间范围",
            options=[7, 30, 90, 180],
            value=30,
            format_func=lambda x: f"近 {x} 天",
            key="custom_sent_days"
        )
    with sent_col2:
        st.markdown("**🤖 AI 精准筛选（可选）**")
        use_ai_filter = st.checkbox("启用 AI 过滤去除误匹配", key="sentiment_use_ai")
        sent_ai_provider = st.selectbox(
            "AI提供商",
            ["openrouter", "cloudflare", "openai", "deepseek", "anthropic", "qwen"],
            format_func=lambda x: {
                "openrouter": "🆓 OpenRouter 免费",
                "cloudflare": "🆓 Cloudflare 免费",
                "openai": "OpenAI", "deepseek": "DeepSeek",
                "anthropic": "Anthropic", "qwen": "通义千问"
            }[x],
            key="sentiment_ai_provider",
            label_visibility="collapsed"
        )
        sent_api_key = st.text_input(
            "API Key",
            type="password",
            key="sentiment_api_key",
            placeholder="sk-... （Cloudflare 请填 账户ID:API令牌）",
            label_visibility="collapsed"
        )

    # 自定义关键词结果（直接显示，按钮触发）
    if custom_kw_input.strip():
        if st.button("🔎 搜索", key="custom_kw_search"):
            custom_kws = [k.strip() for k in custom_kw_input.split(",") if k.strip()]
            cutoff_c = (datetime.now(timezone.utc) - timedelta(days=custom_days)).isoformat()
            custom_matched = []
            for a in all_articles:
                if (a.get("dt", "") or "") < cutoff_c:
                    continue
                text = (a.get("title", "") + " " + a.get("raw_summary", "")).lower()
                if any(kw.lower() in text for kw in custom_kws):
                    custom_matched.append(a)
            custom_matched.sort(key=lambda x: x.get("dt", ""), reverse=True)

            if use_ai_filter and sent_api_key and custom_matched:
                with st.spinner(f"AI 正在精准筛选 {min(len(custom_matched),30)} 条..."):
                    theme_label = "自定义：" + "、".join(custom_kws[:3])
                    custom_matched = ai_classify_sentiment(custom_matched, theme_label, sent_api_key, sent_ai_provider)
                    custom_matched = [a for a in custom_matched if a.get("_ai_relevant", True)]

            st.session_state["custom_kw_results"] = custom_matched
            st.session_state["custom_kw_label"] = f"近 {custom_days} 天 / 关键词: {', '.join(custom_kws[:3])}"

    if "custom_kw_results" in st.session_state:
        results = st.session_state["custom_kw_results"]
        label = st.session_state.get("custom_kw_label", "")
        st.markdown(f"**🔍 自定义追踪：{label} — 匹配 {len(results)} 条**")
        if results:
            if enable_translate:
                warm_translations([a.get("title", "") for a in results[:25]]
                                  + [a.get("raw_summary", "") for a in results[:25]])
            for a in results[:25]:
                _render_sentiment_card(a, enable_translate, "#7c3aed", show_ai_reason=True)
        else:
            st.info("未找到匹配内容，请调整关键词或扩大时间范围")

    st.divider()

    # ---- 预设主题监督面板 ----
    period_options = {"近7天": 7, "近1个月": 30, "近3个月": 90, "近6个月": 180}
    selected_period = st.radio(
        "统计时间段", list(period_options.keys()), horizontal=True, key="sentiment_period"
    )
    selected_days = period_options[selected_period]

    # 汇总数字卡片
    stat_cols = st.columns(len(themes))
    theme_counts = {}
    for i, (theme_name, theme_cfg) in enumerate(themes.items()):
        matched = get_sentiment_articles(all_articles, theme_name, selected_days, themes, companies)
        theme_counts[theme_name] = matched
        color = theme_cfg["color"]
        icon = theme_cfg["icon"]
        with stat_cols[i]:
            st.markdown(
                f'<div style="background:white;border-radius:10px;padding:14px;text-align:center;'
                f'border-top:4px solid {color};box-shadow:0 2px 8px rgba(0,0,0,0.08)">'
                f'<div style="font-size:22px">{icon}</div>'
                f'<div style="font-size:26px;font-weight:700;color:{color}">{len(matched)}</div>'
                f'<div style="font-size:11px;color:#6b7280">{theme_name}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    st.markdown("<div style='margin:12px 0'></div>", unsafe_allow_html=True)

    # 并发预热所有将展示主题的翻译（每主题前30条）
    if enable_translate:
        warm_texts = []
        for tn in themes:
            for a in theme_counts.get(tn, [])[:30]:
                warm_texts.append(a.get("title", ""))
                warm_texts.append(a.get("raw_summary", ""))
        warm_translations(warm_texts)

    # 分主题详情
    for idx, (theme_name, theme_cfg) in enumerate(themes.items()):
        matched = theme_counts[theme_name]
        color = theme_cfg["color"]
        icon = theme_cfg["icon"]
        is_first = idx == 0
        with st.expander(f"{icon} {theme_name} — {selected_period}内 {len(matched)} 条", expanded=is_first):
            if not matched:
                st.info(f"近 {selected_days} 天内暂无精准匹配的{theme_name}动态")
                st.caption("💡 可尝试启用 AI 精准筛选，或在自定义关键词中输入更具体的词")
            else:
                # AI 过滤按钮
                if use_ai_filter and sent_api_key:
                    ai_btn_key = f"ai_filter_btn_{theme_name}"
                    if st.button(f"🤖 AI 精准筛选（当前 {len(matched)} 条）", key=ai_btn_key):
                        with st.spinner("AI 分析中..."):
                            filtered = ai_classify_sentiment(list(matched), theme_name, sent_api_key, sent_ai_provider)
                            st.session_state[f"ai_filtered_{theme_name}"] = filtered

                display = st.session_state.get(f"ai_filtered_{theme_name}", matched)
                if use_ai_filter and sent_api_key and f"ai_filtered_{theme_name}" in st.session_state:
                    ai_ok = [a for a in display if a.get("_ai_relevant", True)]
                    ai_no = [a for a in display if not a.get("_ai_relevant", True)]
                    st.caption(f"✅ AI 确认相关：{len(ai_ok)} 条 | ❌ 过滤误匹配：{len(ai_no)} 条")
                    for a in ai_ok[:30]:
                        _render_sentiment_card(a, enable_translate, color, show_ai_reason=True)
                    if ai_no:
                        with st.expander(f"查看被过滤的 {len(ai_no)} 条"):
                            for a in ai_no[:10]:
                                _render_sentiment_card(a, enable_translate, "#d1d5db", show_ai_reason=True)
                else:
                    for a in matched[:30]:
                        _render_sentiment_card(a, enable_translate, color)


def _render_sentiment_card(a: Dict, enable_translate: bool, color: str, show_ai_reason: bool = False):
    """渲染单条舆情卡片"""
    from html import escape
    title = translate_safe(a.get("title", ""), enable_translate)
    summary = translate_safe(a.get("raw_summary", ""), enable_translate)
    dt_str = (a.get("dt", "") or "")[:10]
    source_e = escape(a.get("source", ""))
    link = a.get("link", "#").replace('"', "%22")
    title_e = escape(title)
    summary_e = escape(summary) if summary else ""
    conf = a.get("_confidence", 0)
    ai_reason = a.get("_ai_reason", "")

    conf_badge = (
        '<span style="background:#dcfce7;color:#166534;font-size:10px;padding:2px 6px;'
        'border-radius:4px;margin-left:6px">高置信</span>'
        if conf == 2 else ""
    )
    summary_html = (
        f'<div style="font-size:13px;color:#6b7280;margin:6px 0;line-height:1.6">{summary_e}</div>'
        if summary_e else ""
    )
    ai_html = (
        f'<div style="font-size:11px;color:#7c3aed;margin-top:4px">🤖 {escape(ai_reason)}</div>'
        if show_ai_reason and ai_reason else ""
    )

    st.markdown(
        f'<div style="background:#ffffff;border:0.5px solid #ddd6ca;border-radius:12px;padding:16px 18px;margin-bottom:10px;'
        f'border-left:4px solid {color}">'
        f'<div style="font-family:Georgia,\'Noto Serif SC\',serif;font-size:17px;font-weight:600;'
        f'margin-bottom:6px;line-height:1.4">'
        f'<a href="{link}" target="_blank" style="text-decoration:none;color:#1a1a1a">{title_e}</a>'
        f'{conf_badge}</div>'
        f'{summary_html}{ai_html}'
        f'<div style="display:flex;justify-content:space-between;font-size:12px;color:#8a8172;'
        f'border-top:0.5px solid #ddd6ca;padding-top:8px;margin-top:8px">'
        f'<span>来源 {source_e} · {dt_str}</span><span>阅读原文 ↗</span>'
        f'</div></div>',
        unsafe_allow_html=True
    )

# ============================================================
# UI 渲染 - 带分页的文章列表
# ============================================================
PAGE_SIZE = 20

# ---- 翻译缓存（内存 + 磁盘），避免每次渲染都重复发起网络翻译请求 ----
TRANS_CACHE_FILE = os.path.join(CACHE_DIR, "translations.json")
_TRANS_CACHE = {}
_TRANS_DIRTY = False

def _load_trans_cache():
    global _TRANS_CACHE
    if _TRANS_CACHE:
        return
    if os.path.exists(TRANS_CACHE_FILE):
        try:
            with open(TRANS_CACHE_FILE, "r", encoding="utf-8") as f:
                _TRANS_CACHE = json.load(f)
        except:
            _TRANS_CACHE = {}

def _flush_trans_cache():
    global _TRANS_DIRTY
    if not _TRANS_DIRTY:
        return
    try:
        with open(TRANS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_TRANS_CACHE, f, ensure_ascii=False)
        _TRANS_DIRTY = False
    except:
        pass

def _needs_translation(text):
    if not text or len(text) < 3:
        return False
    chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
    return chinese_chars / max(len(text), 1) <= 0.3

def _do_translate(text):
    try:
        return GoogleTranslator(source='auto', target='zh-CN').translate(text[:500]) or text
    except:
        return text

def warm_translations(texts):
    """并发预热翻译缓存：把一批待翻译文本并行翻好，渲染时直接命中缓存。"""
    global _TRANS_DIRTY
    _load_trans_cache()
    todo, seen = [], set()
    for t in texts:
        if not t or t in seen:
            continue
        seen.add(t)
        key = t[:500]
        if _needs_translation(t) and key not in _TRANS_CACHE:
            todo.append(key)
    if not todo:
        return
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(_do_translate, todo))
    for key, val in zip(todo, results):
        _TRANS_CACHE[key] = val
    _TRANS_DIRTY = True
    _flush_trans_cache()

def translate_safe(text: str, enable: bool) -> str:
    if not enable or not text or len(text) < 3:
        return text
    if not _needs_translation(text):
        return text
    _load_trans_cache()
    key = text[:500]
    if key in _TRANS_CACHE:
        return _TRANS_CACHE[key]
    global _TRANS_DIRTY
    val = _do_translate(text)
    _TRANS_CACHE[key] = val
    _TRANS_DIRTY = True
    return val

def render_list(articles: List[Dict], enable_ai_translate: bool, sort_mode: str, tab_key: str):
    if not articles:
        st.info("⏳ 正在加载情报数据，请稍后刷新页面或点击强制刷新...")
        return

    # 日期过滤
    filter_col1, filter_col2 = st.columns([3, 1])
    with filter_col1:
        date_filter = st.selectbox(
            "时间范围",
            ["全部", "最近7天", "最近30天", "最近3个月", "最近一年"],
            key=f"date_filter_{tab_key}"
        )
    with filter_col2:
        st.markdown(f"**共 {len(articles)} 条**")

    now = datetime.now(timezone.utc)
    filter_map = {
        "最近7天": 7, "最近30天": 30, "最近3个月": 90, "最近一年": 365
    }
    if date_filter in filter_map:
        cutoff = (now - timedelta(days=filter_map[date_filter])).isoformat()
        articles = [a for a in articles if a.get('dt', '') >= cutoff]

    # 排序 - 用 sort_key 保证稳定（scrape文章dt可能都是抓取时间，用fetched_at兜底）
    def get_sort_dt(a):
        dt = a.get('dt', '') or ''
        # 如果dt是今天（scrape写入的now），尝试用fetched_at
        return dt

    if sort_mode == "时间 (最新)":
        articles.sort(key=get_sort_dt, reverse=True)
    elif sort_mode == "重要性 (最高)":
        KEYWORDS = ["发布", "新品", "收购", "合并", "CEO", "总裁", "离职", "增长", "市场", "趋势", "突破", "创新",
                    "resign", "acquire", "merger", "launch", "growth", "appoint", "new CEO", "partnership"]
        def score(a):
            txt = (a.get('title', '') + a.get('raw_summary', '')).lower()
            return sum(1 for kw in KEYWORDS if kw.lower() in txt)
        articles.sort(key=lambda x: (score(x), get_sort_dt(x)), reverse=True)
    else:
        # 综合推荐：重要性 * 0.5 + 时间新鲜度
        articles.sort(key=get_sort_dt, reverse=True)

    # 分页
    total = len(articles)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    page_key = f"page_{tab_key}"
    if page_key not in st.session_state:
        st.session_state[page_key] = 1

    page = st.session_state[page_key]
    start = (page - 1) * PAGE_SIZE
    end = min(start + PAGE_SIZE, total)
    page_articles = articles[start:end]

    # 并发预热当前页翻译，避免逐条串行网络请求拖慢渲染
    if enable_ai_translate:
        warm_translations([a.get('title', '') for a in page_articles]
                          + [a.get('raw_summary', '') for a in page_articles])

    # 渲染文章
    for a in page_articles:
        title = translate_safe(a['title'], enable_ai_translate)
        summary = translate_safe(a.get('raw_summary', ''), enable_ai_translate)
        raw_dt = a.get('dt', '') or ''
        dt_str = raw_dt[:10] if raw_dt else '未知日期'
        # 转义特殊字符，防止 HTML 注入破坏布局
        title_safe = title.replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
        summary_safe = summary.replace('<', '&lt;').replace('>', '&gt;') if summary else ''
        source_safe = a.get('source', '').replace('<', '&lt;').replace('>', '&gt;')
        link_safe = a.get('link', '#').replace('"', '%22')

        summary_html = f'<div class="article-summary">{summary_safe}</div>' if summary_safe else ''

        card_html = (
            '<div class="article-card">'
            f'<div class="article-title"><a href="{link_safe}" target="_blank">{title_safe}</a></div>'
            f'{summary_html}'
            '<div class="article-meta">'
            f'<span class="byline">来源 {source_safe} · {dt_str}</span>'
            f'<span>阅读原文 ↗</span>'
            '</div>'
            '</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)

    # 分页控件
    if total_pages > 1:
        st.markdown("---")
        nav_cols = st.columns([1, 2, 1])
        with nav_cols[0]:
            if page > 1:
                if st.button("⬅ 上一页", key=f"prev_{tab_key}_{page}"):
                    st.session_state[page_key] = page - 1
                    st.rerun()
        with nav_cols[1]:
            st.markdown(f"<div style='text-align:center; padding-top:8px; color:#6b7280'>第 {page} / {total_pages} 页 &nbsp;·&nbsp; 共 {total} 条</div>", unsafe_allow_html=True)
        with nav_cols[2]:
            if page < total_pages:
                if st.button("下一页 ➡", key=f"next_{tab_key}_{page}"):
                    st.session_state[page_key] = page + 1
                    st.rerun()

# ============================================================
# 主函数
# ============================================================
def main():
    config = load_data_sources()

    with st.sidebar:
        st.markdown(
            '<div style="font-family:Georgia,\'Noto Serif SC\',serif;font-size:22px;'
            'font-weight:600;letter-spacing:1px;color:#1a1a1a;line-height:1.1">KitchBath Intel</div>'
            '<div style="font-size:12px;color:#8a8172;margin-top:4px">Global Bath · Kitchen · Building Materials Intelligence</div>',
            unsafe_allow_html=True
        )
        st.divider()

        enable_translate = st.checkbox("🌐 启用自动翻译", value=True)
        sort_mode = st.selectbox("排序方式", ["时间 (最新)", "重要性 (最高)", "综合推荐"])

        if st.button("🔄 强制刷新所有数据", use_container_width=True):
            trigger_bg_update(MEDIA_STORE, config.get("media_rss"), config.get("media_scrape"), "media", interval_minutes=0)
            trigger_bg_update(ASSOC_STORE, config.get("assoc_rss"), config.get("assoc_scrape"), "assoc", interval_minutes=0)
            st.toast("✅ 后台更新已启动，约1-2分钟后刷新页面查看")

        # 更新时间显示
        state = get_update_state()
        for key, label in [("media", "媒体"), ("assoc", "协会")]:
            last = state.get(key)
            if last:
                st.caption(f"📡 {label}最后更新: {last[:16].replace('T',' ')} UTC")

        st.divider()
        st.markdown(
            '<div class="author-card">'
            '<b>Author</b> · szeyeung<br>'
            '<b>Contact</b> · <a href="mailto:adala7@sina.com">adala7@sina.com</a>'
            '</div>',
            unsafe_allow_html=True
        )

    # ---- 主内容区 ----
    all_articles = store_read(MEDIA_STORE) + store_read(ASSOC_STORE)

    # 从 config 加载舆情主题与重点企业（若缺省则用内置默认）
    themes = config.get("sentiment_themes") or SENTIMENT_THEMES
    companies = config.get("companies", [])

    # 顶部编辑刊物式导航条（英文站名，不含订阅/登录）
    st.markdown(
        '<div class="masthead">'
        '<div class="masthead-brand">KitchBath Intel</div>'
        '<div class="masthead-tag">Global Bath · Kitchen · Building Materials Intelligence</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # 主区刷新按钮：手机端侧边栏默认收起，这里保证任何设备都能强制刷新
    top_l, top_r = st.columns([1, 3])
    with top_l:
        if st.button("🔄 强制刷新数据", use_container_width=True, key="refresh_main"):
            trigger_bg_update(MEDIA_STORE, config.get("media_rss"), config.get("media_scrape"), "media", interval_minutes=0)
            trigger_bg_update(ASSOC_STORE, config.get("assoc_rss"), config.get("assoc_scrape"), "assoc", interval_minutes=0)
            st.toast("✅ 后台更新已启动，约1-2分钟后刷新页面查看")
    with top_r:
        state = get_update_state()
        parts = []
        for key, label in [("media", "媒体"), ("assoc", "协会")]:
            last = state.get(key)
            if last:
                parts.append(f"{label} {last[:16].replace('T', ' ')} UTC")
        if parts:
            st.caption("📡 最后更新：" + " · ".join(parts))

    tab_media, tab_assoc, tab_discovery, tab_sentiment, tab_analysis = st.tabs([
        "📰 行业媒体", "🏛 行业协会", "🔍 情报发现", "📡 舆情监督", "🤖 AI 分析报告"
    ])

    with tab_media:
        trigger_bg_update(MEDIA_STORE, config.get("media_rss"), config.get("media_scrape"), "media")
        articles = store_read(MEDIA_STORE)
        render_list(articles, enable_translate, sort_mode, "media")

    with tab_assoc:
        trigger_bg_update(ASSOC_STORE, config.get("assoc_rss"), config.get("assoc_scrape"), "assoc")
        articles = store_read(ASSOC_STORE)
        render_list(articles, enable_translate, sort_mode, "assoc")

    with tab_discovery:
        # 情报发现关键词 = 重点企业名 + 通用关键词，定向追踪 33 家企业动态
        keywords = (companies or []) + config.get("keywords", [])
        st.caption(f"将对 {len(companies)} 家重点企业 + {len(config.get('keywords', []))} 个行业关键词进行全网定向搜索")
        if st.button("🚀 启动全网情报发现", use_container_width=True):
            trigger_bg_update(DISCOVERY_STORE, None, None, "discovery", interval_minutes=0, keywords=keywords)
            st.toast("✅ 情报发现已启动，约1分钟后刷新")
        articles = store_read(DISCOVERY_STORE)
        render_list(articles, enable_translate, sort_mode, "discovery")

    with tab_sentiment:
        render_sentiment_tab(all_articles, enable_translate, themes, companies)

    with tab_analysis:
        st.markdown("### 🤖 AI 行业分析")
        st.caption("选择大模型、填入 API Key，对指定时间段的全部资讯生成结构化分析报告")

        ac1, ac2 = st.columns([1, 1])
        with ac1:
            ai_provider = st.selectbox(
                "AI 提供商",
                ["openrouter", "cloudflare", "openai", "deepseek", "anthropic", "qwen"],
                format_func=lambda x: {
                    "openrouter": "🆓 OpenRouter (免费模型)",
                    "cloudflare": "🆓 Cloudflare Workers AI (免费)",
                    "openai": "OpenAI (GPT-4o mini)",
                    "deepseek": "DeepSeek",
                    "anthropic": "Anthropic (Claude)",
                    "qwen": "通义千问"
                }[x],
                key="analysis_ai_provider"
            )
            ai_key = st.text_input(
                "API Key",
                type="password",
                placeholder="sk-... 或对应 key（Cloudflare 为 账户ID:API令牌）",
                help="Key 仅在当前会话中使用，不会存储",
                key="analysis_ai_key"
            )
        with ac2:
            analyze_scope = st.radio(
                "分析范围", ["行业媒体", "行业协会", "全部（含情报发现）"], horizontal=True,
                key="analysis_scope"
            )
            analyze_months = st.select_slider(
                "分析时间段", options=[3, 6, 9, 12], value=6,
                format_func=lambda x: f"近 {x} 个月", key="analysis_months_sel"
            )

        if ai_provider == "openrouter":
            st.caption("OpenRouter 免费模型：注册 openrouter.ai 获取免费 API Key，每天有免费额度")
        if ai_provider == "cloudflare":
            st.caption("Cloudflare 免费模型：dash.cloudflare.com → Workers AI 获取；Key 格式为「账户ID:API令牌」，令牌需授予 Workers AI 权限")

        if st.button("🚀 开始生成分析报告", use_container_width=True, type="primary", key="analysis_run"):
            if not ai_key:
                st.error("请先输入 API Key")
            else:
                with st.spinner(f"AI 正在分析近 {analyze_months} 个月数据，请稍候（约30-60秒）..."):
                    if analyze_scope == "行业媒体":
                        data = store_read(MEDIA_STORE)
                    elif analyze_scope == "行业协会":
                        data = store_read(ASSOC_STORE)
                    else:
                        data = (store_read(MEDIA_STORE) + store_read(ASSOC_STORE)
                                + store_read(DISCOVERY_STORE))
                    result = analyze_with_ai(data, ai_key, ai_provider, months=analyze_months)
                    st.session_state["ai_analysis"] = result
                    st.session_state["ai_analysis_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    st.session_state["ai_analysis_months"] = analyze_months

        st.divider()
        if "ai_analysis" in st.session_state:
            months_label = st.session_state.get("ai_analysis_months", 6)
            st.markdown(f"**📊 行业分析报告** · 分析周期：近 {months_label} 个月 · 生成于 {st.session_state.get('ai_analysis_time', '')}")
            st.markdown(st.session_state["ai_analysis"])
            st.divider()
            if st.button("📋 展开原始文本（可复制）"):
                st.code(st.session_state["ai_analysis"], language=None)
        else:
            st.info("💡 在上方选择模型、填入 API Key 并点击「开始生成分析报告」，结果将显示在这里。")

if __name__ == "__main__":
    main()
