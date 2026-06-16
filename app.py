# -*- coding: utf-8 -*-
"""
行业情报系统 —— 主入口

运作流程（重新设计后）：
1. 冷启动（两个分类的磁盘缓存都是空的，典型场景：Streamlit Cloud 容器刚被唤醒/重新部署）
   → 把全部 ~25 个数据源合并成一批，用线程池并发抓取，整体耗时 ≈ 最慢的单个请求，
     而不是逐个请求的耗时总和。
2. 热启动（磁盘上已有数据）→ 直接读盘，毫秒级展示；同时检查是否超过静默更新间隔，
   超过则在后台线程里悄悄重新抓取，不阻塞当前用户的页面。
   用一个基于时间戳的"锁"防止多个用户同时触发重复抓取。
3. 渲染：头条快讯 + 网格卡片，按需分页（点击"加载更多"），AI 摘要仅对当前可见卡片按需调用。
"""

import threading
from datetime import datetime, timezone

import streamlit as st

import enrich
import store
import ui
from config import SOURCE_GROUPS, PAGE_SIZE, BG_UPDATE_INTERVAL_MIN, LOCK_STALE_MIN
from fetcher import fetch_all

st.set_page_config(
    page_title="行业情报系统",
    page_icon="🛰",
    layout="wide",
    initial_sidebar_state="collapsed",
)
ui.inject_css()

STORE_PATHS = {"media": store.MEDIA_STORE, "assoc": store.ASSOC_STORE}
SOURCE_GROUP_OF = {s["name"]: key for key, sources in SOURCE_GROUPS.items() for s in sources}


# ============================================================
# 数据获取
# ============================================================
def _save_result(key, fresh_articles, status, merge_with_existing=True):
    fresh_articles = enrich.enrich(fresh_articles)
    if merge_with_existing:
        existing = store.store_read(STORE_PATHS[key])
        merged = store.merge_articles(existing, fresh_articles)
    else:
        merged = fresh_articles
    store.store_write(STORE_PATHS[key], merged)
    store.set_update_state(**{
        f"{key}_updated_at": datetime.now(timezone.utc).isoformat(),
        f"{key}_status": status,
    })
    return merged


def _bg_update(key):
    try:
        fresh, status = fetch_all(SOURCE_GROUPS[key])
        _save_result(key, fresh, status, merge_with_existing=True)
    except Exception:
        pass
    finally:
        store.release_lock(key)


def cold_start_all():
    """两个分类都没有缓存时，把全部数据源合并成一批并发抓取，只等一次"""
    all_sources = [s for sources in SOURCE_GROUPS.values() for s in sources]
    fresh, status = fetch_all(all_sources)
    fresh = enrich.enrich(fresh)

    by_group = {"media": [], "assoc": []}
    status_by_group = {"media": {}, "assoc": {}}
    for a in fresh:
        grp = SOURCE_GROUP_OF.get(a["source"], "media")
        by_group[grp].append(a)
    for name, st_ in status.items():
        grp = SOURCE_GROUP_OF.get(name, "media")
        status_by_group[grp][name] = st_

    now = datetime.now(timezone.utc).isoformat()
    for key in ("media", "assoc"):
        store.store_write(STORE_PATHS[key], by_group[key])
        store.set_update_state(**{
            f"{key}_updated_at": now,
            f"{key}_status": status_by_group[key],
        })
    return by_group["media"], by_group["assoc"]


def ensure_data(key):
    """返回 (articles, bg_triggered)。已有缓存时静默检查是否需要后台更新。"""
    existing = store.store_read(STORE_PATHS[key])
    if existing:
        if store.needs_update(key, BG_UPDATE_INTERVAL_MIN) and store.try_acquire_lock(key, LOCK_STALE_MIN):
            threading.Thread(target=_bg_update, args=(key,), daemon=True).start()
            return existing, True
        return existing, False

    label = "媒体" if key == "media" else "协会"
    with st.spinner(f"首次加载{label}数据，正在并发抓取全部数据源..."):
        fresh, status = fetch_all(SOURCE_GROUPS[key])
        merged = _save_result(key, fresh, status, merge_with_existing=False)
    return merged, False


# ============================================================
# 搜索过滤
# ============================================================
def apply_search(articles, query):
    if not query:
        return articles
    q = query.strip().lower()
    if not q:
        return articles
    out = []
    for a in articles:
        haystack = f"{a.get('title','')} {a.get('title_cn','')} {a.get('source','')}".lower()
        if q in haystack:
            out.append(a)
    return out


