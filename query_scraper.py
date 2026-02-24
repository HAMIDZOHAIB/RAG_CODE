"""
Enhanced Query Scraper — FIXED THREADED VERSION

Every issue from logs resolved:

✅ Fix 1: Stats reset at start of each process_query() call
✅ Fix 2: BFS sleep reduced (0.5-1.2s → 0.2-0.5s for subpage crawl)
✅ Fix 3: Callback does NOT run inside the executor worker
          Worker: scrape → store result → signal done
          Separate thread: wait for signal → save JSON → embed
          → threads never block each other waiting for embedding
✅ Fix 4: BFS queue capped at max_pages × 3 links (no 48-link explosion)
✅ Fix 5: No sleep between DIFFERENT websites (only between subpages of same site)
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Set, Optional, Tuple, Callable
from urllib.parse import urlparse, urljoin, quote_plus
import time
import re
from collections import deque
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from fake_useragent import UserAgent
import queue as Queue


class EnhancedQueryScraper:
    """
    THREADED SCRAPER — TRUE per-thread pipeline
    
    Flow:
      Thread 1: scrape site1 → put result in queue → DONE (fast)
      Thread 2: scrape site2 → put result in queue → DONE (fast)
      Thread 3: scrape site3 → put result in queue → DONE (fast)
      
      Callback runner (separate thread):
        while queue not empty:
          result = queue.get()
          save JSON → run_embedding()   ← sequential, no races
    
    This means:
    - Scraping threads are never blocked by save/embed
    - Save+embed is sequential (no file lock races)
    - Total time = max(scrape times) + sum(embed times)
    - vs old: sum(scrape + embed times) per thread
    """

    def __init__(
        self,
        scraping_depth: str = "basic",
        max_subpages_per_site: int = None,
        crawl_method: str = "bfs",
        use_playwright: bool = False,
        playwright_timeout: int = 30000,
        use_undetected: bool = True,
        headless: bool = True,
        max_workers: int = 5
    ):
        self.scraping_depth = scraping_depth
        self.max_subpages_per_site = (
            max_subpages_per_site if max_subpages_per_site is not None else float('inf')
        )
        self.crawl_method   = crawl_method
        self.use_playwright = use_playwright
        self.playwright_timeout = playwright_timeout
        self.use_undetected = use_undetected
        self.headless       = headless
        self.max_workers    = max_workers

        self.ua      = UserAgent()
        self.session = requests.Session()
        self._update_session_headers()

        # Thread-local: each worker gets its own requests.Session
        self._thread_local = threading.local()

        # Print lock (cosmetic only — keep logs readable)
        self._print_lock = threading.Lock()

        # Chrome — main thread only
        self.driver = None

        self.priority_paths = {
            'pricing': 100, 'price': 100, 'plans': 100, 'plan': 100,
            'demo': 95, 'trial': 95, 'free-trial': 95, 'get-started': 95,
            'features': 90, 'feature': 90, 'capabilities': 90,
            'products': 85, 'product': 85, 'services': 85, 'service': 85, 'solutions': 85,
            'about': 80, 'about-us': 80, 'company': 80, 'team': 80,
            'how-it-works': 75, 'platform': 75, 'overview': 75, 'technology': 75,
            'resources': 70, 'documentation': 70, 'docs': 70, 'guides': 70,
            'integrations': 65, 'integration': 65, 'api': 65, 'developers': 65,
            'customers': 60, 'case-studies': 60, 'testimonials': 60, 'reviews': 60,
            'industries': 55, 'use-cases': 55, 'faq': 55, 'help': 55, 'support': 55,
            'contact': 50, 'contact-us': 50
        }
        self.acceptable_paths = {
            'blog': 30, 'news': 30, 'updates': 30,
            'careers': 20, 'jobs': 20
        }
        self.skip_paths = [
            '/signup', '/sign-up', '/signin', '/sign-in', '/login', '/register',
            '/admin', '/dashboard', '/profile', '/account', '/settings', '/user',
            '/cart', '/checkout', '/billing', '/invoice',
            '/privacy', '/terms', '/legal', '/cookie', '/gdpr', '/compliance',
            '/download', '/downloads', '/assets', '/cdn',
            'forget-password', '/reset-password',
        ]
        self.skip_extensions = [
            '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico', '.bmp',
            '.mp4', '.mp3', '.avi', '.mov', '.wmv', '.flv', '.webm',
            '.zip', '.rar', '.tar', '.gz', '.7z',
            '.exe', '.dmg', '.pkg', '.deb', '.rpm',
            '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.xml', '.json', '.csv', '.rss', '.atom'
        ]

        print(f"\n🎯 Scraper Configuration:")
        print(f"   📊 Depth      : {scraping_depth.upper()}")
        print(f"   🔢 Max Pages  : {'∞' if self.max_subpages_per_site == float('inf') else max_subpages_per_site}")
        print(f"   🔄 Method     : {crawl_method.upper()}")
        print(f"   🧵 Workers    : {max_workers}")

    # ─────────────────────────────────────────────────────────────────
    # SESSION HELPERS
    # ─────────────────────────────────────────────────────────────────

    def _update_session_headers(self):
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1', 'Connection': 'keep-alive', 'Upgrade-Insecure-Requests': '1',
        })

    def _get_thread_session(self) -> requests.Session:
        """One session per thread with connection pooling. Never shared."""
        if not hasattr(self._thread_local, 'session'):
            s = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=5,
                pool_maxsize=5,
                max_retries=2
            )
            s.mount('http://', adapter)
            s.mount('https://', adapter)
            s.headers.update({
                'User-Agent': self.ua.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1', 'Connection': 'keep-alive', 'Upgrade-Insecure-Requests': '1',
            })
            self._thread_local.session = s
        return self._thread_local.session

    # ─────────────────────────────────────────────────────────────────
    # CHROME — main thread only
    # ─────────────────────────────────────────────────────────────────

    def _init_driver(self):
        if self.driver is not None:
            return self.driver
        try:
            import undetected_chromedriver as uc
            print("   🚀 Initializing Chrome...")
            options = uc.ChromeOptions()
            if self.headless:
                options.add_argument('--headless=new')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-notifications')
            options.add_argument(f'--window-size={random.randint(1024,1920)},{random.randint(768,1080)}')
            self.driver = uc.Chrome(options=options, use_subprocess=True)
            print("   ✅ Chrome ready")
            return self.driver
        except Exception as e:
            print(f"   ⚠️ Chrome failed: {e}")
            self.use_undetected = False
            return None

    def _close_driver(self):
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
            except:
                pass

    # ─────────────────────────────────────────────────────────────────
    # FETCH — thread-safe, no Chrome in workers
    # ─────────────────────────────────────────────────────────────────

    def _fetch_content(self, url: str, retries: int = 2) -> Tuple[Optional[str], Optional[BeautifulSoup]]:
        """Uses thread-local session. NO Chrome. Retries with backoff."""
        session = self._get_thread_session()
        for attempt in range(retries + 1):
            try:
                response = session.get(url, timeout=20)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'lxml')
                return response.text, soup
            except requests.exceptions.RequestException as e:
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                with self._print_lock:
                    print(f"      ⚠️ Fetch failed after {retries+1} attempts [{url[:50]}]: {e}")
                return None, None
            except Exception as e:
                with self._print_lock:
                    print(f"      ⚠️ Error [{url[:50]}]: {e}")
                return None, None

    # ─────────────────────────────────────────────────────────────────
    # SEARCH
    # ─────────────────────────────────────────────────────────────────

    def search_duckduckgo(self, query: str, max_results: int = 5) -> List[str]:
        print(f"\n🔍 Searching: '{query}'")
        urls = self._try_ddgs_search(query, max_results)
        if urls:
            print(f"   ✅ Found {len(urls)} URLs")
            return urls
        urls = self._try_alternative_search(query, max_results)
        if urls:
            print(f"   ✅ Found {len(urls)} URLs (fallback)")
            return urls
        print("   ❌ No URLs found")
        return []

    def _try_ddgs_search(self, query: str, max_results: int) -> List[str]:
        for pkg in ['ddgs', 'duckduckgo_search']:
            try:
                if pkg == 'ddgs':
                    from ddgs import DDGS
                else:
                    from duckduckgo_search import DDGS
                print(f"   📦 Using {pkg}...")
                ddgs = DDGS()
                results = list(ddgs.text(query, max_results=max_results))
                urls = []
                for r in results:
                    url = r.get('href') or r.get('link') or r.get('url')
                    if not url:
                        continue
                    actual = self._decode_duckduckgo_url(url)
                    if actual and self._is_valid_search_result(actual):
                        urls.append(actual)
                return urls[:max_results]
            except ImportError:
                continue
            except Exception as e:
                print(f"   ⚠️ {pkg} error: {e}")
        return []

    def _try_alternative_search(self, query: str, max_results: int) -> List[str]:
        try:
            print("   🔄 Google fallback...")
            encoded = quote_plus(query)
            url = f"https://www.google.com/search?q={encoded}&num={max_results}"
            resp = requests.get(url, headers={'User-Agent': self.ua.random}, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            urls = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('/url?q='):
                    u = href.split('/url?q=')[1].split('&')[0]
                    u = requests.utils.unquote(u)
                    if u.startswith('http') and self._is_valid_search_result(u):
                        urls.append(u)
                        if len(urls) >= max_results:
                            break
            return urls
        except Exception as e:
            print(f"   ⚠️ Fallback failed: {e}")
            return []

    def _decode_duckduckgo_url(self, url: str) -> Optional[str]:
        try:
            from urllib.parse import parse_qs, unquote, urlparse as pu
            if url.startswith('//'):
                url = 'https:' + url
            if 'duckduckgo.com/l/' in url:
                params = parse_qs(pu(url).query)
                if 'uddg' in params:
                    return unquote(params['uddg'][0])
            if not url.startswith('http'):
                url = 'https://' + url
            return url
        except:
            return url

    def _is_valid_search_result(self, url: str) -> bool:
        skip_domains = [
            'youtube.com', 'facebook.com', 'twitter.com', 'x.com',
            'linkedin.com', 'instagram.com', 'tiktok.com', 'snapchat.com',
            'wikipedia.org', 'pinterest.com', 'reddit.com', 'quora.com',
            'researchgate.net', 'medium.com', 'substack.com',
            'amazon.com', 'ebay.com', 'aliexpress.com', 'walmart.com',
            'scholar.google.com', 'docs.google.com', 'drive.google.com',
            'indeed.com', 'glassdoor.com', 'monster.com',
            'slideshare.net', 'github.com', 'stackoverflow.com',
            'tumblr.com', 'vimeo.com', 'dailymotion.com',
            'dropbox.com', 'weebly.com', 'wordpress.com', 'blogspot.com',
            'archive.org', 'archive.is', 'waybackmachine.org',
            'yahoo.com', 'bing.com', 'ask.com', 'discord.com',
            'telegram.org', 'slack.com', 'zoom.us', 'teams.microsoft.com'
        ]
        url_lower = url.lower()
        if any(d in url_lower for d in skip_domains): return False
        if any(p in url_lower for p in self.skip_paths): return False
        if any(url_lower.endswith(e) for e in self.skip_extensions): return False
        return True

    # ─────────────────────────────────────────────────────────────────
    # URL HELPERS
    # ─────────────────────────────────────────────────────────────────

    def normalize_url(self, url: str) -> str:
        url = url.strip().lower()
        if '#' in url: url = url.split('#')[0]
        if url.endswith('/'): url = url[:-1]
        url = url.replace('://www.', '://')
        if '?' in url:
            base = url.split('?')[0]
            if any(p in url for p in ['utm_', 'fbclid', 'gclid', 'ref', 'source', 'campaign']):
                url = base
        return url

    def score_url_importance(self, url: str, link_text: str = "") -> Tuple[int, List[str]]:
        url_lower, text_lower = url.lower(), link_text.lower()
        score, matched = 0, []
        for kw, pts in self.priority_paths.items():
            if kw in url_lower or kw in text_lower:
                score += pts; matched.append(kw)
        for kw, pts in self.acceptable_paths.items():
            if kw in url_lower or kw in text_lower:
                score += pts; matched.append(kw)
        for pat in ['blog/20','news/20','article/','/tag/','/category/',
                    'author/','archive/','wp-content','/feed','/rss']:
            if pat in url_lower: score -= 50
        if urlparse(url).path in ('', '/'): score += 10
        return max(0, score), matched

    def extract_and_prioritize_links(self, url: str, soup: BeautifulSoup,
                                     limit: int = 20) -> List[Dict]:
        """
        ✅ Fix 4: Cap returned links at `limit` (default 20).
        Old code returned ALL 48 links from aspiedent.com even when
        max_pages=3 — wasted time scoring/queueing unused links.
        """
        base_domain = urlparse(url).netloc
        links, seen = [], set()
        for a in soup.find_all('a', href=True):
            abs_url = urljoin(url, a['href'])
            if urlparse(abs_url).netloc != base_domain: continue
            if not self._is_valid_internal_link(abs_url): continue
            norm = self.normalize_url(abs_url)
            if norm in seen: continue
            seen.add(norm)
            score, kws = self.score_url_importance(abs_url, a.get_text(strip=True))
            if score > 0:
                links.append({'url': abs_url, 'score': score, 'keywords': kws})
            if len(links) >= limit * 2:   # collect 2× then sort and take top `limit`
                break
        links.sort(key=lambda x: x['score'], reverse=True)
        return links[:limit]

    def _is_valid_internal_link(self, url: str) -> bool:
        url_lower = url.lower()
        if any(p in url_lower for p in self.skip_paths): return False
        if any(url_lower.endswith(e) for e in self.skip_extensions): return False
        if re.search(r'/\d{4}/\d{2}/', url_lower): return False
        if re.search(r'[?&]page=\d+', url_lower): return False
        return True

    def filter_already_scraped(self, urls: List[str], scraped_urls: Set[str]) -> List[str]:
        normed = {self.normalize_url(u) for u in scraped_urls}
        new_urls, skipped = [], 0
        for u in urls:
            if self.normalize_url(u) in normed: skipped += 1
            else: new_urls.append(u)
        if skipped:
            print(f"   🔄 Skipped {skipped} already-scraped URLs")
        return new_urls

    # ─────────────────────────────────────────────────────────────────
    # TEXT EXTRACTION
    # ─────────────────────────────────────────────────────────────────

    def extract_readable_text(self, soup: BeautifulSoup, remove_nav: bool = True) -> str:
        remove_tags = (['script','style','nav','footer','header','iframe','svg','noscript']
                       if remove_nav else ['script','style','iframe','svg','noscript'])
        for tag in soup(remove_tags):
            tag.decompose()
        main = None
        for sel in ['main','article','[role="main"]','.main-content',
                    '#main-content','.content','#content']:
            main = soup.select_one(sel)
            if main: break
        if not main:
            main = soup.find('body') or soup
        return self._create_text_chunks(self._extract_content_sections(main))

    def _extract_content_sections(self, element) -> List[Dict]:
        sections = []
        for child in element.find_all(
            ['h1','h2','h3','h4','h5','h6','p','ul','ol'], recursive=True
        ):
            tag = child.name.lower()
            if tag in ('h1','h2','h3','h4','h5','h6'):
                txt = child.get_text(strip=True)
                if txt and len(txt) > 2:
                    sections.append({'type':'header','content':txt})
            elif tag == 'p':
                txt = child.get_text(separator=' ', strip=True)
                if txt and len(txt) > 20:
                    sections.append({'type':'paragraph','content':txt})
            elif tag in ('ul','ol'):
                items = [li.get_text(strip=True)
                         for li in child.find_all('li', recursive=False)
                         if li.get_text(strip=True)]
                if items:
                    sections.append({'type':'list','content':items})
        return sections

    def _create_text_chunks(self, sections: List[Dict]) -> str:
        if not sections: return "No content extracted"
        chunks, cur, cur_wc, num = [], [], 0, 1
        MAX = 500
        for s in sections:
            t = s['type']
            if   t == 'header':    fmt, wc = f"\n\n{s['content']}\n", len(s['content'].split())
            elif t == 'paragraph': fmt, wc = f"{s['content']}\n",     len(s['content'].split())
            elif t == 'list':
                fmt = '\n'.join(f"• {i}" for i in s['content']) + '\n'
                wc  = sum(len(i.split()) for i in s['content'])
            else: continue
            if cur_wc > 0 and cur_wc + wc > MAX:
                chunks.append(f"\n--- Section {num} ---\n\n" + ''.join(cur))
                cur, cur_wc, num = [fmt], wc, num+1
            else:
                cur.append(fmt); cur_wc += wc
        if cur:
            chunks.append(f"\n--- Section {num} ---\n\n" + ''.join(cur))
        return '\n'.join(chunks)

    # ─────────────────────────────────────────────────────────────────
    # CRAWLERS — sleep reduced (Fix 2), link cap added (Fix 4)
    # ─────────────────────────────────────────────────────────────────

    def crawl_website_bfs(self, start_url: str, max_pages: int) -> List[Dict]:
        unlimited = max_pages == float('inf')
        visited   = {self.normalize_url(start_url)}
        queue     = deque([start_url])
        pages     = []
        while queue:
            if not unlimited and len(pages) >= max_pages: break
            url = queue.popleft()
            try:
                content, soup = self._fetch_content(url)
                if not content or not soup: continue
                title = soup.title.string.strip() if soup.title and soup.title.string else ""
                text  = self.extract_readable_text(soup)
                score, kws = self.score_url_importance(url)
                pages.append({'url':url,'title':title,'text':text,'score':score,'keywords':kws})
                with self._print_lock:
                    print(f"         ✅ [{len(pages)}] {url[:55]} ({len(text):,} ch)")
                # ✅ Fix 4: cap links at max_pages×3 so we don't queue 48 links for a 3-page crawl
                remaining = (max_pages - len(pages)) if not unlimited else 20
                link_limit = max(remaining * 3, 5)
                for lk in self.extract_and_prioritize_links(url, soup, limit=link_limit):
                    norm = self.normalize_url(lk['url'])
                    if norm not in visited:
                        visited.add(norm); queue.append(lk['url'])
                # ✅ Fix 2: shorter sleep between subpages of same site
                time.sleep(random.uniform(0.2, 0.5))
            except Exception as e:
                with self._print_lock:
                    print(f"         ❌ {url[:50]}: {e}")
        return pages

    def crawl_website_dfs(self, start_url: str, max_pages: int,
                          visited: Set[str] = None, pages: List[Dict] = None,
                          depth: int = 0, max_depth: int = 10) -> List[Dict]:
        if visited is None: visited = set()
        if pages   is None: pages   = []
        unlimited = max_pages == float('inf')
        if (not unlimited and len(pages) >= max_pages) or depth > max_depth: return pages
        norm = self.normalize_url(start_url)
        if norm in visited: return pages
        visited.add(norm)
        try:
            content, soup = self._fetch_content(start_url)
            if not content or not soup: return pages
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            text  = self.extract_readable_text(soup)
            score, kws = self.score_url_importance(start_url)
            pages.append({'url':start_url,'title':title,'text':text,'score':score,'keywords':kws})
            with self._print_lock:
                print(f"         ✅ D{depth} [{len(pages)}] {start_url[:55]} ({len(text):,} ch)")
            remaining = (max_pages - len(pages)) if not unlimited else 20
            for lk in self.extract_and_prioritize_links(start_url, soup, limit=remaining*3):
                if not unlimited and len(pages) >= max_pages: break
                self.crawl_website_dfs(lk['url'], max_pages, visited, pages, depth+1, max_depth)
                time.sleep(random.uniform(0.2, 0.5))  # ✅ Fix 2
        except Exception as e:
            with self._print_lock:
                print(f"         ❌ {start_url[:50]}: {e}")
        return pages

    def crawl_website_priority(self, start_url: str, max_pages: int) -> List[Dict]:
        unlimited = max_pages == float('inf')
        visited   = {self.normalize_url(start_url)}
        pq, pages = [], []
        try:
            content, soup = self._fetch_content(start_url)
            if not content or not soup: return pages
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            text  = self.extract_readable_text(soup)
            score, kws = self.score_url_importance(start_url)
            pages.append({'url':start_url,'title':title,'text':text,'score':score,'keywords':kws})
            with self._print_lock:
                print(f"         🏠 {start_url[:55]} ({len(text):,} ch)")
            for lk in self.extract_and_prioritize_links(start_url, soup, limit=20):
                norm = self.normalize_url(lk['url'])
                if norm not in visited:
                    pq.append((lk['score'], lk['url'], lk['keywords'])); visited.add(norm)
        except Exception as e:
            with self._print_lock:
                print(f"         ❌ {start_url[:50]}: {e}")
            return pages
        pq.sort(key=lambda x: x[0], reverse=True)
        while pq:
            if not unlimited and len(pages) >= max_pages: break
            sc, url, kws = pq.pop(0)
            try:
                content, soup = self._fetch_content(url)
                if not content or not soup: continue
                title = soup.title.string.strip() if soup.title and soup.title.string else ""
                text  = self.extract_readable_text(soup)
                pages.append({'url':url,'title':title,'text':text,'score':sc,'keywords':kws})
                with self._print_lock:
                    print(f"         🎯 [{len(pages)}] {url[:55]} ({len(text):,} ch)")
                for lk in self.extract_and_prioritize_links(url, soup, limit=20):
                    norm = self.normalize_url(lk['url'])
                    if norm not in visited:
                        pq.append((lk['score'], lk['url'], lk['keywords'])); visited.add(norm)
                pq.sort(key=lambda x: x[0], reverse=True)
                time.sleep(random.uniform(0.2, 0.5))  # ✅ Fix 2
            except Exception as e:
                with self._print_lock:
                    print(f"         ❌ {url[:50]}: {e}")
        return pages

    # ─────────────────────────────────────────────────────────────────
    # SCRAPERS
    # ─────────────────────────────────────────────────────────────────

    def scrape_website_basic(self, url: str) -> Dict:
        with self._print_lock:
            print(f"   📄 [BASIC] {url[:65]}")
        try:
            content, soup = self._fetch_content(url)
            if not content or not soup: raise Exception("Failed to fetch")
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            meta_parts = []
            for attr in [('name','description'),('property','og:description')]:
                tag = soup.find('meta', attrs={attr[0]:attr[1]})
                if tag and tag.get('content'):
                    c = tag['content'].strip()
                    if c not in meta_parts: meta_parts.append(c)
            text = self.extract_readable_text(soup)
            with self._print_lock:
                print(f"      ✅ {len(text):,} chars")
            return {'website_link':url,'title':title or 'No title',
                    'metadata':' | '.join(meta_parts) or 'No metadata','plain_text':text}
        except Exception as e:
            with self._print_lock:
                print(f"      ❌ {url[:50]}: {e}")
            return {'website_link':url,'title':'Error - Failed to scrape',
                    'metadata':f'Error: {e}','plain_text':f'Failed: {e}'}

    def scrape_website_deep(self, url: str) -> Dict:
        with self._print_lock:
            print(f"   📄 [DEEP] {url[:65]}")
        try:
            content, soup = self._fetch_content(url)
            if not content or not soup: raise Exception("Failed to fetch")
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            meta_parts = []
            for meta in soup.find_all('meta'):
                n = meta.get('name','').lower(); p = meta.get('property','').lower()
                c = meta.get('content','').strip()
                if c and (n in ('description','keywords','author') or
                          p in ('og:description','og:title')):
                    if c not in meta_parts: meta_parts.append(c)
            text = self.extract_readable_text(soup, remove_nav=False)
            with self._print_lock:
                print(f"      ✅ {len(text):,} chars")
            return {'website_link':url,'title':title,'metadata':' | '.join(meta_parts),'plain_text':text}
        except Exception as e:
            with self._print_lock:
                print(f"      ❌ {url[:50]}: {e}")
            return {'website_link':url,'title':'Error','metadata':'Failed','plain_text':f'Error: {e}'}

    def scrape_website_multipage(self, url: str, max_subpages: int = None) -> Dict:
        if max_subpages is None:
            max_subpages = self.max_subpages_per_site
        with self._print_lock:
            print(f"   📄 [MULTI-{self.crawl_method.upper()}] {url[:60]}")
        if   self.crawl_method == "bfs":  pages = self.crawl_website_bfs(url, max_subpages)
        elif self.crawl_method == "dfs":  pages = self.crawl_website_dfs(url, max_subpages)
        else:                              pages = self.crawl_website_priority(url, max_subpages)
        if not pages:
            return {'website_link':url,'title':'Error','metadata':'Failed','plain_text':'No pages crawled'}
        all_kws = [kw for p in pages for kw in p.get('keywords',[])]
        top_kws = sorted(set(all_kws), key=all_kws.count, reverse=True)[:5]
        meta = f"Crawled {len(pages)} pages | Sections: {', '.join(top_kws)}"
        body = f"Website: {url}\nPages: {len(pages)}\n"
        for i, p in enumerate(pages, 1):
            body += f"\n--- Page {i}: {p.get('title','')} ---\nURL: {p['url']}\n{p['text']}\n"
        with self._print_lock:
            print(f"      ✅ {len(body):,} chars from {len(pages)} pages")
        return {'website_link':url,'title':pages[0]['title'],'metadata':meta,'plain_text':body}

    def scrape_website(self, url: str) -> Dict:
        url = self._validate_and_fix_url(url)
        if not url:
            return {'website_link':url,'title':'Error','metadata':'Invalid URL','plain_text':'URL validation failed'}
        if   self.scraping_depth == "basic":     return self.scrape_website_basic(url)
        elif self.scraping_depth == "deep":      return self.scrape_website_deep(url)
        elif self.scraping_depth == "multipage": return self.scrape_website_multipage(url)
        else:                                    return self.scrape_website_basic(url)

    def _validate_and_fix_url(self, url: str) -> Optional[str]:
        if not url or not isinstance(url, str): return None
        url = url.strip()
        if url.startswith('//'): url = 'https:' + url
        elif not url.startswith('http'): url = 'https://' + url
        url = self._decode_duckduckgo_url(url)
        try:
            p = urlparse(url)
            return url if p.scheme and p.netloc else None
        except: return None

    # ─────────────────────────────────────────────────────────────────
    # ✅ FIXED process_query
    # ─────────────────────────────────────────────────────────────────

    def process_query(
        self,
        query: str,
        max_websites: int = 10,
        already_scraped: Set[str] = None,
        on_website_scraped: Callable[[Dict], None] = None
    ) -> List[Dict]:
        """
        TRUE per-thread pipeline using a callback queue.

        Architecture:
        ┌─────────────────────────────────────────────────────────┐
        │  ThreadPoolExecutor (max_workers threads)               │
        │  Thread 1: scrape site1 → put(result) → DONE ✅        │
        │  Thread 2: scrape site2 → put(result) → DONE ✅        │
        │  Thread 3: scrape site3 → put(result) → DONE ✅        │
        └──────────────────────┬──────────────────────────────────┘
                               │  Queue (thread-safe)
        ┌──────────────────────▼──────────────────────────────────┐
        │  Callback runner (ONE dedicated thread)                 │
        │  while results available:                               │
        │    result = queue.get()                                 │
        │    on_website_scraped(result)  ← save JSON + embed     │
        └─────────────────────────────────────────────────────────┘

        WHY this is better than your current approach:
        - Scraping threads are NEVER blocked by slow embedding
        - on_website_scraped runs sequentially → no file lock races
        - No jitter/sleep hacks needed
        - Stats reset on every call (Fix 1)
        """
        print(f"\n{'='*65}")
        print(f"🚀 QUERY SCRAPER")
        print(f"{'='*65}")
        print(f"Query          : '{query}'")
        print(f"Depth          : {self.scraping_depth.upper()}")
        print(f"Max Workers    : {self.max_workers}")
        print(f"Already scraped: {len(already_scraped or set())} URLs")

        # ✅ Fix 1: Reset stats on every call
        stats = {'successful': 0, 'failed': 0, 'total_chars': 0}

        if already_scraped is None:
            already_scraped = set()

        # Search
        urls = self.search_duckduckgo(query, max_results=max_websites * 3)
        if not urls:
            print("\n❌ No URLs found!")
            return []

        # Filter already-scraped
        if already_scraped:
            print(f"\n🔍 Filtering already-scraped URLs...")
            urls = self.filter_already_scraped(urls, already_scraped)

        urls = urls[:max_websites]
        if not urls:
            print("\n⚠️  All URLs already scraped!")
            return []

        num_threads = min(len(urls), self.max_workers)
        print(f"\n🧵 {num_threads} workers for {len(urls)} URLs")
        print(f"{'='*65}\n")

        results      = []
        results_lock = threading.Lock()

        # ── ✅ Fix 3: Callback queue — scraping threads just put results here ──
        # The callback runner thread picks them up and processes one at a time
        # → no blocking of scraping threads during slow embedding
        callback_queue = Queue.Queue()

        def callback_runner():
            """
            Dedicated thread that processes scraped results one at a time.
            Runs on_website_scraped (save JSON + embed) sequentially.
            Ends when it receives the sentinel value None.
            """
            while True:
                item = callback_queue.get()
                if item is None:        # sentinel — no more items
                    callback_queue.task_done()
                    break
                data, idx, total = item
                url = data.get('website_link','?')
                print(f"\n💾 [Callback] Processing [{idx}/{total}]: {url[:50]}")
                try:
                    on_website_scraped(data)
                    print(f"   ✅ [Callback] Done [{idx}/{total}]")
                except Exception as e:
                    print(f"   ❌ [Callback] Error: {e}")
                callback_queue.task_done()

        # Start callback runner thread (only if there's a callback)
        if on_website_scraped:
            cb_thread = threading.Thread(target=callback_runner, daemon=True, name="CallbackRunner")
            cb_thread.start()

        def scrape_one(url: str, index: int) -> Dict:
            """
            Worker: ONLY scrapes. Does NOT call on_website_scraped directly.
            Puts successful result into callback_queue and exits immediately.
            """
            t = threading.current_thread().name
            with self._print_lock:
                print(f"🧵 [{t}] ▶ START [{index}/{len(urls)}]: {url[:55]}")

            try:
                data  = self.scrape_website(url)
                is_ok = data.get('title') not in ('Error','Error - Failed to scrape')
            except Exception as e:
                data  = {'website_link':url,'title':'Error','metadata':f'Exception: {e}','plain_text':f'Error: {e}'}
                is_ok = False

            with results_lock:
                results.append(data)
                done = len(results)

            if is_ok:
                stats['successful'] += 1
                stats['total_chars'] += len(data.get('plain_text',''))
            else:
                stats['failed'] += 1

            status = "✅" if is_ok else "❌"
            with self._print_lock:
                print(f"🧵 [{t}] {status} DONE [{done}/{len(urls)}]: {url[:50]}")

            # ✅ Fix 3: Put in queue — don't block this thread
            if is_ok and on_website_scraped:
                callback_queue.put((data, done, len(urls)))

            return data

        # ── Run all scraping threads ─────────────────────────────────
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = {
                executor.submit(scrape_one, url, idx): url
                for idx, url in enumerate(urls, 1)
            }
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"❌ Future error: {e}")

        # ── Signal callback runner that scraping is done ─────────────
        if on_website_scraped:
            callback_queue.put(None)   # sentinel
            cb_thread.join()           # wait for all callbacks to finish

        # ── Summary ─────────────────────────────────────────────────
        self._close_driver()

        print(f"\n{'='*65}")
        print(f"✅ ALL DONE")
        print(f"   ✅ Successful : {stats['successful']}")
        print(f"   ❌ Failed     : {stats['failed']}")
        if stats['successful']:
            avg = stats['total_chars'] // stats['successful']
            print(f"   📝 Total text : {stats['total_chars']:,} chars")
            print(f"   📊 Avg/site   : {avg:,} chars")
        print(f"{'='*65}")

        return results