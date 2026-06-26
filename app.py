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
* { margin: 0; padding: 0; box-sizing: border-box; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
.stDeployButton { display: none; }
header { visibility: hidden; }

.article-card {
    background: white;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    transition: all 0.3s ease;
    border-left: 4px solid #2563eb;
}
.article-card:hover {
    box-shadow: 0 8px 24px rgba(0,0,0,0.15);
    transform: translateY(-2px);
}
.article-title { font-size: 17px; font-weight: 600; margin-bottom: 10px; color: #1f2937; line-height: 1.5; }
.article-title a { text-decoration: none; color: inherit; }
.article-title a:hover { color: #2563eb; }
.article-summary { font-size: 13px; color: #6b7280; margin-bottom: 12px; line-height: 1.6; }
.article-meta {
    display: flex; justify-content: space-between; align-items: center;
    flex-wrap: wrap; gap: 8px; font-size: 12px; color: #9ca3af;
    border-top: 1px solid #e5e7eb; padding-top: 10px;
}
.badge { display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; }
.badge-source { background: #dbeafe; color: #1e40af; }

.analysis-box {
    background: linear-gradient(135deg, #f0f4ff 0%, #e8f0fe 100%);
    border-radius: 12px; padding: 20px; margin-bottom: 16px;
    border-left: 4px solid #4f46e5;
    white-space: pre-wrap; line-height: 1.8; font-size: 14px; color: #1f2937;
}

html { scroll-behavior: smooth; }
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

def load_rss(name: str, url: str) -> List[Dict]:
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": HEADERS["User-Agent"]})
        for entry in feed.entries:
            dt = None
            for f in ['published_parsed', 'updated_parsed']:
                if hasattr(entry, f) and getattr(entry, f):
                    try:
                        dt = datetime(*getattr(entry, f)[:6], tzinfo=timezone.utc).isoformat()
                    except:
                        pass
                    break
            # 过滤超过2年的旧内容
            if dt:
                age = datetime.now(timezone.utc) - datetime.fromisoformat(dt)
                if age.days > 730:
                    continue
            title = getattr(entry, 'title', '').strip()
            link = getattr(entry, 'link', '').strip()
            if not title or not link:
                continue
            articles.append({
                "title": title,
                "link": link,
                "source": name,
                "dt": dt or datetime.now(timezone.utc).isoformat(),
                "raw_summary": clean_text(getattr(entry, 'summary', '')),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as e:
        print(f"RSS error {name}: {e}")
    return articles

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
            for element in soup.select(selector):
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
                link = urljoin(target_url, href)
                key = title[:60]
                if key not in seen:
                    articles.append({
                        "title": title, "link": link, "source": name,
                        "dt": datetime.now(timezone.utc).isoformat(),
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
            for item in soup.select(item_sel):
                t_el = item.select_one(title_sel)
                if not t_el:
                    continue
                a_el = t_el if t_el.name == 'a' else t_el.find('a')
                title = t_el.get_text(strip=True)
                href = (a_el.get("href", "") if a_el else "")
                if not title or len(title) < 8:
                    continue
                link = urljoin(news_url, href) if href else news_url
                summary = ""
                if sum_sel:
                    s_el = item.select_one(sum_sel)
                    summary = s_el.get_text(strip=True) if s_el else ""
                key = title[:60]
                if key not in seen:
                    articles.append({
                        "title": title, "link": link, "source": name,
                        "dt": datetime.now(timezone.utc).isoformat(),
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
    import random
    articles = []
    selected_kws = random.sample(keywords, min(len(keywords), 4))
    industry_context = "bathroom kitchen sanitary plumbing ceramic"
    for kw in selected_kws:
        try:
            search_query = f'"{kw}" {industry_context} news'
            url = f"https://html.duckduckgo.com/html/?q={search_query.replace(' ', '+')}&df=m"
            res = requests.get(url, timeout=15, headers=HEADERS)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                for r in soup.select('.result')[:6]:
                    a = r.select_one('.result__a')
                    snippet = r.select_one('.result__snippet')
                    if a and a.get('href'):
                        title = a.get_text(strip=True)
                        snip_text = snippet.get_text().lower() if snippet else ""
                        if len(title) > 10:
                            articles.append({
                                "title": f"✨ {title}",
                                "link": a['href'],
                                "source": f"情报发现: {kw}",
                                "dt": datetime.now(timezone.utc).isoformat(),
                                "raw_summary": snippet.get_text(strip=True) if snippet else "",
                                "fetched_at": datetime.now(timezone.utc).isoformat(),
                            })
        except:
            pass
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
        store_write(store_path, merged[:800])
        set_update_state(state_key, datetime.now(timezone.utc).isoformat())
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
def analyze_with_ai(articles: List[Dict], api_key: str, provider: str = "openai", months: int = 6) -> str:
    """用外部大模型对指定月数内文章进行行业分析"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30 * months)
    recent = [a for a in articles if a.get('dt', '') >= cutoff.isoformat()]
    if not recent:
        return f"暂无近 {months} 个月的数据可分析，请先刷新数据或扩大时间范围。"

    # 收集所有媒体/协会来源名称，供模型排除
    all_sources = sorted(set(a.get('source', '') for a in recent if a.get('source')))
    sources_note = "、".join(all_sources[:40])

    # 提取标题摘要（最多200条，格式：[来源] 标题（摘要））
    titles_text = "\n".join([
        f"- [{a['source']}] {a['title']}" + (f"（{a['raw_summary'][:100]}）" if a.get('raw_summary') else "")
        for a in recent[:200]
    ])

    period_label = f"{cutoff.strftime('%Y年%m月')} 至今（约 {months} 个月）"

    prompt = f"""你是一位资深的全球卫浴、厨房和建材行业分析师。

以下是信息流系统在 {period_label} 从全球行业媒体和协会抓取的 {len(recent)} 条资讯，格式为「[来源平台] 标题（摘要）」：

{titles_text}

=== 重要说明 ===
方括号内是【信息来源平台名称】，不是企业名称，包括：{sources_note}
请务必区分：
- 来源平台（如 KBB Review、SDBPRO、Moebelmarkt、SanitaerNews 等）= 媒体/协会，不是行业企业
- 真正的行业企业（如 Kohler、Hansgrohe、TOTO、Grohe、Duravit、Roca、LIXIL 等）= 才应出现在企业分析中

=== 请输出以下结构的中文分析报告 ===

## 一、主要趋势归纳（{period_label}）
列出 4-6 个核心趋势，每条包含：趋势名称、具体表现、可能原因

## 二、企业动态追踪
分析真实行业企业（非媒体平台）的重要动态，包括：
- 人事变动（高管任免、离职）
- 并购与战略合作
- 新品发布与技术突破
- 财务与市场变化

## 三、地区市场热度
分析欧洲、北美、亚太、中东等各地区市场的活跃程度和关键事件

## 四、风险与机会信号
从以上资讯中识别：行业潜在风险 / 值得关注的早期机会信号

## 五、分析师综合点评
- 行业整体所处阶段判断
- 近期最值得重点关注的 3 件事
- 对下一季度的前瞻预判

请用专业但易懂的中文输出，避免将媒体平台名称误认为企业。"""

    try:
        if provider == "openai" or provider == "deepseek":
            base_url = "https://api.openai.com/v1" if provider == "openai" else "https://api.deepseek.com/v1"
            model = "gpt-4o-mini" if provider == "openai" else "deepseek-chat"
            res = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 2000},
                timeout=60
            )
            data = res.json()
            return data["choices"][0]["message"]["content"]
        elif provider == "anthropic":
            res = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                json={"model": "claude-haiku-4-5-20251001", "max_tokens": 2000, "messages": [{"role": "user", "content": prompt}]},
                timeout=60
            )
            data = res.json()
            return data["content"][0]["text"]
        elif provider == "qwen" or provider == "tongyi":
            res = requests.post(
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": "qwen-turbo", "input": {"messages": [{"role": "user", "content": prompt}]}},
                timeout=60
            )
            data = res.json()
            return data["output"]["text"]
        elif provider == "openrouter":
            model = "google/gemma-3-27b-it:free"
            res = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://kitchbathintel.streamlit.app",
                    "X-Title": "KitchBath Intel Dashboard"
                },
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 2000},
                timeout=90
            )
            data = res.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"]
            else:
                return f"OpenRouter 返回错误：{data.get('error', {}).get('message', str(data))}"
        else:
            return "不支持的 AI 提供商，请选择 OpenRouter / OpenAI / DeepSeek / Anthropic / 通义千问。"
    except Exception as e:
        return f"AI 分析出错：{str(e)}\n\n请检查 API Key 是否正确，以及网络连接是否正常。"


# ============================================================
# 舆情监督功能 v2 — 精准复合匹配 + 可选 AI 二次筛选
# ============================================================

# ---- 主题定义：采用「必须命中 + 加分词」双层逻辑 ----
SENTIMENT_THEMES = {
    "高管人事变动": {
        "must_any_zh": ["离职", "辞职", "卸任", "退休", "接任", "就任", "任命为", "升任", "出任", "新任"],
        "must_any_en": ["resign", "steps down", "step down", "departure", "appointed as", "named as",
                        "new CEO", "new president", "successor", "replaces", "takes over as",
                        "joins as", "promoted to", "hired as", "fired", "ousted"],
        "boost_zh": ["CEO", "总裁", "董事长", "总经理", "首席执行官", "副总裁"],
        "boost_en": ["CEO", "president", "chairman", "chief", "executive", "VP"],
        "exclude_if_en": ["award", "conference", "exhibition", "show", "report", "study",
                          "trend", "market", "product", "collection", "design"],
        "color": "#ef4444",
        "icon": "\U0001f454"
    },
    "并购与战略合作": {
        "must_any_zh": ["收购", "并购", "合并", "战略合作", "入股", "控股", "股权转让", "联合成立"],
        "must_any_en": ["acquires", "acquired", "acquisition", "merger", "merges", "takeover",
                        "buys", "purchased", "joint venture", "strategic partnership", "stakes in",
                        "invest in", "investment in", "equity stake"],
        "boost_zh": ["投资", "合作"],
        "boost_en": ["deal", "billion", "million", "agreement"],
        "exclude_if_en": ["award", "conference", "exhibition"],
        "color": "#f59e0b",
        "icon": "\U0001f91d"
    },
    "新品与技术发布": {
        "must_any_zh": ["发布", "推出", "上市", "新品", "首发", "全新", "专利获批", "技术突破"],
        "must_any_en": ["launches", "unveiled", "introduces", "new product", "debut",
                        "released", "announcing", "patent granted", "breakthrough"],
        "boost_zh": ["创新", "智能", "节水"],
        "boost_en": ["award", "design", "smart", "IoT", "sustainable"],
        "exclude_if_en": [],
        "color": "#10b981",
        "icon": "\U0001f680"
    },
    "财务与市场变化": {
        "must_any_zh": ["裁员", "亏损", "盈利增长", "营收下滑", "破产", "重组", "市场份额", "季报", "年报"],
        "must_any_en": ["layoffs", "job cuts", "bankruptcy", "restructuring", "revenue decline",
                        "profit warning", "quarterly results", "annual report", "market share",
                        "sales drop", "record revenue", "earnings"],
        "boost_zh": ["增长", "下滑"],
        "boost_en": ["billion", "million", "percent", "growth", "decline"],
        "exclude_if_en": ["award", "exhibition", "conference"],
        "color": "#6366f1",
        "icon": "\U0001f4c8"
    }
}


def match_sentiment_theme(article: Dict, theme_config: Dict) -> tuple:
    """精准复合匹配。返回 (matched: bool, confidence: int)"""
    title = article.get("title", "") or ""
    summary = article.get("raw_summary", "") or ""
    text = (title + " " + summary).lower()

    must_zh = theme_config.get("must_any_zh", [])
    must_en = theme_config.get("must_any_en", [])
    boost_zh = theme_config.get("boost_zh", [])
    boost_en = theme_config.get("boost_en", [])
    excludes = theme_config.get("exclude_if_en", [])

    hit_must = any(kw.lower() in text for kw in must_zh + must_en)
    if not hit_must:
        return False, 0

    hit_exclude = any(kw.lower() in text for kw in excludes) if excludes else False
    boost_score = sum(1 for kw in boost_zh + boost_en if kw.lower() in text)

    if hit_exclude and boost_score == 0:
        return False, 0

    confidence = 2 if boost_score >= 1 else 1
    return True, confidence


def get_sentiment_articles(all_articles: List[Dict], theme_name: str, days: int) -> List[Dict]:
    """获取指定主题、指定天数内的匹配文章，按置信度+时间排序"""
    theme_config = SENTIMENT_THEMES.get(theme_name, {})
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    matched = []
    for a in all_articles:
        if (a.get("dt", "") or "") < cutoff:
            continue
        hit, conf = match_sentiment_theme(a, theme_config)
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
            res = requests.post("https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                         "HTTP-Referer": "https://kitchbathintel.streamlit.app"},
                json={"model": "google/gemma-3-27b-it:free",
                      "messages": [{"role": "user", "content": prompt}], "max_tokens": 1500},
                timeout=90)
            result_text = res.json()["choices"][0]["message"]["content"]
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


def render_sentiment_tab(all_articles: List[Dict], enable_translate: bool):
    """渲染舆情监督 Tab"""
    st.markdown("### 📡 舆情监督中心")
    st.caption("精准追踪行业关键动态：人事变动、并购消息、新品发布、财务预警")

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
            ["openrouter", "openai", "deepseek", "anthropic", "qwen"],
            format_func=lambda x: {
                "openrouter": "🆓 OpenRouter 免费",
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
            placeholder="sk-...",
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
    stat_cols = st.columns(len(SENTIMENT_THEMES))
    theme_counts = {}
    for i, (theme_name, theme_cfg) in enumerate(SENTIMENT_THEMES.items()):
        matched = get_sentiment_articles(all_articles, theme_name, selected_days)
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

    # 分主题详情
    for theme_name, theme_cfg in SENTIMENT_THEMES.items():
        matched = theme_counts[theme_name]
        color = theme_cfg["color"]
        icon = theme_cfg["icon"]
        is_first = theme_name == "高管人事变动"
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
        f'<div style="background:white;border-radius:10px;padding:16px;margin-bottom:10px;'
        f'border-left:4px solid {color};box-shadow:0 1px 6px rgba(0,0,0,0.08)">'
        f'<div style="font-size:15px;font-weight:600;margin-bottom:6px">'
        f'<a href="{link}" target="_blank" style="text-decoration:none;color:#1f2937">{title_e}</a>'
        f'{conf_badge}</div>'
        f'{summary_html}{ai_html}'
        f'<div style="display:flex;justify-content:space-between;font-size:12px;color:#9ca3af;'
        f'border-top:1px solid #f3f4f6;padding-top:8px;margin-top:8px">'
        f'<span>📍 {source_e}</span><span>🕒 {dt_str}</span>'
        f'</div></div>',
        unsafe_allow_html=True
    )

# ============================================================
# UI 渲染 - 带分页的文章列表
# ============================================================
PAGE_SIZE = 20

def translate_safe(text: str, enable: bool) -> str:
    if not enable or not text or len(text) < 3:
        return text
    try:
        # 如果已经主要是中文就跳过
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        if chinese_chars / max(len(text), 1) > 0.3:
            return text
        return GoogleTranslator(source='auto', target='zh-CN').translate(text[:500]) or text
    except:
        return text

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
            f'<span><span class="badge badge-source">📍 {source_safe}</span></span>'
            f'<span>🕒 {dt_str}</span>'
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
        st.title("🛰 行业情报系统 v3.5")
        st.caption("实时监控全球卫浴行业动态")
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

        # ---- AI 分析板块 ----
        st.markdown("### 🤖 AI 行业分析")
        st.caption("输入大模型 API Key，对近一年数据生成分析报告")

        ai_provider = st.selectbox(
            "AI 提供商",
            ["openrouter", "openai", "deepseek", "anthropic", "qwen"],
            format_func=lambda x: {
                "openrouter": "🆓 OpenRouter (免费模型)",
                "openai": "OpenAI (GPT-4o mini)",
                "deepseek": "DeepSeek",
                "anthropic": "Anthropic (Claude)",
                "qwen": "通义千问"
            }[x]
        )
        if ai_provider == "openrouter":
            st.caption("OpenRouter 免费模型：注册 openrouter.ai 获取免费 API Key，每天有免费额度")
        ai_key = st.text_input(
            "API Key",
            type="password",
            placeholder="sk-... 或对应 key",
            help="Key 仅在当前会话中使用，不会存储"
        )

        analyze_scope = st.radio(
            "分析范围",
            ["行业媒体", "行业协会", "全部合并"],
            horizontal=True
        )
        analyze_months = st.select_slider(
            "分析时间段",
            options=[3, 6, 9, 12],
            value=6,
            format_func=lambda x: f"近 {x} 个月"
        )

        if st.button("🚀 开始生成分析报告", use_container_width=True, type="primary"):
            if not ai_key:
                st.error("请先输入 API Key")
            else:
                with st.spinner(f"AI 正在分析近 {analyze_months} 个月数据，请稍候（约30-60秒）..."):
                    if analyze_scope == "行业媒体":
                        data = store_read(MEDIA_STORE)
                    elif analyze_scope == "行业协会":
                        data = store_read(ASSOC_STORE)
                    else:
                        data = store_read(MEDIA_STORE) + store_read(ASSOC_STORE)

                    result = analyze_with_ai(data, ai_key, ai_provider, months=analyze_months)
                    st.session_state["ai_analysis"] = result
                    st.session_state["ai_analysis_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    st.session_state["ai_analysis_months"] = analyze_months

    # ---- 主内容区 ----
    all_articles = store_read(MEDIA_STORE) + store_read(ASSOC_STORE)

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
        keywords = config.get("keywords", [])
        if st.button("🚀 启动全网情报发现", use_container_width=True):
            trigger_bg_update(DISCOVERY_STORE, None, None, "discovery", interval_minutes=0, keywords=keywords)
            st.toast("✅ 情报发现已启动，约1分钟后刷新")
        articles = store_read(DISCOVERY_STORE)
        render_list(articles, enable_translate, sort_mode, "discovery")

    with tab_sentiment:
        render_sentiment_tab(all_articles, enable_translate)

    with tab_analysis:
        if "ai_analysis" in st.session_state:
            months_label = st.session_state.get("ai_analysis_months", 6)
            st.markdown(f"**📊 行业分析报告** · 分析周期：近 {months_label} 个月 · 生成于 {st.session_state.get('ai_analysis_time', '')}")
            st.divider()
            # 用 st.markdown 直接渲染 markdown 内容（不套 HTML div，避免转义问题）
            st.markdown(st.session_state["ai_analysis"])
            st.divider()
            if st.button("📋 展开原始文本（可复制）"):
                st.code(st.session_state["ai_analysis"], language=None)
        else:
            st.info("💡 请在左侧侧边栏输入 API Key 并点击「开始生成分析报告」，结果将显示在这里。")
            st.markdown("""
**功能说明：**
- 自动提取指定月数内的全部行业资讯（媒体+协会）
- 通过大模型识别主要趋势、企业动态、市场热点
- **已内置媒体来源提示**，模型不会将媒体平台误认为企业
- 支持 🆓 OpenRouter 免费模型 / OpenAI / DeepSeek / Anthropic / 通义千问
- API Key 仅在当前浏览器会话使用，不会被存储或上传
            """)

if __name__ == "__main__":
    main()
