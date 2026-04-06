"""
Sentinel Crawlers — Playwright 동적 크롤링 + Google News RSS

Phase 1 (자금): Bizinfo 기업마당 (Playwright), K-Startup (Playwright), Google News
Phase 2 (규제): Google News 식약처/관세
Phase 3 (플랫폼): Google News 이커머스
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from config import COMPANY_PROFILE, KEYWORDS
from db import generate_item_id

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0"
}

# ── 연관성 필터 ───────────────────────────────────────────

RELEVANCE_KEYWORDS = (
    COMPANY_PROFILE.get("industry", [])
    + KEYWORDS["primary"]
    + KEYWORDS["support_type"]
    + ["온라인", "해외", "수출", "수입", "통관", "관세", "플랫폼", "셀러",
       "판매자", "스마트스토어", "쿠팡", "11번가",
       "건기식", "식품", "영양", "비타민", "보충제",
       "1인", "소규모", "예비창업", "스타트업",
       "수원", "영통", "경기"]
)

EXCLUDE_KEYWORDS = [
    "자동차", "조선", "반도체", "건설", "토목", "축산", "어업",
    "광업", "제철", "철강", "용접", "배관", "전기공사",
    "유아교육", "어린이집", "장례",
]


def _is_relevant(title: str, body: str = "") -> bool:
    text = (title + " " + body).lower()
    for kw in EXCLUDE_KEYWORDS:
        if kw in text:
            return False
    for kw in RELEVANCE_KEYWORDS:
        if kw.lower() in text:
            return True
    general = ["전국", "소상공인", "중소기업", "창업", "온라인", "수출"]
    return any(kw in text for kw in general)


def _extract_keywords(title: str) -> List[str]:
    return [kw for kw in RELEVANCE_KEYWORDS if kw in title][:5]


def _dedupe(items: List[Dict]) -> List[Dict]:
    seen = set()
    unique = []
    for r in items:
        if r["item_id"] not in seen:
            seen.add(r["item_id"])
            unique.append(r)
    return unique


# ══════════════════════════════════════════════════════════
# Phase 1: 기업마당 (Playwright 동적 크롤링)
# ══════════════════════════════════════════════════════════

async def crawl_bizinfo_playwright() -> List[Dict[str, Any]]:
    """기업마당 Playwright 동적 크롤링"""
    results = []
    search_terms = ["이커머스", "구매대행", "청년창업", "소상공인", "수출", "헬스케어", "온라인판매", "건강기능식품"]

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("Playwright 미설치 — requests 폴백")
        return crawl_bizinfo_requests()

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            for keyword in search_terms:
                try:
                    url = f"https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/list.do?rows=10&cpage=1&skey=1&sval={quote_plus(keyword)}"
                    await page.goto(url, timeout=15000)
                    await page.wait_for_timeout(2000)

                    rows = await page.query_selector_all("table tbody tr")
                    for row in rows[:10]:
                        try:
                            link_el = await row.query_selector("a")
                            if not link_el:
                                continue
                            title = (await link_el.inner_text()).strip()
                            if not title or len(title) < 5:
                                continue
                            if not _is_relevant(title):
                                continue

                            href = await link_el.get_attribute("href") or ""
                            if href and not href.startswith("http"):
                                href = "https://www.bizinfo.go.kr" + href

                            # 마감일 추출
                            tds = await row.query_selector_all("td")
                            deadline = ""
                            org = ""
                            for td in tds:
                                text = (await td.inner_text()).strip()
                                dates = re.findall(r"\d{4}[.-]\d{2}[.-]\d{2}", text)
                                if dates:
                                    deadline = dates[-1].replace(".", "-")
                                elif not org and 2 < len(text) < 30:
                                    org = text

                            # 수원/경기 가점 체크
                            is_local = any(loc in title for loc in ["수원", "영통", "경기"])

                            results.append({
                                "item_id": generate_item_id("bizinfo", title, href),
                                "source": "bizinfo",
                                "category": "funding",
                                "title": title,
                                "url": href,
                                "deadline": deadline,
                                "keywords": _extract_keywords(title),
                                "raw_data": {
                                    "search_keyword": keyword,
                                    "organization": org,
                                    "is_local_suwon": is_local,
                                },
                            })
                        except Exception:
                            pass
                except Exception as e:
                    logger.debug(f"bizinfo ({keyword}): {e}")

            await browser.close()
    except Exception as e:
        logger.warning(f"Playwright 실패: {e} — requests 폴백")
        return crawl_bizinfo_requests()

    unique = _dedupe(results)
    logger.info(f"[Bizinfo/Playwright] {len(unique)}개 수집")
    return unique


def crawl_bizinfo_requests() -> List[Dict[str, Any]]:
    """기업마당 requests 폴백"""
    results = []
    search_terms = ["이커머스", "구매대행", "청년창업", "소상공인", "수출", "헬스케어", "온라인판매", "건강기능식품"]

    for keyword in search_terms:
        try:
            url = f"https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/list.do?rows=10&cpage=1&skey=1&sval={quote_plus(keyword)}"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            for row in soup.select("table tbody tr")[:10]:
                link_el = row.select_one("a")
                if not link_el:
                    continue
                title = link_el.get_text(strip=True)
                if not title or len(title) < 5 or not _is_relevant(title):
                    continue

                href = link_el.get("href", "")
                if href and not href.startswith("http"):
                    href = "https://www.bizinfo.go.kr" + href

                deadline = ""
                for td in row.select("td"):
                    dates = re.findall(r"\d{4}[.-]\d{2}[.-]\d{2}", td.get_text(strip=True))
                    if dates:
                        deadline = dates[-1].replace(".", "-")

                is_local = any(loc in title for loc in ["수원", "영통", "경기"])

                results.append({
                    "item_id": generate_item_id("bizinfo", title, href),
                    "source": "bizinfo",
                    "category": "funding",
                    "title": title,
                    "url": href,
                    "deadline": deadline,
                    "keywords": _extract_keywords(title),
                    "raw_data": {"search_keyword": keyword, "is_local_suwon": is_local},
                })
        except Exception as e:
            logger.warning(f"bizinfo ({keyword}): {e}")

    unique = _dedupe(results)
    logger.info(f"[Bizinfo/requests] {len(unique)}개 수집")
    return unique


# ══════════════════════════════════════════════════════════
# Phase 1: K-Startup (Playwright 동적 크롤링)
# ══════════════════════════════════════════════════════════

async def crawl_kstartup_playwright() -> List[Dict[str, Any]]:
    """K-Startup Playwright 크롤링"""
    results = []

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("Playwright 미설치")
        return []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto("https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do", timeout=15000)
            await page.wait_for_timeout(3000)

            rows = await page.query_selector_all("table tbody tr, .tbl_list tbody tr")
            for row in rows[:20]:
                try:
                    link_el = await row.query_selector("a")
                    if not link_el:
                        continue
                    title = (await link_el.inner_text()).strip()
                    if not title or len(title) < 5:
                        continue

                    href = await link_el.get_attribute("href") or ""
                    if href and not href.startswith("http"):
                        href = "https://www.k-startup.go.kr" + href

                    tds = await row.query_selector_all("td")
                    deadline = ""
                    for td in tds:
                        text = (await td.inner_text()).strip()
                        dates = re.findall(r"\d{4}[.-]\d{2}[.-]\d{2}", text)
                        if dates:
                            deadline = dates[-1].replace(".", "-")

                    results.append({
                        "item_id": generate_item_id("kstartup", title, href),
                        "source": "kstartup",
                        "category": "funding",
                        "title": title,
                        "url": href,
                        "deadline": deadline,
                        "keywords": _extract_keywords(title) or ["창업지원"],
                        "raw_data": {},
                    })
                except Exception:
                    pass

            await browser.close()
    except Exception as e:
        logger.warning(f"K-Startup 크롤링 실패: {e}")

    unique = _dedupe(results)
    logger.info(f"[K-Startup/Playwright] {len(unique)}개 수집")
    return unique


# ══════════════════════════════════════════════════════════
# Google News RSS (규제 / 플랫폼 / 창업)
# ══════════════════════════════════════════════════════════

def _crawl_google_news(queries: List[str], category: str) -> List[Dict[str, Any]]:
    results = []
    current_year = datetime.now().year  # 2026

    for query in queries:
        try:
            # 최근 30일 내 기사만 (when:30d)
            encoded = quote_plus(query)
            url = f"https://news.google.com/rss/search?q={encoded}+when:30d&hl=ko&gl=KR&ceid=KR:ko"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "xml")

            for item in soup.select("item")[:10]:
                title_el = item.select_one("title")
                link_el = item.select_one("link")
                pub_el = item.select_one("pubDate")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                title_clean = title.rsplit(" - ", 1)[0].strip() if " - " in title else title
                source_name = title.rsplit(" - ", 1)[1].strip() if " - " in title else ""

                if not _is_relevant(title_clean):
                    continue

                # 날짜 필터: 올해(2026년) 기사만
                pub_text = pub_el.get_text(strip=True) if pub_el else ""
                if pub_text and str(current_year) not in pub_text:
                    continue

                # 제목에 작년 이하 연도가 포함된 기사 제외
                past_years = [str(y) for y in range(2020, current_year)]
                if any(py in title_clean for py in past_years):
                    continue

                link = link_el.get_text(strip=True) if link_el else ""

                results.append({
                    "item_id": generate_item_id(f"news_{category}", title_clean, link),
                    "source": "news",
                    "category": category,
                    "title": title_clean,
                    "url": link,
                    "keywords": _extract_keywords(title_clean),
                    "raw_data": {
                        "query": query,
                        "media": source_name,
                        "pub_date": pub_el.get_text(strip=True) if pub_el else "",
                    },
                })
        except Exception as e:
            logger.warning(f"Google News ({query}): {e}")

    unique = _dedupe(results)
    logger.info(f"[News/{category}] {len(unique)}개 수집")
    return unique


def crawl_funding_news():
    now = datetime.now()
    year = now.year
    month = now.month

    return _crawl_google_news([
        f"{year}년 청년창업 지원사업 이커머스",
        f"{year}년 소상공인 지원금 온라인판매",
        f"{year}년 수출 바우처 소상공인",
        f"경기도 수원 창업 지원 {year}",
        f"{year}년 1인 기업 창업 지원사업",
        f"창업진흥원 {year}년 지원사업 모집",
        f"경기도 {year}년 소상공인 지원",
        f"수원시 {year}년 창업 지원",
        f"중소벤처기업부 {year}년 정책자금",
        f"{year}년 {month}월 창업 지원사업 모집",
    ], "funding")


def crawl_regulation_news():
    year = datetime.now().year
    return _crawl_google_news([
        f"식약처 건강기능식품 {year}",
        f"건기식 인증 규정 {year}",
        f"해외직구 통관 관세 {year}",
        f"구매대행 규제 {year}",
        f"이커머스 식품 안전 {year}",
    ], "regulation")


def crawl_platform_news():
    year = datetime.now().year
    return _crawl_google_news([
        f"네이버 스마트스토어 정책 변경 {year}",
        f"쿠팡 수수료 셀러 {year}",
        f"이커머스 플랫폼 정책 {year}",
        f"해외직구 구매대행 트렌드 {year}",
        f"웰니스 이커머스 트렌드 {year}",
    ], "platform")


# ══════════════════════════════════════════════════════════
# Phase 1+: 공식 사이트 직접 크롤링 (정부/창진원/경기도/수원시)
# ══════════════════════════════════════════════════════════

def crawl_official_sites() -> List[Dict[str, Any]]:
    """정부기관 공식 사이트 공고 수집"""
    results = []
    year = datetime.now().year

    sites = [
        # (이름, URL, 카테고리)
        ("창업진흥원", f"https://www.kised.or.kr/menu.es?mid=a10305010000", "funding"),
        ("중소벤처기업부", "https://www.mss.go.kr/site/smba/ex/bbs/List.do?cbIdx=86", "funding"),
        ("소상공인진흥공단", "https://www.semas.or.kr/web/board/webBoardList.kmdc?bCd=2", "funding"),
        ("경기경제과학진흥원", "https://www.gbsa.or.kr/bbs/board.php?bo_table=notice", "funding"),
        ("수원시청", "https://www.suwon.go.kr/web/board/BD_board.list.do?bbsCd=1042", "funding"),
        ("수원산업진흥원", "https://www.swip.or.kr/main/board.do?boardId=BBS_0000006", "funding"),
    ]

    for site_name, url, category in sites:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            # 범용 파서: 테이블 또는 리스트에서 링크 추출
            links = []
            for selector in ["table tbody tr a", ".board_list a", ".bbs_list a",
                             ".list_item a", "ul.list li a", ".tbl_list a",
                             ".bbsListTbl a", "div.list a"]:
                links.extend(soup.select(selector))

            # 직접 a 태그가 안 잡히면 전체 a에서 제목처럼 보이는 것 추출
            if not links:
                links = [a for a in soup.select("a") if a.get_text(strip=True) and 10 < len(a.get_text(strip=True)) < 150]

            for link in links[:15]:
                title = link.get_text(strip=True)
                if not title or len(title) < 8:
                    continue

                # 연도 필터: 올해 또는 연도 미표기만
                past_years = [str(y) for y in range(2020, year)]
                if any(py in title for py in past_years):
                    continue

                href = link.get("href", "")
                if href and not href.startswith("http"):
                    # 상대 경로 처리
                    from urllib.parse import urljoin
                    href = urljoin(url, href)

                # 지원사업/공고 관련 키워드 체크
                support_kw = ["모집", "공고", "지원", "신청", "접수", "안내", "사업",
                              "창업", "소상공인", "바우처", "자금", "대출", "보조"]
                if not any(kw in title for kw in support_kw):
                    continue

                is_local = any(loc in title for loc in ["수원", "영통", "경기"])

                results.append({
                    "item_id": generate_item_id(site_name, title, href),
                    "source": site_name,
                    "category": category,
                    "title": f"[{site_name}] {title}",
                    "url": href,
                    "deadline": "",
                    "keywords": _extract_keywords(title) + ([site_name] if site_name not in _extract_keywords(title) else []),
                    "raw_data": {"site": site_name, "is_local_suwon": is_local},
                })

        except Exception as e:
            logger.warning(f"[{site_name}] 크롤링 실패: {e}")

    unique = _dedupe(results)
    logger.info(f"[공식사이트] {len(unique)}개 수집 ({len(sites)}개 사이트)")
    return unique


# ══════════════════════════════════════════════════════════
# 통합 실행
# ══════════════════════════════════════════════════════════

def run_all_crawlers() -> List[Dict[str, Any]]:
    all_items = []

    # Playwright 크롤러 (async)
    loop = asyncio.new_event_loop()
    try:
        bizinfo = loop.run_until_complete(crawl_bizinfo_playwright())
        all_items.extend(bizinfo)
    except Exception as e:
        logger.error(f"Bizinfo: {e}")
        all_items.extend(crawl_bizinfo_requests())

    try:
        kstartup = loop.run_until_complete(crawl_kstartup_playwright())
        all_items.extend(kstartup)
    except Exception as e:
        logger.error(f"K-Startup: {e}")
    loop.close()

    # 공식사이트 직접 크롤링
    try:
        all_items.extend(crawl_official_sites())
    except Exception as e:
        logger.error(f"공식사이트: {e}")

    # Google News (동기)
    all_items.extend(crawl_funding_news())
    all_items.extend(crawl_regulation_news())
    all_items.extend(crawl_platform_news())

    logger.info(f"[총합] {len(all_items)}개 아이템 수집")
    return all_items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    items = run_all_crawlers()
    for item in items[:10]:
        local = item.get("raw_data", {}).get("is_local_suwon", False)
        print(f"  [{item['category']:10s}] {'📍' if local else '  '} {item['title'][:60]}")
    print(f"\n총 {len(items)}개 수집")