def fmt_update_time(iso_str):
    if not iso_str:
        return "未知"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%m-%d %H:%M")
    except Exception:
        return "未知"


# ============================================================
# 一个分类的整页渲染（头条 + 网格 + 分页 + 诊断）
# ============================================================
def render_category_tab(key, articles, enable_ai):
    if not articles:
        ui.render_empty("没有匹配的情报，换个关键词试试")
        return

    page_key = f"page_{key}"
    st.session_state.setdefault(page_key, 1)
    page = st.session_state[page_key]
    visible = articles[: page * PAGE_SIZE]
    hero, grid_items = visible[0], visible[1:]

    def summary_fn(article):
        if enable_ai:
            return enrich.get_ai_summary(article["title"], article.get("raw_summary", ""), article["source"])
        return article.get("summary_clean") or ""

    ui.render_hero(hero, summary_fn(hero))

    if grid_items:
        ui.render_section_label("更多情报 · MORE DISPATCHES")
        ui.render_grid(grid_items, summary_fn=summary_fn, start_no=2)

    total, shown = len(articles), len(visible)
    if shown < total:
        st.caption(f"已显示 {shown} / {total} 条")
        if st.button(f"加载更多（还有 {total - shown} 条）", key=f"more_{key}", use_container_width=True):
            st.session_state[page_key] = page + 1
            st.rerun()
    else:
        st.caption(f"已显示全部 {total} 条")

    status = store.get_update_state().get(f"{key}_status")
    ui.render_source_status(status)


# ============================================================
# 主流程
# ============================================================
def main():
    media_existing = store.store_read(STORE_PATHS["media"])
    assoc_existing = store.store_read(STORE_PATHS["assoc"])

    if not media_existing and not assoc_existing:
        with st.spinner("首次加载，正在并发同步全部数据源（媒体 + 协会）..."):
            media_articles, assoc_articles = cold_start_all()
        bg_triggered = False
    else:
        media_articles, bg1 = ensure_data("media")
        assoc_articles, bg2 = ensure_data("assoc")
        bg_triggered = bg1 or bg2

    media_articles = enrich.enrich(media_articles)
    assoc_articles = enrich.enrich(assoc_articles)

    state = store.get_update_state()
    total_sources = sum(len(v) for v in SOURCE_GROUPS.values())
    ui.render_header(state.get("media_updated_at"), state.get("assoc_updated_at"), total_sources)

    col_search, col_sort, col_ai, col_refresh = st.columns([4, 2, 2, 1.2])
    with col_search:
        search_query = st.text_input(
            "搜索", placeholder="🔍  搜索标题关键词 / 来源…", label_visibility="collapsed"
        )
    with col_sort:
        sort_mode = st.selectbox(
            "排序", ["时间优先", "重要性优先", "综合排序"], label_visibility="collapsed"
        )
    with col_ai:
        enable_ai = st.checkbox("启用 AI 深度摘要", value=False, help="需在部署环境配置 ANTHROPIC_API_KEY")
    with col_refresh:
        if st.button("🔄 刷新", use_container_width=True):
            store.set_update_state(
                media_updated_at=None, assoc_updated_at=None,
                media_lock_ts=None, assoc_lock_ts=None,
            )
            for k in ("page_media", "page_assoc"):
                st.session_state.pop(k, None)
            st.rerun()

    media_articles = enrich.sort_articles(media_articles, sort_mode)
    assoc_articles = enrich.sort_articles(assoc_articles, sort_mode)

    media_filtered = apply_search(media_articles, search_query)
    assoc_filtered = apply_search(assoc_articles, search_query)

    ui.render_stats(
        len(media_filtered), len(assoc_filtered),
        fmt_update_time(state.get("media_updated_at")),
        fmt_update_time(state.get("assoc_updated_at")),
    )
    if bg_triggered:
        st.caption("⟳ 后台正在静默更新数据，过一会儿重新打开可看到最新内容")

    tab_media, tab_assoc = st.tabs([
        f"📰 行业媒体（{len(media_filtered)}）",
        f"🏛 行业协会（{len(assoc_filtered)}）",
    ])
    with tab_media:
        render_category_tab("media", media_filtered, enable_ai)
    with tab_assoc:
        render_category_tab("assoc", assoc_filtered, enable_ai)

    st.markdown(
        '<div style="margin-top:40px; padding-top:14px; border-top:1px solid var(--border); '
        'font-family:var(--f-mono); font-size:11px; color:var(--text-mute);">'
        "标题由 Google 翻译自动转译，可能存在误差 · AI 摘要由 Claude 生成（启用时）"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
