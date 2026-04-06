"""
Daily Wellness Scout Agent
매일 자동으로 글로벌 웰니스 트렌드를 분석하고 리포트를 생성합니다.
"""
import asyncio
import schedule
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from anthropic import Anthropic
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import os
import logging
import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import re
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from db_manager import DatabaseManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/daily_scout.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DailyWellnessScout:
    """매일 자동 실행되는 웰니스 트렌드 모니터링 에이전트"""

    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.db = DatabaseManager()
        self.ua = UserAgent()

        # 지역별 설정 (실제 크롤링 URL 포함)
        self.regions = {
            "japan": {
                "name": "🇯🇵 일본",
                "sources": ["라쿠텐", "아마존JP", "코스메"],
                "keywords": ["サプリメント", "健康食品", "ウェルネス", "プロテイン"],
                "crawl_urls": [
                    {
                        "source": "라쿠텐 헬스케어",
                        "url": "https://ranking.rakuten.co.jp/daily/110601/",
                        "type": "rakuten"
                    },
                    {
                        "source": "iHerb JP 스포츠",
                        "url": "https://jp.iherb.com/c/sports-nutrition",
                        "type": "iherb"
                    },
                    {
                        "source": "iHerb JP 비타민",
                        "url": "https://jp.iherb.com/c/vitamins",
                        "type": "iherb"
                    },
                    {
                        "source": "iHerb JP 오메가3",
                        "url": "https://jp.iherb.com/c/omega-3-fish-oil",
                        "type": "iherb"
                    }
                ]
            },
            "china": {
                "name": "🇨🇳 중국",
                "sources": ["1688", "타오바오", "징동", "iHerb CN"],
                "keywords": ["保健品", "营养补充", "健康", "蛋白粉", "维生素", "鱼油"],
                "crawl_urls": [
                    {
                        "source": "1688 건강식품",
                        "url": "https://s.1688.com/selloffer/offer_search.htm?keywords=%E4%BF%9D%E5%81%A5%E5%93%81+%E8%90%A5%E5%85%BB&n=y&netType=1%2C11",
                        "type": "alibaba1688"
                    },
                    {
                        "source": "1688 프로틴",
                        "url": "https://s.1688.com/selloffer/offer_search.htm?keywords=%E8%9B%8B%E7%99%BD%E7%B2%89+%E4%B9%B3%E6%B8%85&n=y&netType=1%2C11",
                        "type": "alibaba1688"
                    },
                    {
                        "source": "1688 비타민",
                        "url": "https://s.1688.com/selloffer/offer_search.htm?keywords=%E7%BB%B4%E7%94%9F%E7%B4%A0+%E9%B1%BC%E6%B2%B9+%E8%86%B3%E9%A3%9F%E8%A1%A5%E5%85%85%E5%89%82&n=y",
                        "type": "alibaba1688"
                    },
                    {
                        "source": "타오바오 웰니스",
                        "url": "https://s.taobao.com/search?q=%E8%BF%9B%E5%8F%A3%E4%BF%9D%E5%81%A5%E5%93%81+%E8%90%A5%E5%85%BB%E8%A1%A5%E5%85%85&imgfile=&js=1&stats_click=search_radio_all",
                        "type": "taobao"
                    }
                ]
            },
            "us": {
                "name": "🇺🇸 미국",
                "sources": ["아마존US", "iHerb", "GNC"],
                "keywords": ["supplements", "wellness", "health", "protein", "yoga mat", "resistance band", "dumbbell", "knee support", "pet vitamin", "dog probiotic"],
                "crawl_urls": [
                    {
                        "source": "iHerb US 스포츠",
                        "url": "https://www.iherb.com/c/sports-nutrition",
                        "type": "iherb"
                    },
                    {
                        "source": "iHerb US 비타민",
                        "url": "https://www.iherb.com/c/vitamins",
                        "type": "iherb"
                    },
                    {
                        "source": "iHerb US 오메가3",
                        "url": "https://www.iherb.com/c/omega-3-fish-oil",
                        "type": "iherb"
                    },
                    {
                        "source": "iHerb US 반려동물",
                        "url": "https://www.iherb.com/c/pet-supplements",
                        "type": "iherb"
                    },
                    {
                        "source": "Amazon Health Best Sellers",
                        "url": "https://www.amazon.com/Best-Sellers-Health-Personal-Care/zgbs/hpc",
                        "type": "amazon"
                    },
                    {
                        "source": "Amazon Sports & Yoga",
                        "url": "https://www.amazon.com/Best-Sellers-Sports-Outdoors/zgbs/sporting-goods",
                        "type": "amazon"
                    },
                    {
                        "source": "Amazon Pet Supplies",
                        "url": "https://www.amazon.com/Best-Sellers-Pet-Supplies/zgbs/pet-supplies",
                        "type": "amazon"
                    }
                ]
            },
            "uk": {
                "name": "🇬🇧 영국",
                "sources": ["아마존UK", "Holland & Barrett", "Boots"],
                "keywords": ["supplements", "vitamins", "wellness", "health"],
                "crawl_urls": [
                    {
                        "source": "Holland & Barrett",
                        "url": "https://www.hollandandbarrett.com/shop/vitamins-supplements/",
                        "type": "holland_barrett"
                    }
                ]
            }
        }

        # 웰니스 카테고리
        self.categories = [
            "영양제/보충제",
            "건강 기능식품",
            "단백질/프로틴",
            "홈 피트니스",
            "수면/회복",
            "스트레스 관리",
            "면역력",
            "장 건강",
            "관절/뼈 건강",
            "피부/콜라겐",
            "다이어트/체중관리",
            "오메가3/피쉬오일",
            "비타민/미네랄",
            "항산화/디톡스"
        ]

    async def init_database(self):
        """PostgreSQL 데이터베이스 초기화"""
        await self.db.init_pool()
        logger.info("✅ PostgreSQL 데이터베이스 초기화 완료")

    async def fetch_html(self, url: str, max_retries: int = 3) -> str:
        """HTML 가져오기 (재시도 로직 포함)"""
        headers = {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,ko;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }

        for attempt in range(max_retries):
            try:
                # SSL 검증 우회 옵션 (일부 사이트용)
                connector = aiohttp.TCPConnector(ssl=False)
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status == 200:
                            html = await response.text()
                            logger.debug(f"✓ 200 OK: {url} (길이: {len(html)} 바이트)")
                            return html
                        elif response.status == 403:
                            logger.warning(f"⚠️ 403 Forbidden: {url} - 재시도 {attempt + 1}/{max_retries}")
                            await asyncio.sleep(2 ** attempt)  # 지수 백오프
                        elif response.status == 429:
                            logger.warning(f"⚠️ 429 Rate Limited: {url} - 대기 후 재시도")
                            await asyncio.sleep(5 * (attempt + 1))
                        elif response.status >= 500:
                            logger.warning(f"⚠️ {response.status} Server Error: {url} - 재시도 {attempt + 1}/{max_retries}")
                            await asyncio.sleep(3)
                        else:
                            logger.warning(f"⚠️ HTTP {response.status}: {url}")
                            await asyncio.sleep(1)
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ Timeout ({30}초 초과): {url} - 재시도 {attempt + 1}/{max_retries}")
                await asyncio.sleep(2)
            except aiohttp.ClientError as e:
                logger.error(f"❌ 네트워크 오류: {url} - {type(e).__name__}: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"❌ 예상치 못한 오류: {url} - {type(e).__name__}: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

        logger.error(f"💥 최종 실패: {url} (모든 재시도 소진)")
        return None

    async def fetch_html_with_browser(self, url: str, wait_time: int = 3) -> Optional[str]:
        """Playwright 헤드리스 브라우저로 HTML 가져오기 (강성 사이트용)"""
        try:
            logger.info(f"   🌐 브라우저 크롤링 시작: {url}")

            async with async_playwright() as p:
                # Chromium 브라우저 실행 (헤드리스 모드)
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-web-security'
                    ]
                )

                # 봇 탐지 회피 설정
                context = await browser.new_context(
                    user_agent=self.ua.random,
                    viewport={'width': 1920, 'height': 1080},
                    locale='ko-KR',
                    timezone_id='Asia/Seoul',
                    extra_http_headers={
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1'
                    }
                )

                # 새 페이지 열기
                page = await context.new_page()

                # JavaScript 비활성화로 위장 (일부 사이트)
                # await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

                # 페이지 로드 (타임아웃 30초)
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=30000)

                    # 추가 대기 (동적 콘텐츠 렌더링)
                    await asyncio.sleep(wait_time)

                    # HTML 소스 가져오기
                    html = await page.content()

                    logger.info(f"   ✅ 브라우저 크롤링 성공: {len(html)} 바이트")

                    return html

                except Exception as e:
                    logger.error(f"   ❌ 페이지 로드 실패: {url} - {type(e).__name__}: {str(e)}")
                    return None

                finally:
                    # 리소스 정리
                    await page.close()
                    await context.close()
                    await browser.close()

        except Exception as e:
            logger.error(f"   ❌ 브라우저 크롤링 실패: {url} - {type(e).__name__}: {str(e)}")
            return None

    async def parse_iherb(self, html: str, source_name: str) -> List[Dict]:
        """iHerb 파싱"""
        products = []
        try:
            soup = BeautifulSoup(html, 'lxml')

            # iHerb 상품 카드 찾기
            product_cards = soup.select('.product-cell, .product-card, div[data-qa="product-card"]')[:50]

            for card in product_cards:
                try:
                    # 상품명
                    title_elem = card.select_one('.product-title, [data-qa="product-title"], h3, h4')
                    title = title_elem.get_text(strip=True) if title_elem else None

                    # 브랜드
                    brand_elem = card.select_one('.product-brand, [data-qa="product-brand"], .brand')
                    brand = brand_elem.get_text(strip=True) if brand_elem else "Unknown"

                    # 가격
                    price_elem = card.select_one('.price, [data-qa="product-price"], .product-price')
                    price = price_elem.get_text(strip=True) if price_elem else "N/A"

                    # URL
                    link_elem = card.select_one('a[href*="/pr/"]')
                    url = urljoin("https://www.iherb.com", link_elem['href']) if link_elem and link_elem.get('href') else None

                    if title and url:
                        products.append({
                            "source": source_name,
                            "product_name": title,
                            "brand": brand,
                            "price": price,
                            "url": url
                        })
                except Exception as e:
                    logger.debug(f"카드 파싱 실패: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"iHerb 파싱 실패: {str(e)}")

        return products

    async def parse_amazon(self, html: str, source_name: str) -> List[Dict]:
        """Amazon 베스트셀러 파싱"""
        products = []
        try:
            soup = BeautifulSoup(html, 'lxml')

            # Amazon 상품 찾기
            items = soup.select('.zg-item-immersion, .a-carousel-card, div[data-asin]')[:50]

            for item in items:
                try:
                    # ASIN 추출
                    asin = item.get('data-asin')

                    # 상품명
                    title_elem = item.select_one('.p13n-sc-truncated, ._cDEzb_p13n-sc-css-line-clamp-3_g3dy1, a img')
                    if title_elem and title_elem.name == 'img':
                        title = title_elem.get('alt', '')
                    else:
                        title = title_elem.get_text(strip=True) if title_elem else None

                    # 가격
                    price_elem = item.select_one('.p13n-sc-price, ._cDEzb_p13n-sc-price_3mJ9Z, .a-price .a-offscreen')
                    price = price_elem.get_text(strip=True) if price_elem else "N/A"

                    # URL
                    link_elem = item.select_one('a[href*="/dp/"]')
                    url = urljoin("https://www.amazon.com", link_elem['href']) if link_elem and link_elem.get('href') else f"https://www.amazon.com/dp/{asin}" if asin else None

                    if title and url:
                        products.append({
                            "source": source_name,
                            "product_name": title[:200],  # 길이 제한
                            "brand": "Amazon",
                            "price": price,
                            "url": url
                        })
                except Exception as e:
                    logger.debug(f"아마존 카드 파싱 실패: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"Amazon 파싱 실패: {str(e)}")

        return products

    async def parse_rakuten(self, html: str, source_name: str) -> List[Dict]:
        """라쿠텐 랭킹 파싱"""
        products = []
        try:
            soup = BeautifulSoup(html, 'lxml')

            # 라쿠텐 랭킹 아이템
            items = soup.select('.ranking_item, .item, div[class*="ranking"]')[:50]

            for item in items:
                try:
                    # 상품명
                    title_elem = item.select_one('.ranking_item_name, .item_name, h3, a')
                    title = title_elem.get_text(strip=True) if title_elem else None

                    # 가격
                    price_elem = item.select_one('.price, .item_price, span[class*="price"]')
                    price = price_elem.get_text(strip=True) if price_elem else "N/A"

                    # URL
                    link_elem = item.select_one('a[href]')
                    url = link_elem['href'] if link_elem and link_elem.get('href') else None

                    if title and url:
                        products.append({
                            "source": source_name,
                            "product_name": title,
                            "brand": "라쿠텐",
                            "price": price,
                            "url": url
                        })
                except Exception as e:
                    logger.debug(f"라쿠텐 카드 파싱 실패: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"라쿠텐 파싱 실패: {str(e)}")

        return products

    async def parse_generic(self, html: str, source_name: str) -> List[Dict]:
        """범용 파서 (다른 사이트용)"""
        products = []
        try:
            soup = BeautifulSoup(html, 'lxml')

            # 일반적인 상품 컨테이너 패턴
            selectors = [
                'div[class*="product"]', 'div[class*="item"]',
                'li[class*="product"]', 'article[class*="product"]',
                'div[data-product]'
            ]

            items = []
            for selector in selectors:
                items = soup.select(selector)[:50]
                if items:
                    break

            for item in items:
                try:
                    # 상품명 (다양한 패턴)
                    title_elem = item.select_one('h2, h3, h4, .title, [class*="title"], [class*="name"]')
                    title = title_elem.get_text(strip=True) if title_elem else None

                    # 가격
                    price_elem = item.select_one('[class*="price"], .price, span[class*="amount"]')
                    price = price_elem.get_text(strip=True) if price_elem else "N/A"

                    # URL
                    link_elem = item.select_one('a[href]')
                    url = link_elem['href'] if link_elem and link_elem.get('href') else None
                    if url and not url.startswith('http'):
                        url = urljoin(source_name, url)

                    if title and url:
                        products.append({
                            "source": source_name,
                            "product_name": title[:200],
                            "brand": "Generic",
                            "price": price,
                            "url": url
                        })
                except Exception as e:
                    logger.debug(f"범용 파싱 실패: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"범용 파싱 실패: {str(e)}")

        return products

    async def parse_1688(self, html: str, source_name: str) -> List[Dict]:
        """1688 파서 (알리바바 도매)"""
        products = []
        try:
            soup = BeautifulSoup(html, 'lxml')

            # 1688 상품 카드 셀렉터
            selectors = [
                'div[class*="offer-card"]', 'div[class*="sm-offer-item"]',
                'div[class*="card-container"]', 'div[data-trackexp]',
                'div[class*="mojar-element-card"]', 'li[class*="offer"]',
            ]

            items = []
            for selector in selectors:
                items = soup.select(selector)[:30]
                if items:
                    break

            # 폴백: a 태그에서 직접 추출
            if not items:
                items = soup.select('a[href*="offer"][class*="title"], a[href*="detail.1688.com"]')[:30]

            for item in items:
                try:
                    title_elem = item.select_one('[class*="title"], h4, h3, [class*="name"], .mojar-element-title')
                    title = title_elem.get_text(strip=True) if title_elem else None

                    # 1688 가격 (¥ 표시)
                    price_elem = item.select_one('[class*="price"], .sm-offer-priceNum, [class*="amount"]')
                    price = '¥' + price_elem.get_text(strip=True).replace('¥', '').strip() if price_elem else "N/A"

                    link_elem = item.select_one('a[href*="detail.1688.com"], a[href*="offer"]')
                    if not link_elem:
                        link_elem = item if item.name == 'a' else item.select_one('a[href]')
                    url = link_elem['href'] if link_elem and link_elem.get('href') else None
                    if url and not url.startswith('http'):
                        url = 'https:' + url if url.startswith('//') else 'https://detail.1688.com' + url

                    if title and len(title) > 3:
                        products.append({
                            "source": source_name,
                            "product_name": title[:200],
                            "brand": "1688",
                            "price": price,
                            "url": url or ""
                        })
                except Exception:
                    continue

            logger.info(f"   1688 파싱: {len(products)}개 상품")

        except Exception as e:
            logger.error(f"1688 파싱 실패: {str(e)}")

        return products

    async def parse_taobao(self, html: str, source_name: str) -> List[Dict]:
        """타오바오 파서"""
        products = []
        try:
            soup = BeautifulSoup(html, 'lxml')

            # 타오바오 검색 결과 셀렉터
            selectors = [
                'div[class*="Content--contentInner"]', 'div[data-widgetid]',
                'div[class*="Card--doubleCard"]', 'div[class*="item"]',
                'a[class*="Card"]',
            ]

            items = []
            for selector in selectors:
                items = soup.select(selector)[:30]
                if items:
                    break

            for item in items:
                try:
                    title_elem = item.select_one('[class*="Title"], [class*="title"], span[class*="name"], h3')
                    title = title_elem.get_text(strip=True) if title_elem else None

                    price_elem = item.select_one('[class*="Price"], [class*="price"], [class*="priceInt"]')
                    price_text = price_elem.get_text(strip=True) if price_elem else ""
                    price = '¥' + price_text.replace('¥', '').strip() if price_text else "N/A"

                    link_elem = item.select_one('a[href*="taobao.com"], a[href*="item.htm"], a[href*="detail"]')
                    if not link_elem:
                        link_elem = item if item.name == 'a' else item.select_one('a[href]')
                    url = link_elem['href'] if link_elem and link_elem.get('href') else None
                    if url and not url.startswith('http'):
                        url = 'https:' + url if url.startswith('//') else 'https://item.taobao.com' + url

                    if title and len(title) > 3:
                        products.append({
                            "source": source_name,
                            "product_name": title[:200],
                            "brand": "타오바오",
                            "price": price,
                            "url": url or ""
                        })
                except Exception:
                    continue

            logger.info(f"   타오바오 파싱: {len(products)}개 상품")

        except Exception as e:
            logger.error(f"타오바오 파싱 실패: {str(e)}")

        return products

    async def fetch_real_trends(self, region_code: str, config: Dict) -> List[Dict]:
        """실제 웹사이트 크롤링으로 트렌드 상품 수집"""
        all_products = []

        crawl_urls = config.get('crawl_urls', [])

        if not crawl_urls:
            logger.warning(f"⚠️ {config['name']}: 크롤링 URL 없음, 스킵")
            return []

        successful_crawls = 0
        failed_crawls = 0

        for crawl_config in crawl_urls:
            source_name = crawl_config['source']
            url = crawl_config['url']
            site_type = crawl_config['type']

            logger.info(f"   🔍 크롤링 시작: {source_name}")
            logger.debug(f"      URL: {url}")
            logger.debug(f"      타입: {site_type}")

            try:
                # === 하이브리드 라우터: 강성 사이트 감지 ===
                # rakuten, jd는 무조건 브라우저 크롤링
                use_browser = site_type in ['rakuten', 'jd', 'holland_barrett', 'alibaba1688', 'taobao']

                html = None

                if use_browser:
                    # 강성 사이트: Playwright 브라우저 사용
                    logger.info(f"   🎯 강성 사이트 감지 → 브라우저 크롤링 모드")
                    html = await self.fetch_html_with_browser(url)
                else:
                    # 일반 사이트: 빠른 aiohttp 사용
                    logger.info(f"   ⚡ 일반 사이트 → 고속 HTTP 모드")
                    html = await self.fetch_html(url)

                    # Fallback: HTTP 실패 시 브라우저로 재시도
                    if not html or len(html) < 1000:
                        logger.warning(f"   ⚠️ HTTP 실패 → 브라우저 Fallback 시도")
                        html = await self.fetch_html_with_browser(url)

                if not html:
                    logger.warning(f"   ⚠️ {source_name}: HTML 없음 (모든 방법 실패)")
                    failed_crawls += 1
                    continue

                # HTML 길이 검증
                if len(html) < 1000:
                    logger.warning(f"   ⚠️ {source_name}: HTML 너무 짧음 ({len(html)} 바이트) - 차단 가능성")
                    failed_crawls += 1
                    continue

                # 사이트 유형별 파서 선택
                if site_type == 'iherb':
                    products = await self.parse_iherb(html, source_name)
                elif site_type == 'amazon':
                    products = await self.parse_amazon(html, source_name)
                elif site_type == 'rakuten':
                    products = await self.parse_rakuten(html, source_name)
                elif site_type == 'alibaba1688':
                    products = await self.parse_1688(html, source_name)
                elif site_type == 'taobao':
                    products = await self.parse_taobao(html, source_name)
                else:
                    products = await self.parse_generic(html, source_name)

                # 데이터 검증
                if not products:
                    logger.warning(f"   ⚠️ {source_name}: 파싱된 상품 0개 (HTML 구조 변경 가능성)")
                    failed_crawls += 1
                    continue

                # 유효한 URL이 있는 상품만 필터링
                valid_products = [p for p in products if p.get('url') and p.get('product_name')]
                if len(valid_products) < len(products):
                    logger.debug(f"   🔧 {source_name}: 불완전한 데이터 제거 ({len(products)} → {len(valid_products)})")

                logger.info(f"   ✅ {source_name}: {len(valid_products)}개 상품 수집 성공")
                all_products.extend(valid_products)
                successful_crawls += 1

                # 크롤링 간격 (로봇 방지)
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"   ❌ {source_name} 크롤링 실패: {type(e).__name__}: {str(e)}")
                failed_crawls += 1
                continue

        # 최종 통계
        logger.info(f"   📊 {config['name']} 크롤링 완료:")
        logger.info(f"      성공: {successful_crawls}개 소스")
        logger.info(f"      실패: {failed_crawls}개 소스")
        logger.info(f"      수집: {len(all_products)}개 상품")

        # 최소 데이터 검증
        if len(all_products) < 5:
            logger.warning(f"   ⚠️ {config['name']}: 수집된 상품이 너무 적음 ({len(all_products)}개) - 크롤링 차단 가능성 높음")

        return all_products

    async def run_daily_scan(self):
        """매일 오전 9시 실행되는 메인 프로세스"""
        logger.info("🔍 Daily Wellness Scan 시작")
        start_time = datetime.now()

        try:
            # 1. 각 지역별 트렌드 수집
            all_products = []
            for region_code, config in self.regions.items():
                logger.info(f"   {config['name']} 트렌드 스캔 중...")
                products = await self.scan_region(region_code, config)
                all_products.extend(products)
                logger.info(f"   → {len(products)}개 상품 발견")

            logger.info(f"📊 총 {len(all_products)}개 상품 분석 시작")

            # 2. AI 분석 및 리스크 필터링
            filtered = await self.analyze_and_filter(all_products)

            # 3. 데이터베이스 저장
            await self.save_to_db(filtered, all_products)

            # 4. 리포트 생성
            report_html = await self.generate_report(filtered, all_products)
            report_summary = await self.generate_summary(filtered)

            # 5. 이메일 발송
            if os.getenv("ENABLE_EMAIL", "true").lower() == "true":
                await self.send_email_report(report_html)

            # 6. 슬랙 알림
            if os.getenv("ENABLE_SLACK", "true").lower() == "true":
                await self.send_slack_notification(report_summary, filtered)

            # 7. 긴급 알림 체크
            await self.check_urgent_alerts(filtered)

            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"✅ Daily Wellness Scan 완료 ({elapsed:.1f}초)")
            logger.info(f"   통과: {len([p for p in filtered if p['risk_assessment']['status']=='통과'])}개")
            logger.info(f"   보류: {len([p for p in filtered if p['risk_assessment']['status']=='보류'])}개")

        except Exception as e:
            logger.error(f"❌ Daily Scan 실패: {str(e)}", exc_info=True)
            await self.send_error_alert(str(e))

    async def scan_region(self, region_code: str, config: Dict) -> List[Dict]:
        """특정 지역의 트렌드 스캔 (실시간 크롤링 + AI 필터링 파이프라인)"""

        logger.info(f"   🚀 {config['name']} 파이프라인 시작: 크롤링 → AI 필터링")

        # ===== 1단계: 실제 웹사이트 크롤링 =====
        raw_products = await self.fetch_real_trends(region_code, config)

        if not raw_products:
            logger.warning(f"   ⚠️ {config['name']}: 크롤링된 데이터 없음")
            return []

        logger.info(f"   📊 1차 수집 완료: {len(raw_products)}개 → AI 분석 시작")

        # ===== 2단계: Claude AI에게 실제 데이터를 컨텍스트로 주입 =====
        # 크롤링된 상품 목록을 텍스트로 포매팅
        product_list_text = "\n".join([
            f"{idx}. {p['product_name']} | {p['brand']} | {p['price']} | {p['source']} | {p['url']}"
            for idx, p in enumerate(raw_products[:100], 1)  # 최대 100개만 전달
        ])

        prompt = f"""당신은 {config['name']} 지역의 웰니스/헬스케어 소싱 전문가입니다.

**중요: 아래는 방금 실제 웹사이트에서 크롤링한 "진짜 상품 데이터"입니다.**

=== 크롤링된 실제 상품 목록 ({len(raw_products)}개) ===
{product_list_text}
===================================================

**임무**:
위 실제 크롤링 데이터에서 "한국 시장 진입 가능성이 높은 최대 100개 상품"을 선별해주세요.
(크롤링된 데이터가 100개 미만이면 전체 선별 가능)

**선별 기준**:
1. ✅ 통과 가능: 일반 영양제, 프로틴, 비타민, 콜라겐 등
2. ❌ 제외 대상:
   - 의료기기 표방 (혈압/혈당 조절, 질병 치료 등)
   - 금지 성분 함유 (마황, CBD, THC, 요힘빈 등)
   - 유명 브랜드 복제품 의심
   - 한국 건기식 인증 불가능한 성분

**카테고리 분류**:
{chr(10).join(f"- {cat}" for cat in self.categories)}

**출력 형식** (JSON 배열, 반드시 위 크롤링 목록에서만 선택):
[
  {{
    "region": "{region_code}",
    "source": "크롤링된 소스명 그대로 사용",
    "product_name": "크롤링된 상품명 (한국어 번역 가능)",
    "brand": "크롤링된 브랜드명",
    "price": "크롤링된 가격 그대로",
    "category": "카테고리 (위 목록에서 선택)",
    "trend_score": 0-100점 (인기도 + 한국 수요 평가),
    "korea_demand": "높음/중간/낮음",
    "description": "상품 특징 2-3줄",
    "url": "크롤링된 URL 그대로 사용"
  }}
]

**필수 준수 사항**:
- 절대 상품을 지어내지 마세요. 위 크롤링 목록에 있는 것만 사용.
- URL은 크롤링된 실제 URL을 그대로 포함.
- 최소 8개, 최대 15개 선별.
- 반드시 유효한 JSON 형식으로만 응답.

JSON만 출력하세요:"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text

            # 마크다운 코드 블록 제거
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            # JSON 파싱
            products = json.loads(content.strip())

            # 리스트가 아니면 빈 배열 반환
            if not isinstance(products, list):
                logger.warning(f"   ⚠️ AI 응답이 리스트가 아님 ({region_code})")
                return []

            logger.info(f"   ✅ AI 필터링 완료: {len(raw_products)}개 → {len(products)}개 선별")
            return products

        except json.JSONDecodeError as e:
            logger.error(f"   ❌ JSON 파싱 실패 ({region_code}): {str(e)}")
            logger.error(f"   응답 내용 (처음 300자): {content[:300] if 'content' in locals() else '응답 없음'}")
            return []
        except Exception as e:
            logger.error(f"   ❌ AI 필터링 실패 ({region_code}): {str(e)}")
            return []

    async def analyze_and_filter(self, products: List[Dict]) -> List[Dict]:
        """리스크 필터링 및 분석"""
        filtered = []

        for product in products:
            try:
                # 각 상품에 대해 리스크 평가
                risk = await self.check_wellness_risks(product)
                product['risk_assessment'] = risk

                # 통과 또는 보류 상품만 포함
                if risk['status'] in ['통과', '보류']:
                    filtered.append(product)

            except Exception as e:
                logger.error(f"상품 분석 실패: {product.get('product_name')}: {str(e)}")

        # 트렌드 점수 순 정렬
        filtered.sort(key=lambda x: x.get('trend_score', 0), reverse=True)

        return filtered[:10]  # 상위 10개

    async def check_wellness_risks(self, product: Dict) -> Dict:
        """웰니스 특화 리스크 체크"""

        prompt = f"""상품 리스크 평가:

**상품명**: {product.get('product_name')}
**브랜드**: {product.get('brand')}
**카테고리**: {product.get('category')}
**설명**: {product.get('description')}

**한국 구매대행 가능성 판단**:

1. **의료기기 오인 표방**
   - "혈압 강하", "혈당 조절", "질병 치료" 등 의학적 효능 표방
   - "완치", "예방", "재생" 등 의약품 오인 문구
   → 위험도: low/medium/high

2. **건강기능식품 인증**
   - 한국 식약처 건기식 인증 가능 성분인지
   - 통관 시 문제 가능성
   → 위험도: low/medium/high

3. **금지 성분**
   - 마황, 요힘빈, CBD, THC 등 규제 성분
   - 스테로이드 등 금지 물질
   → 위험도: low/medium/high

4. **지재권**
   - 유명 브랜드 복제품 여부
   - 특허 침해 가능성
   → 위험도: low/medium/high

**판단 결과** (JSON):
{{
  "status": "통과/보류/제외",
  "risks": {{
    "의료기기": {{"level": "low/medium/high", "reason": "이유"}},
    "건기식인증": {{"level": "low/medium/high", "reason": "이유"}},
    "금지성분": {{"level": "low/medium/high", "reason": "이유"}},
    "지재권": {{"level": "low/medium/high", "reason": "이유"}}
  }},
  "confirmation_needed": ["확인 필요 항목들"],
  "vendor_questions_kr": "벤더에게 물어볼 질문 (한국어)",
  "vendor_questions_cn": "벤더에게 물어볼 질문 (중국어)",
  "next_step": "마진 산정/벤더 확인/제외 처리",
  "overall_reason": "종합 판단 이유 (1-2줄)"
}}

**판단 기준**:
- high가 1개 이상 → 제외
- medium이 2개 이상 → 보류
- 나머지 → 통과

반드시 유효한 JSON으로만 응답하세요."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text

            # 마크다운 코드 블록 제거
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            risk_data = json.loads(content.strip())
            return risk_data

        except Exception as e:
            logger.error(f"리스크 체크 실패: {str(e)}")
            if 'content' in locals():
                logger.error(f"응답 내용 (처음 200자): {content[:200]}")
            return {
                "status": "제외",
                "risks": {},
                "confirmation_needed": [],
                "next_step": "오류로 인한 제외",
                "overall_reason": f"분석 오류: {str(e)}"
            }

    async def save_to_db(self, filtered_products: List[Dict], all_products: List[Dict]):
        """PostgreSQL에 저장"""
        today = datetime.now().strftime('%Y-%m-%d')

        # 통과/보류 상품만 저장
        products_to_save = []
        for product in filtered_products:
            products_to_save.append({
                'region': product.get('region'),
                'source': product.get('source'),
                'product_name': product.get('product_name'),
                'brand': product.get('brand'),
                'price': product.get('price'),
                'category': product.get('category'),
                'trend_score': product.get('trend_score'),
                'korea_demand': product.get('korea_demand'),
                'risk_status': product['risk_assessment']['status'],
                'description': product.get('description'),
                'url': product.get('url')
            })

        await self.db.save_products(products_to_save, today)

        # 일일 통계 저장
        passed = len([p for p in filtered_products if p['risk_assessment']['status'] == '통과'])
        pending = len([p for p in filtered_products if p['risk_assessment']['status'] == '보류'])
        rejected = len(all_products) - len(filtered_products)

        # 가장 많이 등장한 카테고리
        categories = [p.get('category') for p in filtered_products if p.get('category')]
        top_category = max(set(categories), key=categories.count) if categories else "없음"

        await self.db.save_daily_stats({
            'date': today,
            'total_analyzed': len(all_products),
            'passed': passed,
            'pending': pending,
            'rejected': rejected,
            'top_category': top_category
        })

        logger.info(f"💾 PostgreSQL 저장 완료: {len(filtered_products)}개 상품")

    async def generate_report(self, products: List[Dict], all_products: List[Dict]) -> str:
        """HTML 리포트 생성"""

        today = datetime.now().strftime('%Y년 %m월 %d일 (%a)')

        # 통계
        passed = [p for p in products if p['risk_assessment']['status'] == '통과']
        pending = [p for p in products if p['risk_assessment']['status'] == '보류']
        rejected_count = len(all_products) - len(products)

        # 상품 카드 HTML 생성
        product_cards = ""
        for idx, product in enumerate(products[:5], 1):
            risk = product['risk_assessment']
            status_emoji = "✅" if risk['status'] == '통과' else "⚠️"
            status_color = "#28a745" if risk['status'] == '통과' else "#ffc107"

            product_cards += f"""
            <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid {status_color};">
                <h3 style="margin-top: 0;">{idx}️⃣ {status_emoji} [{risk['status']}] {product.get('product_name')}</h3>
                <p><strong>출처:</strong> {self.regions[product['region']]['name']} - {product.get('source')}</p>
                <p><strong>브랜드:</strong> {product.get('brand')} | <strong>가격:</strong> {product.get('price')}</p>
                <p><strong>카테고리:</strong> {product.get('category')} | <strong>트렌드 점수:</strong> ⭐ {product.get('trend_score')}/100</p>
                <p><strong>한국 수요:</strong> {product.get('korea_demand')}</p>
                <p><strong>설명:</strong> {product.get('description')}</p>
                <p><strong>종합 판단:</strong> {risk.get('overall_reason')}</p>
                {f"<p><strong>확인 필요:</strong> {', '.join(risk.get('confirmation_needed', []))}</p>" if risk.get('confirmation_needed') else ""}
                <p><strong>다음 단계:</strong> {risk.get('next_step')}</p>
            </div>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 30px; }}
                .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 30px; }}
                .stat-card {{ background: white; padding: 20px; border-radius: 10px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .stat-number {{ font-size: 32px; font-weight: bold; color: #667eea; }}
                .stat-label {{ font-size: 14px; color: #666; margin-top: 5px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 Fortimove Daily Wellness Report</h1>
                <p>{today}</p>
            </div>

            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{len(all_products)}</div>
                    <div class="stat-label">분석한 상품</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="color: #28a745;">{len(passed)}</div>
                    <div class="stat-label">✅ 통과</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="color: #ffc107;">{len(pending)}</div>
                    <div class="stat-label">⚠️ 보류</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="color: #dc3545;">{rejected_count}</div>
                    <div class="stat-label">❌ 제외</div>
                </div>
            </div>

            <h2 style="color: #667eea;">🎯 오늘의 추천 상품 TOP 5</h2>
            {product_cards}

            <div style="background: white; padding: 20px; border-radius: 10px; margin-top: 30px; text-align: center; color: #666;">
                <p>Generated by Fortimove AI Sourcing Agent</p>
                <p>Next report: {(datetime.now() + timedelta(days=1)).strftime('%Y년 %m월 %d일')} 10:00 AM</p>
            </div>
        </body>
        </html>
        """

        return html

    async def generate_summary(self, products: List[Dict]) -> str:
        """슬랙용 요약 생성"""
        passed = [p for p in products if p['risk_assessment']['status'] == '통과']
        pending = [p for p in products if p['risk_assessment']['status'] == '보류']

        summary = f"""📅 *Daily Wellness Report* - {datetime.now().strftime('%Y-%m-%d')}

📊 *오늘의 통계*
• 통과: {len(passed)}개 ✅
• 보류: {len(pending)}개 ⚠️

🎯 *TOP 3 추천 상품*
"""
        for idx, product in enumerate(products[:3], 1):
            summary += f"{idx}. {product.get('product_name')} ({self.regions[product['region']]['name']})\n"

        return summary

    async def send_email_report(self, html_content: str):
        """이메일 리포트 발송"""
        try:
            # 환경 변수 읽기 (Docker Compose에서 전달된 값 우선)
            email_from = os.getenv("EMAIL_SENDER") or os.getenv("SCOUT_EMAIL_SENDER") or os.getenv("EMAIL_FROM", "sourcing@fortimove.com")
            email_to = os.getenv("EMAIL_RECIPIENTS") or os.getenv("SCOUT_EMAIL_RECIPIENTS") or os.getenv("EMAIL_TO", "team@fortimove.com")
            smtp_user = os.getenv("EMAIL_SENDER") or os.getenv("SCOUT_EMAIL_SENDER") or os.getenv("SMTP_USER")
            smtp_pass = os.getenv("EMAIL_PASSWORD") or os.getenv("SCOUT_EMAIL_PASSWORD") or os.getenv("SMTP_PASS")

            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Fortimove Daily Wellness Report - {datetime.now().strftime('%Y-%m-%d')}"
            msg['From'] = email_from
            msg['To'] = email_to

            msg.attach(MIMEText(html_content, 'html', 'utf-8'))

            # SMTP 발송
            smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
            smtp_port = int(os.getenv("SMTP_PORT", "587"))

            if smtp_user and smtp_pass:
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                    server.send_message(msg)

                logger.info("📧 이메일 리포트 발송 완료")
            else:
                logger.warning("⚠️ SMTP 설정 없음 - 이메일 발송 스킵")

        except Exception as e:
            logger.error(f"이메일 발송 실패: {str(e)}")

    async def send_slack_notification(self, summary: str, products: List[Dict]):
        """슬랙 알림"""
        webhook_url = os.getenv("SLACK_WEBHOOK_URL") or os.getenv("SCOUT_SLACK_WEBHOOK_URL")

        if not webhook_url or webhook_url == "https://hooks.slack.com/services/YOUR/WEBHOOK/URL":
            logger.warning("⚠️ 슬랙 웹훅 URL 없음 - 슬랙 알림 스킵")
            return

        try:
            # 긴급 아이템 체크
            hot_items = [p for p in products if p.get('trend_score', 0) >= 90]

            if hot_items:
                summary += f"\n\n🔥 *긴급 알림*: 트렌드 점수 90+ 아이템 {len(hot_items)}개 발견!"

            payload = {
                "text": summary,
                "username": "Fortimove Scout Bot",
                "icon_emoji": ":chart_with_upwards_trend:"
            }

            response = requests.post(webhook_url, json=payload)

            if response.status_code == 200:
                logger.info("📢 슬랙 알림 발송 완료")
            else:
                logger.error(f"슬랙 알림 실패: {response.status_code} - {response.text}")
                logger.error(f"Webhook URL: {webhook_url[:50]}...")

        except Exception as e:
            logger.error(f"슬랙 알림 오류: {str(e)}")

    async def check_urgent_alerts(self, products: List[Dict]):
        """긴급 알림 체크 (고득점 아이템)"""
        hot_items = [p for p in products if p.get('trend_score', 0) >= 90]

        if hot_items:
            logger.info(f"🔥 긴급 알림: 핫 아이템 {len(hot_items)}개 발견!")

            # 별도 슬랙 채널에 긴급 알림
            urgent_webhook = os.getenv("SLACK_URGENT_WEBHOOK_URL") or os.getenv("SCOUT_SLACK_URGENT_WEBHOOK_URL")
            if urgent_webhook:
                for item in hot_items:
                    payload = {
                        "text": f"🔥🔥🔥 *핫 아이템 발견!*\n\n*{item.get('product_name')}*\n트렌드 점수: {item.get('trend_score')}/100\n{self.regions[item['region']]['name']} - {item.get('source')}\n\n즉시 검토 필요!",
                        "username": "Urgent Alert Bot",
                        "icon_emoji": ":fire:"
                    }
                    requests.post(urgent_webhook, json=payload)

    async def send_error_alert(self, error_message: str):
        """에러 알림"""
        logger.error(f"🚨 에러 알림: {error_message}")

        webhook_url = os.getenv("SLACK_WEBHOOK_URL") or os.getenv("SCOUT_SLACK_WEBHOOK_URL")
        if webhook_url:
            payload = {
                "text": f"🚨 *Daily Scout 에러 발생*\n\n```{error_message}```\n\n시스템 점검 필요!",
                "username": "Error Alert Bot",
                "icon_emoji": ":rotating_light:"
            }
            requests.post(webhook_url, json=payload)

    async def get_trend_analysis(self, days=30) -> Dict:
        """장기 트렌드 분석 (30일 데이터)"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # 최근 30일 데이터
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # 카테고리별 통계
        c.execute('''
            SELECT category, COUNT(*) as count
            FROM products
            WHERE date >= ? AND risk_status = '통과'
            GROUP BY category
            ORDER BY count DESC
            LIMIT 5
        ''', (start_date,))

        top_categories = dict(c.fetchall())

        # 지역별 통계
        c.execute('''
            SELECT region, COUNT(*) as count
            FROM products
            WHERE date >= ? AND risk_status = '통과'
            GROUP BY region
            ORDER BY count DESC
        ''', (start_date,))

        region_stats = dict(c.fetchall())

        conn.close()

        return {
            "top_categories": top_categories,
            "region_stats": region_stats,
            "period_days": days
        }


async def init_and_run():
    """초기화 및 실행"""
    scout = DailyWellnessScout()
    await scout.init_database()  # PostgreSQL 초기화

    # 즉시 테스트 실행 (옵션)
    if os.getenv("RUN_IMMEDIATELY", "false").lower() == "true":
        logger.info("🚀 즉시 테스트 실행 시작...")
        await scout.run_daily_scan()

    return scout

def start_scheduler():
    """스케줄러 시작"""
    scout = asyncio.run(init_and_run())

    # 매일 오전 9시 실행
    schedule_time = os.getenv("SCHEDULE_TIME", "09:00")
    schedule.every().day.at(schedule_time).do(
        lambda: asyncio.run(scout.run_daily_scan())
    )

    logger.info("=" * 60)
    logger.info("📅 Daily Wellness Scout 시작 (PostgreSQL)")
    logger.info(f"⏰ 매일 {schedule_time}에 자동 실행")
    logger.info(f"🗄️  데이터베이스: PostgreSQL (db:5432/fortimove_images)")
    logger.info("=" * 60)

    # 스케줄러 루프
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    start_scheduler()
