"""
Enhanced Query Scraper - FIXED UNDETECTED VERSION
✅ Fixed duckduckgo_search import issue
✅ Improved fallback mechanisms
"""

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from typing import List, Dict, Set, Optional, Tuple
from urllib.parse import urlparse, urljoin, quote_plus
import time
import re
from collections import Counter, deque
import asyncio
import random
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from fake_useragent import UserAgent
import json


class EnhancedQueryScraper:
    """
    UNDETECTED SCRAPER with FIXES
    """
    
    def __init__(
        self, 
        scraping_depth: str = "basic", 
        max_subpages_per_site: int = None,
        crawl_method: str = "bfs",
        use_playwright: bool = False,
        playwright_timeout: int = 30000,
        use_undetected: bool = True,
        headless: bool = True
    ):
        self.scraping_depth = scraping_depth
        self.max_subpages_per_site = max_subpages_per_site if max_subpages_per_site is not None else float('inf')
        self.crawl_method = crawl_method
        self.use_playwright = use_playwright
        self.playwright_timeout = playwright_timeout
        self.use_undetected = use_undetected
        self.headless = headless
        
        # Initialize User-Agent generator
        self.ua = UserAgent()
        
        # Session for requests (with rotating user agents)
        self.session = requests.Session()
        self._update_session_headers()
        
        # Chrome driver (will be initialized lazily)
        self.driver = None
        
        # Keep your original lists
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
            '/download', '/downloads', '/assets', '/cdn','forget-password', '/reset-password',
        ]
        
        self.skip_extensions = [
            '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico', '.bmp',
            '.mp4', '.mp3', '.avi', '.mov', '.wmv', '.flv', '.webm',
            '.zip', '.rar', '.tar', '.gz', '.7z',
            '.exe', '.dmg', '.pkg', '.deb', '.rpm',
            '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.xml', '.json', '.csv', '.rss', '.atom'
        ]
        
        print(f"\n🎯 UNDETECTED Scraping Configuration:")
        print(f"   📊 Depth: {scraping_depth.upper()}")
        print(f"   🔢 Max Subpages: {'UNLIMITED' if self.max_subpages_per_site == float('inf') else max_subpages_per_site}")
        print(f"   🔄 Crawl Method: {crawl_method.upper()}")
        print(f"   🚀 Undetected Chrome: {'ENABLED' if use_undetected else 'DISABLED'}")
        print(f"   👻 Headless: {headless}")
    
    def _update_session_headers(self):
        """Update session headers with new user agent"""
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def _init_driver(self):
        """Initialize undetected Chrome driver (lazy loading)"""
        if self.driver is not None:
            return self.driver
        
        print("   🚀 Initializing undetected Chrome...")
        try:
            options = uc.ChromeOptions()
            
            if self.headless:
                options.add_argument('--headless=new')
            
            # Anti-detection settings
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--no-sandbox')
            options.add_argument(f'--user-agent={self.ua.random}')
            
            # Random window size
            width = random.randint(1024, 1920)
            height = random.randint(768, 1080)
            options.add_argument(f'--window-size={width},{height}')
            
            # Disable automation flags
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Add more evasion arguments
            options.add_argument('--disable-web-security')
            options.add_argument('--allow-running-insecure-content')
            options.add_argument('--disable-notifications')
            
            self.driver = uc.Chrome(
                options=options,
                use_subprocess=True
            )
            
            # Evasion scripts
            scripts = [
                """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                """,
                """
                window.chrome = { runtime: {} };
                """,
                """
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                """,
                """
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                """,
                """
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                """
            ]
            
            for script in scripts:
                self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": script
                })
            
            print("   ✅ Undetected Chrome initialized")
            return self.driver
            
        except Exception as e:
            print(f"   ⚠️ Undetected Chrome init failed: {e}")
            self.use_undetected = False
            return None
    
    def _close_driver(self):
        """Close Chrome driver"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
            except:
                pass
    
    def _fetch_with_chrome(self, url: str) -> Optional[str]:
        """Fetch page content using undetected Chrome"""
        if not self.use_undetected:
            return None
        
        driver = self._init_driver()
        if not driver:
            return None
        
        try:
            print(f"      🌐 Chrome fetching: {url[:60]}...")
            
            # Rotate user agent
            new_ua = self.ua.random
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": new_ua
            })
            
            # Navigate to URL
            driver.get(url)
            
            # Random wait for page load
            wait_time = random.uniform(3, 6)
            time.sleep(wait_time)
            
            # Simulate human behavior
            self._simulate_human_behavior(driver)
            
            # Wait for content with timeout
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except:
                pass
            
            # Get page source
            content = driver.page_source
            
            return content
            
        except Exception as e:
            print(f"      ⚠️ Chrome fetch error: {e}")
            return None
        finally:
            # Don't quit driver here - keep it for reuse
            pass
    
    def _simulate_human_behavior(self, driver):
        """Simulate human-like interactions"""
        try:
            actions = ActionChains(driver)
            
            # Random mouse movements
            for _ in range(random.randint(2, 5)):
                x_offset = random.randint(-100, 100)
                y_offset = random.randint(-100, 100)
                actions.move_by_offset(x_offset, y_offset)
                actions.perform()
                time.sleep(random.uniform(0.1, 0.4))
            
            # Random scroll
            if random.random() > 0.3:
                scroll_amount = random.randint(300, 1200)
                driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                time.sleep(random.uniform(0.5, 2.0))
            
            # Sometimes scroll back
            if random.random() > 0.6:
                driver.execute_script("window.scrollBy(0, -400);")
                time.sleep(random.uniform(0.3, 1.0))
                
        except:
            pass
    
    def _fetch_content(self, url: str) -> Optional[Tuple[str, BeautifulSoup]]:
        """
        Unified content fetching with fallback
        """
        # Update session headers
        self._update_session_headers()
        
        # Try Chrome first if enabled
        if self.use_undetected:
            chrome_content = self._fetch_with_chrome(url)
            if chrome_content:
                try:
                    soup = BeautifulSoup(chrome_content, 'lxml')
                    return chrome_content, soup
                except:
                    pass
        
        # Fallback to requests
        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            return response.text, soup
            
        except Exception as e:
            print(f"      ⚠️ Requests fetch error: {e}")
            return None, None
    
    def search_duckduckgo(self, query: str, max_results: int = 5) -> List[str]:
        """Search DuckDuckGo and return URLs - FIXED VERSION"""
        print(f"\n🔍 Searching for: '{query}'")
        
        urls = []
        
        # Try different search methods
        urls = self._try_ddgs_search(query, max_results)
        
        if urls:
            print(f"   ✅ Found {len(urls)} URLs using ddgs")
            return urls
        
        # Try alternative methods
        urls = self._try_alternative_search(query, max_results)
        
        if urls:
            print(f"   ✅ Found {len(urls)} URLs using alternative method")
            return urls
        
        print(f"   ❌ No URLs found for query: {query}")
        return []
    
    def _try_ddgs_search(self, query: str, max_results: int) -> List[str]:
        """Try ddgs package (new name)"""
        try:
            # Try new package name first
            from ddgs import DDGS
            print("   📦 Using ddgs package (new)...")
            
            ddgs = DDGS()
            results = list(ddgs.text(query, max_results=max_results))
            
            urls = []
            for result in results:
                url = result.get('href') or result.get('link') or result.get('url')
                if not url:
                    continue
                
                actual_url = self._decode_duckduckgo_url(url)
                
                if actual_url and self._is_valid_search_result(actual_url):
                    urls.append(actual_url)
            
            return urls[:max_results]
            
        except ImportError:
            try:
                # Try old package name
                from duckduckgo_search import DDGS
                print("   📦 Using duckduckgo_search package (old)...")
                
                ddgs = DDGS()
                results = list(ddgs.text(query, max_results=max_results))
                
                urls = []
                for result in results:
                    url = result.get('href') or result.get('link') or result.get('url')
                    if not url:
                        continue
                    
                    actual_url = self._decode_duckduckgo_url(url)
                    
                    if actual_url and self._is_valid_search_result(actual_url):
                        urls.append(actual_url)
                
                return urls[:max_results]
                
            except ImportError:
                print("   ⚠️  Neither ddgs nor duckduckgo_search installed")
                return []
            except Exception as e:
                print(f"   ⚠️  Old package error: {e}")
                return []
        except Exception as e:
            print(f"   ⚠️  New package error: {e}")
            return []
    
    def _try_alternative_search(self, query: str, max_results: int) -> List[str]:
        """Try alternative search methods"""
        try:
            # Method 1: Direct Google scraping (simplified)
            print("   🔄 Trying alternative search method...")
            
            encoded_query = quote_plus(query)
            search_url = f"https://www.google.com/search?q={encoded_query}&num={max_results}"
            
            headers = {
                'User-Agent': self.ua.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            response = requests.get(search_url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            urls = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                
                # Extract Google result URLs
                if href.startswith('/url?q='):
                    url = href.split('/url?q=')[1].split('&')[0]
                    url = requests.utils.unquote(url)
                    
                    if url.startswith('http') and self._is_valid_search_result(url):
                        urls.append(url)
                        
                        if len(urls) >= max_results:
                            break
            
            return urls
            
        except Exception as e:
            print(f"   ⚠️  Alternative search failed: {e}")
            return []
    
    def _search_duckduckgo_html(self, query: str, max_results: int) -> List[str]:
        """Fallback HTML scraping"""
        try:
            from urllib.parse import parse_qs, unquote
            
            encoded_query = quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            links = soup.find_all('a', class_='result__a')
            
            urls = []
            for link in links[:max_results]:
                href = link.get('href')
                if not href:
                    continue
                
                actual_url = self._decode_duckduckgo_url(href)
                
                if actual_url and self._is_valid_search_result(actual_url):
                    urls.append(actual_url)
            
            return urls
        except Exception as e:
            return []
    
    def _decode_duckduckgo_url(self, url: str) -> Optional[str]:
        """Decode DuckDuckGo redirect URLs"""
        try:
            from urllib.parse import parse_qs, unquote, urlparse as parse_url
            
            if url.startswith('//'):
                url = 'https:' + url
            
            if 'duckduckgo.com/l/' in url:
                parsed = parse_url(url)
                params = parse_qs(parsed.query)
                
                if 'uddg' in params:
                    actual_url = unquote(params['uddg'][0])
                    return actual_url
            
            if not url.startswith('http'):
                url = 'https://' + url
            
            return url
            
        except Exception as e:
            return url  # Return original if decode fails
    
    def _is_valid_search_result(self, url: str) -> bool:
        """Check if search result URL should be scraped"""
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
            'yahoo.com', 'bing.com', 'ask.com', 'discord.com', 'telegram.org',
            'slack.com', 'zoom.us', 'teams.microsoft.com'
        ]
        
        url_lower = url.lower()
        
        # Skip social media and common platforms
        if any(domain in url_lower for domain in skip_domains):
            return False
        
        # Skip auth/account pages
        if any(path in url_lower for path in self.skip_paths):
            return False
        
        # Skip file downloads
        if any(url_lower.endswith(ext) for ext in self.skip_extensions):
            return False
        
        return True
    
    # KEEP ALL YOUR ORIGINAL FUNCTIONS FROM HERE
    # Only the search function was modified above
    
    def normalize_url(self, url: str) -> str:
        """Normalize URL for comparison"""
        url = url.strip().lower()
        
        if '#' in url:
            url = url.split('#')[0]
        
        if url.endswith('/'):
            url = url[:-1]
        
        url = url.replace('://www.', '://')
        
        if '?' in url:
            base_url = url.split('?')[0]
            tracking_params = ['utm_', 'fbclid', 'gclid', 'ref', 'source', 'campaign']
            if any(param in url for param in tracking_params):
                url = base_url
        
        return url
    
    def extract_readable_text(self, soup: BeautifulSoup, remove_nav: bool = True) -> str:
        """Extract readable text"""
        if remove_nav:
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'iframe', 'svg', 'noscript']):
                tag.decompose()
        else:
            for tag in soup(['script', 'style', 'iframe', 'svg', 'noscript']):
                tag.decompose()
        
        main_content = None
        for selector in ['main', 'article', '[role="main"]', '.main-content', '#main-content', '.content', '#content']:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        if not main_content:
            main_content = soup.find('body')
        
        if not main_content:
            main_content = soup
        
        sections = self._extract_content_sections(main_content)
        chunks = self._create_text_chunks(sections)
        
        return chunks
    
    def _extract_content_sections(self, element) -> List[Dict]:
        """Extract content sections"""
        sections = []
        current_header = None
        
        for child in element.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'div', 'section'], recursive=True):
            tag_name = child.name.lower()
            
            if tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                header_text = child.get_text(strip=True)
                if header_text and len(header_text) > 2:
                    current_header = header_text
                    sections.append({
                        'type': 'header',
                        'content': header_text,
                        'header': current_header
                    })
            
            elif tag_name == 'p':
                para_text = child.get_text(separator=' ', strip=True)
                if para_text and len(para_text) > 20:
                    sections.append({
                        'type': 'paragraph',
                        'content': para_text,
                        'header': current_header
                    })
            
            elif tag_name in ['ul', 'ol']:
                list_items = []
                for li in child.find_all('li', recursive=False):
                    li_text = li.get_text(strip=True)
                    if li_text:
                        list_items.append(li_text)
                
                if list_items:
                    sections.append({
                        'type': 'list',
                        'content': list_items,
                        'header': current_header
                    })
        
        return sections
    
    def _create_text_chunks(self, sections: List[Dict]) -> str:
        """Create text chunks"""
        if not sections:
            return "No content extracted"
        
        chunks = []
        current_chunk = []
        current_word_count = 0
        chunk_number = 1
        
        MAX_WORDS_PER_CHUNK = 500
        
        for section in sections:
            section_type = section['type']
            content = section['content']
            
            if section_type == 'header':
                formatted = f"\n\n{content}\n"
                word_count = len(content.split())
                
            elif section_type == 'paragraph':
                formatted = f"{content}\n"
                word_count = len(content.split())
                
            elif section_type == 'list':
                list_text = '\n'.join([f"• {item}" for item in content])
                formatted = f"{list_text}\n"
                word_count = sum(len(item.split()) for item in content)
            
            else:
                continue
            
            if current_word_count > 0 and (current_word_count + word_count > MAX_WORDS_PER_CHUNK):
                chunk_header = f"\n--- Section {chunk_number} ---\n\n"
                chunks.append(chunk_header + ''.join(current_chunk))
                
                current_chunk = [formatted]
                current_word_count = word_count
                chunk_number += 1
            else:
                current_chunk.append(formatted)
                current_word_count += word_count
        
        if current_chunk:
            chunk_header = f"\n--- Section {chunk_number} ---\n\n"
            chunks.append(chunk_header + ''.join(current_chunk))
        
        return '\n'.join(chunks)
    
    def score_url_importance(self, url: str, link_text: str = "") -> Tuple[int, List[str]]:
        """Score URL importance"""
        url_lower = url.lower()
        text_lower = link_text.lower()
        
        score = 0
        matched_keywords = []
        
        for keyword, points in self.priority_paths.items():
            if keyword in url_lower or keyword in text_lower:
                score += points
                matched_keywords.append(keyword)
        
        for keyword, points in self.acceptable_paths.items():
            if keyword in url_lower or keyword in text_lower:
                score += points
                matched_keywords.append(keyword)
        
        unwanted_patterns = [
            'blog/20', 'news/20', 'article/', '/tag/', '/category/',
            'author/', 'archive/', 'wp-content', '/feed', '/rss'
        ]
        for pattern in unwanted_patterns:
            if pattern in url_lower:
                score -= 50
        
        parsed = urlparse(url)
        if parsed.path in ['', '/']:
            score += 10
        
        return max(0, score), matched_keywords
    
    def extract_and_prioritize_links(self, url: str, soup: BeautifulSoup) -> List[Dict]:
        """Extract and prioritize links"""
        base_domain = urlparse(url).netloc
        all_links = []
        seen_normalized = set()
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            absolute_url = urljoin(url, href)
            
            link_domain = urlparse(absolute_url).netloc
            if link_domain != base_domain:
                continue
            
            if not self._is_valid_internal_link(absolute_url):
                continue
            
            normalized = self.normalize_url(absolute_url)
            if normalized in seen_normalized:
                continue
            seen_normalized.add(normalized)
            
            link_text = link.get_text(strip=True)
            
            score, keywords = self.score_url_importance(absolute_url, link_text)
            
            if score > 0:
                all_links.append({
                    'url': absolute_url,
                    'text': link_text,
                    'score': score,
                    'keywords': keywords
                })
        
        all_links.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"      🔗 Found {len(all_links)} internal links")
        
        return all_links
    
    def _is_valid_internal_link(self, url: str) -> bool:
        """Check if internal link is valid"""
        url_lower = url.lower()
        
        if any(path in url_lower for path in self.skip_paths):
            return False
        
        if any(url_lower.endswith(ext) for ext in self.skip_extensions):
            return False
        
        if re.search(r'/\d{4}/\d{2}/', url_lower):
            return False
        
        if re.search(r'[?&]page=\d+', url_lower):
            return False
        
        return True
    
    def crawl_website_bfs(self, start_url: str, max_pages: int) -> List[Dict]:
        """BFS crawling"""
        print(f"\n      🔄 BFS Crawling: {start_url}")
        
        unlimited = max_pages == float('inf')
        if unlimited:
            print(f"      ♾️  UNLIMITED MODE")
        
        base_domain = urlparse(start_url).netloc
        visited = set()
        queue = deque([start_url])
        scraped_pages = []
        
        normalized_start = self.normalize_url(start_url)
        visited.add(normalized_start)
        
        while queue:
            if not unlimited and len(scraped_pages) >= max_pages:
                break
                
            current_url = queue.popleft()
            
            progress = f"[{len(scraped_pages)+1}]" if unlimited else f"[{len(scraped_pages)+1}/{max_pages}]"
            print(f"      📄 {progress} {current_url[:60]}...", end=' ')
            
            try:
                content, soup = self._fetch_content(current_url)
                if not content or not soup:
                    print(f"❌ Failed")
                    continue
                
                title = soup.title.string.strip() if soup.title and soup.title.string else ""
                plain_text = self.extract_readable_text(soup, remove_nav=True)
                
                score, keywords = self.score_url_importance(current_url)
                
                scraped_pages.append({
                    'url': current_url,
                    'title': title,
                    'text': plain_text,
                    'score': score,
                    'keywords': keywords
                })
                
                print(f"✅ {len(plain_text):,} chars")
                
                priority_links = self.extract_and_prioritize_links(current_url, soup)
                
                for link_info in priority_links:
                    link_url = link_info['url']
                    normalized_link = self.normalize_url(link_url)
                    
                    if normalized_link not in visited:
                        visited.add(normalized_link)
                        queue.append(link_url)
                
                time.sleep(random.uniform(1, 2))
                
            except Exception as e:
                print(f"❌ {str(e)[:30]}")
                continue
        
        print(f"\n      ✅ BFS crawled {len(scraped_pages)} pages")
        return scraped_pages
    
    def crawl_website_dfs(self, start_url: str, max_pages: int, visited: Set[str] = None, scraped_pages: List[Dict] = None, depth: int = 0, max_depth: int = 10) -> List[Dict]:
        """DFS crawling"""
        if visited is None:
            visited = set()
            print(f"\n      🔄 DFS Crawling: {start_url}")
        
        if scraped_pages is None:
            scraped_pages = []
        
        unlimited = max_pages == float('inf')
        
        if (not unlimited and len(scraped_pages) >= max_pages) or depth > max_depth:
            return scraped_pages
        
        normalized_url = self.normalize_url(start_url)
        if normalized_url in visited:
            return scraped_pages
        
        visited.add(normalized_url)
        
        indent = "   " * depth
        progress = f"[{len(scraped_pages)+1}]" if unlimited else f"[{len(scraped_pages)+1}/{max_pages}]"
        print(f"      {indent}📄 {progress} Depth {depth}: {start_url[:50]}...", end=' ')
        
        try:
            content, soup = self._fetch_content(start_url)
            if not content or not soup:
                print(f"❌ Failed")
                return scraped_pages
            
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            plain_text = self.extract_readable_text(soup, remove_nav=True)
            
            score, keywords = self.score_url_importance(start_url)
            
            scraped_pages.append({
                'url': start_url,
                'title': title,
                'text': plain_text,
                'score': score,
                'keywords': keywords
            })
            
            print(f"✅ {len(plain_text):,} chars")
            
            priority_links = self.extract_and_prioritize_links(start_url, soup)
            
            for link_info in priority_links:
                if not unlimited and len(scraped_pages) >= max_pages:
                    break
                
                link_url = link_info['url']
                self.crawl_website_dfs(link_url, max_pages, visited, scraped_pages, depth + 1, max_depth)
                time.sleep(random.uniform(0.5, 1.5))
            
        except Exception as e:
            print(f"❌ {str(e)[:30]}")
        
        if depth == 0:
            print(f"\n      ✅ DFS crawled {len(scraped_pages)} pages")
        
        return scraped_pages
    
    def crawl_website_priority(self, start_url: str, max_pages: int) -> List[Dict]:
        """Priority-based crawling"""
        print(f"\n      🎯 Priority Crawling: {start_url}")
        
        unlimited = max_pages == float('inf')
        if unlimited:
            print(f"      ♾️  UNLIMITED MODE")
        
        base_domain = urlparse(start_url).netloc
        visited = set()
        priority_queue = []
        scraped_pages = []
        
        normalized_start = self.normalize_url(start_url)
        visited.add(normalized_start)
        
        progress = "[1]" if unlimited else f"[1/{max_pages}]"
        print(f"      🏠 {progress} Homepage: {start_url[:60]}...", end=' ')
        
        try:
            content, soup = self._fetch_content(start_url)
            if not content or not soup:
                print(f"❌ Failed")
                return scraped_pages
            
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            plain_text = self.extract_readable_text(soup, remove_nav=True)
            score, keywords = self.score_url_importance(start_url)
            
            scraped_pages.append({
                'url': start_url,
                'title': title,
                'text': plain_text,
                'score': score,
                'keywords': keywords
            })
            
            print(f"✅ {len(plain_text):,} chars")
            
            priority_links = self.extract_and_prioritize_links(start_url, soup)
            
            for link_info in priority_links:
                link_url = link_info['url']
                normalized_link = self.normalize_url(link_url)
                
                if normalized_link not in visited:
                    priority_queue.append((link_info['score'], link_url, link_info['keywords']))
                    visited.add(normalized_link)
            
        except Exception as e:
            print(f"❌ {str(e)[:30]}")
            return scraped_pages
        
        priority_queue.sort(key=lambda x: x[0], reverse=True)
        
        while priority_queue:
            if not unlimited and len(scraped_pages) >= max_pages:
                break
                
            score, current_url, keywords = priority_queue.pop(0)
            
            keyword_str = ', '.join(keywords[:2]) if keywords else 'general'
            progress = f"[{len(scraped_pages)+1}]" if unlimited else f"[{len(scraped_pages)+1}/{max_pages}]"
            print(f"      🎯 {progress} [{score}] {keyword_str}: {current_url[:45]}...", end=' ')
            
            try:
                content, soup = self._fetch_content(current_url)
                if not content or not soup:
                    print(f"❌ Failed")
                    continue
                
                title = soup.title.string.strip() if soup.title and soup.title.string else ""
                plain_text = self.extract_readable_text(soup, remove_nav=True)
                
                scraped_pages.append({
                    'url': current_url,
                    'title': title,
                    'text': plain_text,
                    'score': score,
                    'keywords': keywords
                })
                
                print(f"✅ {len(plain_text):,} chars")
                
                new_links = self.extract_and_prioritize_links(current_url, soup)
                
                for link_info in new_links:
                    link_url = link_info['url']
                    normalized_link = self.normalize_url(link_url)
                    
                    if normalized_link not in visited:
                        priority_queue.append((link_info['score'], link_url, link_info['keywords']))
                        visited.add(normalized_link)
                
                priority_queue.sort(key=lambda x: x[0], reverse=True)
                
                time.sleep(random.uniform(1, 2))
                
            except Exception as e:
                print(f"❌ {str(e)[:30]}")
                continue
        
        print(f"\n      ✅ Priority crawl completed: {len(scraped_pages)} pages")
        return scraped_pages
    
    def scrape_website_basic(self, url: str) -> Dict:
        """Basic scraping"""
        print(f"\n   📄 [BASIC] Scraping: {url}")
        
        try:
            content, soup = self._fetch_content(url)
            if not content or not soup:
                raise Exception("Failed to fetch content")
            
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            
            metadata_parts = []
            desc = soup.find('meta', attrs={'name': 'description'})
            if desc and desc.get('content'):
                metadata_parts.append(desc['content'].strip())
            
            og_desc = soup.find('meta', attrs={'property': 'og:description'})
            if og_desc and og_desc.get('content') and og_desc['content'] not in metadata_parts:
                metadata_parts.append(og_desc['content'].strip())
            
            metadata = ' | '.join(metadata_parts)
            
            plain_text = self.extract_readable_text(soup, remove_nav=True)
            
            print(f"\n      ✅ SCRAPING SUCCESS!")
            print(f"      Title: {title[:50]}...")
            print(f"      Text: {len(plain_text):,} chars")
            
            return {
                'website_link': url,
                'title': title if title else 'No title found',
                'metadata': metadata if metadata else 'No metadata found',
                'plain_text': plain_text if plain_text else 'No content extracted'
            }
        except Exception as e:
            print(f"\n      ❌ SCRAPING FAILED: {e}")
            
            return {
                'website_link': url,
                'title': 'Error - Failed to scrape',
                'metadata': f'Error: {e}',
                'plain_text': f'Failed to scrape website. Error: {e}'
            }
    
    def scrape_website_deep(self, url: str) -> Dict:
        """Deep scraping"""
        print(f"\n   📄 [DEEP] Scraping: {url}")
        
        try:
            content, soup = self._fetch_content(url)
            if not content or not soup:
                raise Exception("Failed to fetch content")
            
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            
            metadata_parts = []
            
            for meta in soup.find_all('meta'):
                name = meta.get('name', '').lower()
                prop = meta.get('property', '').lower()
                content_text = meta.get('content', '').strip()
                
                if content_text and (name in ['description', 'keywords', 'author'] or 
                                    prop in ['og:description', 'og:title']):
                    if content_text not in metadata_parts:
                        metadata_parts.append(content_text)
            
            metadata = ' | '.join(metadata_parts)
            
            plain_text = self.extract_readable_text(soup, remove_nav=False)
            
            print(f"      ✅ Title: {title[:50]}...")
            print(f"      ✅ Text: {len(plain_text):,} chars")
            
            return {
                'website_link': url,
                'title': title,
                'metadata': metadata,
                'plain_text': plain_text
            }
        except Exception as e:
            print(f"      ❌ Error: {e}")
            return {
                'website_link': url,
                'title': 'Error',
                'metadata': 'Failed to scrape',
                'plain_text': f'Error: {str(e)}'
            }
    
    def scrape_website_multipage(self, url: str, max_subpages: int = None) -> Dict:
        """Multi-page scraping"""
        if max_subpages is None:
            max_subpages = self.max_subpages_per_site
        
        print(f"\n   📄 [MULTI-PAGE - {self.crawl_method.upper()}] Scraping: {url}")
        
        # Use appropriate crawl method
        if self.crawl_method == "bfs":
            scraped_pages = self.crawl_website_bfs(url, max_subpages)
        elif self.crawl_method == "dfs":
            scraped_pages = self.crawl_website_dfs(url, max_subpages)
        else:  # priority (default)
            scraped_pages = self.crawl_website_priority(url, max_subpages)
        
        if not scraped_pages:
            return {
                'website_link': url,
                'title': 'Error',
                'metadata': 'Failed to crawl',
                'plain_text': 'No pages could be crawled'
            }
        
        homepage = scraped_pages[0]
        title = homepage['title']
        
        all_keywords = []
        for page in scraped_pages:
            all_keywords.extend(page.get('keywords', []))
        
        unique_keywords = list(set(all_keywords))
        top_keywords = sorted(unique_keywords, key=all_keywords.count, reverse=True)[:5]
        
        metadata = f"Crawled {len(scraped_pages)} pages using {self.crawl_method.upper()}"
        if top_keywords:
            metadata += f" | Sections: {', '.join(top_keywords)}"
        
        all_pages_content = []
        
        summary = f"""MULTI-PAGE CRAWL RESULTS
Website: {url}
Method: {self.crawl_method.upper()}
Pages Scraped: {len(scraped_pages)}
Top Sections: {', '.join(top_keywords[:3])}

"""
        all_pages_content.append(summary)
        
        for i, page in enumerate(scraped_pages, 1):
            page_section = f"""

--- Page {i}/{len(scraped_pages)}: {page.get('title', 'Untitled')} ---

URL: {page['url']}
Keywords: {', '.join(page.get('keywords', [])) if page.get('keywords') else 'N/A'}

{page['text']}
"""
            all_pages_content.append(page_section)
        
        combined_text = '\n'.join(all_pages_content)
        
        print(f"\n      ✅ MULTI-PAGE COMPLETE: {len(combined_text):,} chars from {len(scraped_pages)} pages")
        
        return {
            'website_link': url,
            'title': title,
            'metadata': metadata,
            'plain_text': combined_text
        }
    
    def scrape_website(self, url: str) -> Dict:
        """Main scraper"""
        url = self._validate_and_fix_url(url)
        
        if not url:
            return {
                'website_link': url,
                'title': 'Error',
                'metadata': 'Invalid URL',
                'plain_text': 'URL validation failed'
            }
        
        if self.scraping_depth == "basic":
            return self.scrape_website_basic(url)
        elif self.scraping_depth == "deep":
            return self.scrape_website_deep(url)
        elif self.scraping_depth == "multipage":
            return self.scrape_website_multipage(url)
        else:
            return self.scrape_website_basic(url)
    
    def _validate_and_fix_url(self, url: str) -> Optional[str]:
        """Validate URL"""
        if not url or not isinstance(url, str):
            return None
        
        url = url.strip()
        
        if url.startswith('//'):
            url = 'https:' + url
        elif not url.startswith('http'):
            url = 'https://' + url
        
        url = self._decode_duckduckgo_url(url)
        
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return None
            return url
        except:
            return None
    
    def filter_already_scraped(self, urls: List[str], scraped_urls: Set[str]) -> List[str]:
        """Filter already scraped URLs"""
        normalized_scraped = {self.normalize_url(url) for url in scraped_urls}
        
        new_urls = []
        skipped_count = 0
        
        for url in urls:
            normalized_url = self.normalize_url(url)
            
            if normalized_url in normalized_scraped:
                skipped_count += 1
            else:
                new_urls.append(url)
        
        if skipped_count > 0:
            print(f"   🔄 Filtered {skipped_count} already-scraped URLs")
        
        return new_urls
    
    def process_query(
        self, 
        query: str, 
        max_websites: int = 10, 
        already_scraped: Set[str] = None
    ) -> List[Dict]:
        """Main processing pipeline"""
        print(f"\n{'='*70}")
        print(f"🚀 UNDETECTED QUERY SCRAPER")
        print(f"{'='*70}")
        print(f"Query: '{query}'")
        print(f"Depth: {self.scraping_depth.upper()}")
        print(f"Crawl Method: {self.crawl_method.upper()}")
        
        if already_scraped is None:
            already_scraped = set()
        
        print(f"Already scraped: {len(already_scraped)} URLs")
        
        search_count = max_websites * 3
        urls = self.search_duckduckgo(query, max_results=search_count)
        
        if not urls:
            print("\n❌ No URLs found!")
            return []
        
        if already_scraped:
            print(f"\n🔍 Checking for duplicates...")
            urls = self.filter_already_scraped(urls, already_scraped)
        
        urls = urls[:max_websites]
        
        if not urls:
            print("\n⚠️  All URLs already scraped!")
            return []
        
        print(f"\n📄 Scraping {len(urls)} websites...")
        
        results = []
        
        for i, url in enumerate(urls, 1):
            print(f"\n{'='*70}")
            print(f"[WEBSITE {i}/{len(urls)}]")
            
            data = self.scrape_website(url)
            results.append(data)
            
            if i < len(urls):
                delay = random.uniform(2, 4)
                time.sleep(delay)
        
        # Close driver after scraping
        self._close_driver()
        
        print(f"\n{'='*70}")
        print(f"✅ SCRAPING COMPLETE")
        print(f"{'='*70}")
        
        successful = [r for r in results if r['title'] != 'Error']
        print(f"  Successful: {len(successful)}/{len(results)}")
        
        if successful:
            char_counts = [len(r['plain_text']) for r in successful]
            print(f"  Total text: {sum(char_counts):,} chars")
            if char_counts:
                print(f"  Avg per site: {sum(char_counts) // len(char_counts):,} chars")
        
        return results


# Quick test function
def test_scraper():
    """Test the scraper"""
    print("🧪 Testing scraper...")
    
    scraper = EnhancedQueryScraper(
        scraping_depth="basic",
        max_subpages_per_site=10,
        crawl_method="priority",
        use_undetected=True,
        headless=True
    )
    
    # Test search
    urls = scraper.search_duckduckgo("MRI medical imaging", max_results=2)
    print(f"\nFound URLs: {urls}")
    
    if urls:
        # Test scraping
        result = scraper.scrape_website(urls[0])
        print(f"\nScraped: {result['title'][:50]}...")
        print(f"Text length: {len(result['plain_text']):,} chars")
    
    scraper._close_driver()


if __name__ == "__main__":
    # Install required packages first:
    # pip install undetected-chromedriver selenium beautifulsoup4 fake-useragent requests ddgs
    
    # Test the scraper
    test_scraper()