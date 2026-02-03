"""
Enhanced Query Scraper - DEEP CRAWLING VERSION
✅ BFS/DFS crawling for complete site traversal
✅ Playwright support for JavaScript/React sites
✅ Smart priority-based crawling
✅ Full content preservation with chunking
"""

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from typing import List, Dict, Set, Optional, Tuple
from urllib.parse import urlparse, urljoin, quote_plus
import time
import re
from collections import Counter, deque
import asyncio


class EnhancedQueryScraper:
    """
    DEEP CRAWLING scraper with:
    - BFS/DFS crawling for complete site coverage
    - Playwright for JavaScript-heavy sites
    - Priority-based intelligent crawling
    - Full content preservation
    """
    
    def __init__(
        self, 
        scraping_depth: str = "basic", 
        max_subpages_per_site: int = None,  # None = unlimited (scrape all found links)
        crawl_method: str = "bfs",  # "bfs", "dfs", or "priority"
        use_playwright: bool = False,
        playwright_timeout: int = 30000
    ):
        """
        Initialize scraper
        
        Args:
            scraping_depth: "basic", "deep", or "multipage"
            max_subpages_per_site: Maximum internal pages to scrape per website (None = unlimited, scrape all found links)
            crawl_method: "bfs" (breadth-first), "dfs" (depth-first), or "priority" (smart)
            use_playwright: Use Playwright for JavaScript-heavy sites
            playwright_timeout: Timeout for Playwright page loads (ms)
        """
        self.scraping_depth = scraping_depth
        self.max_subpages_per_site = max_subpages_per_site if max_subpages_per_site is not None else float('inf')
        self.crawl_method = crawl_method
        self.use_playwright = use_playwright
        self.playwright_timeout = playwright_timeout
        
        # Session for requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        # Playwright browser instance (lazy loaded)
        self.playwright_browser = None
        self.playwright_context = None
        
        # IMPROVED: Smarter URL filtering
        # High priority pages (should scrape)
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
        
        # Low priority but acceptable
        self.acceptable_paths = {
            'blog': 30, 'news': 30, 'updates': 30,
            'careers': 20, 'jobs': 20
        }
        
        # Skip these completely
        self.skip_paths = [
            '/signup', '/sign-up', '/signin', '/sign-in', '/login', '/register',
            '/admin', '/dashboard', '/profile', '/account', '/settings', '/user',
            '/cart', '/checkout', '/billing', '/invoice',
            '/privacy', '/terms', '/legal', '/cookie', '/gdpr', '/compliance',
            '/download', '/downloads', '/assets', '/cdn','forget-password', '/reset-password',
        ]
        
        # File extensions to skip
        self.skip_extensions = [
            '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico', '.bmp',
            '.mp4', '.mp3', '.avi', '.mov', '.wmv', '.flv', '.webm',
            '.zip', '.rar', '.tar', '.gz', '.7z',
            '.exe', '.dmg', '.pkg', '.deb', '.rpm',
            '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.xml', '.json', '.csv', '.rss', '.atom'
        ]
        
        print(f"\n🎯 Scraping Configuration:")
        print(f"   📊 Depth: {scraping_depth.upper()}")
        print(f"   🔢 Max Subpages: {'UNLIMITED (scrape all found links)' if max_subpages_per_site == float('inf') else max_subpages_per_site}")
        print(f"   🔄 Crawl Method: {crawl_method.upper()}")
        print(f"   🎭 Playwright: {'ENABLED' if use_playwright else 'DISABLED'}")
        self._print_depth_info()
    
    def _print_depth_info(self):
        """Print information about selected scraping depth"""
        if self.scraping_depth == "basic":
            print("   ⚡ BASIC: Single page, fast, readable chunks")
        elif self.scraping_depth == "deep":
            print("   🔍 DEEP: More sections, structured content")
        elif self.scraping_depth == "multipage":
            print(f"   🌊 MULTI-PAGE: {self.crawl_method.upper()} crawling of priority pages")
    
    # async def _init_playwright(self):
    #     """Initialize Playwright browser (lazy loading)"""
    #     if self.playwright_browser is not None:
    #         return
        
    #     try:
    #         from playwright.async_api import async_playwright
            
    #         print("   🎭 Initializing Playwright...")
    #         self.playwright_instance = await async_playwright().start()
    #         self.playwright_browser = await self.playwright_instance.chromium.launch(
    #             headless=True,
    #             args=['--no-sandbox', '--disable-setuid-sandbox']
    #         )
    #         self.playwright_context = await self.playwright_browser.new_context(
    #             user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    #         )
    #         print("   ✅ Playwright initialized")
    #     except ImportError:
    #         print("   ⚠️  Playwright not installed. Install with: pip install playwright && playwright install")
    #         self.use_playwright = False
    #     except Exception as e:
    #         print(f"   ⚠️  Playwright init failed: {e}")
    #         self.use_playwright = False
    
    # async def _close_playwright(self):
    #     """Close Playwright browser"""
    #     if self.playwright_browser:
    #         await self.playwright_context.close()
    #         await self.playwright_browser.close()
    #         await self.playwright_instance.stop()
    #         self.playwright_browser = None
    #         self.playwright_context = None
    
    # async def _fetch_with_playwright(self, url: str) -> Optional[str]:
    #     """Fetch page content using Playwright (for JS-heavy sites)"""
    #     try:
    #         page = await self.playwright_context.new_page()
    #         await page.goto(url, wait_until='networkidle', timeout=self.playwright_timeout)
            
    #         # Wait for dynamic content
    #         await page.wait_for_timeout(2000)
            
    #         # Get rendered HTML
    #         content = await page.content()
    #         await page.close()
            
    #         return content
    #     except Exception as e:
    #         print(f"      ⚠️  Playwright fetch error: {e}")
    #         return None
    
    def search_duckduckgo(self, query: str, max_results: int = 10) -> List[str]:
        """Search DuckDuckGo and return URLs"""
        print(f"\n🔍 Searching DuckDuckGo: '{query}'")
        
        urls = []
        
        # Try ddgs package
        try:
            from duckduckgo_search import DDGS
            print("   📦 Using duckduckgo-search package...")
            
            ddgs = DDGS()
            results = list(ddgs.text(query, max_results=max_results))
            
            print(f"   🔎 Found {len(results)} search results")
            
            for result in results:
                url = result.get('href') or result.get('link') or result.get('url')
                if not url:
                    continue
                
                # Decode if it's a DuckDuckGo redirect
                actual_url = self._decode_duckduckgo_url(url)
                
                if actual_url and self._is_valid_search_result(actual_url):
                    urls.append(actual_url)
            
            if urls:
                print(f"   ✅ Selected {len(urls)} valid URLs")
                return urls
        except ImportError:
            print("   ⚠️  duckduckgo-search not installed, using HTML fallback...")
        except Exception as e:
            print(f"   ⚠️  Search error: {e}, using HTML fallback...")
        
        # Fallback: HTML scraping
        if not urls:
            urls = self._search_duckduckgo_html(query, max_results)
        
        return urls
    
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
                
                # Decode DuckDuckGo redirect URLs
                actual_url = self._decode_duckduckgo_url(href)
                
                if actual_url and self._is_valid_search_result(actual_url):
                    urls.append(actual_url)
            
            print(f"   ✅ Found {len(urls)} URLs via HTML scraping")
            return urls
        except Exception as e:
            print(f"   ❌ HTML scraping failed: {e}")
            return []
    
    def _decode_duckduckgo_url(self, url: str) -> Optional[str]:
        """
        Decode DuckDuckGo redirect URLs
        Example: //duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com
        Returns: https://example.com
        """
        try:
            from urllib.parse import parse_qs, unquote, urlparse as parse_url
            
            # Add scheme if missing
            if url.startswith('//'):
                url = 'https:' + url
            
            # Check if it's a DuckDuckGo redirect
            if 'duckduckgo.com/l/' in url:
                parsed = parse_url(url)
                params = parse_qs(parsed.query)
                
                # Extract actual URL from 'uddg' parameter
                if 'uddg' in params:
                    actual_url = unquote(params['uddg'][0])
                    return actual_url
            
            # If not a redirect, return as-is (with scheme added if needed)
            if not url.startswith('http'):
                url = 'https://' + url
            
            return url
            
        except Exception as e:
            print(f"      ⚠️  URL decode error: {e}")
            return None
    
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
            'mdpi.com', 'researchgate.net'
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
    
    def normalize_url(self, url: str) -> str:
        """Normalize URL for comparison"""
        url = url.strip().lower()
        
        # Remove fragment
        if '#' in url:
            url = url.split('#')[0]
        
        # Remove trailing slash
        if url.endswith('/'):
            url = url[:-1]
        
        # Remove www
        url = url.replace('://www.', '://')
        
        # Remove tracking parameters
        if '?' in url:
            base_url = url.split('?')[0]
            tracking_params = ['utm_', 'fbclid', 'gclid', 'ref', 'source', 'campaign']
            if any(param in url for param in tracking_params):
                url = base_url
        
        return url
    
    def extract_readable_text(self, soup: BeautifulSoup, remove_nav: bool = True) -> str:
        """
        CHUNKED TEXT EXTRACTION: Extract text in clear, digestible chunks
        
        Creates properly formatted chunks:
        - Clear section headers with [CHUNK X]
        - Preserves context within each chunk
        - Easy to scan and understand
        """
        if remove_nav:
            # Remove navigation, footer, header
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'iframe', 'svg', 'noscript']):
                tag.decompose()
        else:
            # Only remove scripts and styles
            for tag in soup(['script', 'style', 'iframe', 'svg', 'noscript']):
                tag.decompose()
        
        # Find main content area
        main_content = None
        for selector in ['main', 'article', '[role="main"]', '.main-content', '#main-content', '.content', '#content']:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        if not main_content:
            main_content = soup.find('body')
        
        if not main_content:
            main_content = soup
        
        # Extract all content sections
        sections = self._extract_content_sections(main_content)
        
        # Create readable chunks
        chunks = self._create_text_chunks(sections)
        
        return chunks
    
    def _extract_content_sections(self, element) -> List[Dict]:
        """
        Extract content organized by sections
        Returns list of {type, content, header} dicts
        PRESERVES: Currency symbols ($, €, £, ¥), prices, amounts
        """
        sections = []
        current_header = None
        
        for child in element.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'div', 'section'], recursive=True):
            tag_name = child.name.lower()
            
            # Headers create new sections
            if tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                header_text = child.get_text(strip=True)
                if header_text and len(header_text) > 2:
                    current_header = header_text
                    sections.append({
                        'type': 'header',
                        'content': header_text,
                        'header': current_header
                    })
            
            # Paragraphs - preserve all special characters
            elif tag_name == 'p':
                # Use separator=' ' to preserve spaces, strip=True to clean edges
                para_text = child.get_text(separator=' ', strip=True)
                if para_text and len(para_text) > 20:  # Meaningful paragraphs only
                    sections.append({
                        'type': 'paragraph',
                        'content': para_text,  # Preserves $, €, £, ¥ and all amounts
                        'header': current_header
                    })
            
            # Lists - preserve special characters
            elif tag_name in ['ul', 'ol']:
                list_items = []
                for li in child.find_all('li', recursive=False):
                    li_text = li.get_text(strip=True)
                    if li_text:
                        list_items.append(li_text)  # Preserves currency symbols
                
                if list_items:
                    sections.append({
                        'type': 'list',
                        'content': list_items,
                        'header': current_header
                    })
        
        return sections
    
    def _create_text_chunks(self, sections: List[Dict]) -> str:
        """
        Create clean, readable text from sections
        NO decorative boxes, just pure content with simple section markers
        """
        if not sections:
            return "No content extracted"
        
        chunks = []
        current_chunk = []
        current_word_count = 0
        chunk_number = 1
        
        TARGET_WORDS_PER_CHUNK = 300  # Ideal chunk size
        MAX_WORDS_PER_CHUNK = 500     # Maximum before forcing new chunk
        
        for section in sections:
            section_type = section['type']
            content = section['content']
            header = section.get('header')
            
            # Format section based on type - CLEAN formatting only
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
            
            # Check if adding this would exceed limit
            if current_word_count > 0 and (current_word_count + word_count > MAX_WORDS_PER_CHUNK):
                # Save current chunk with simple marker
                chunk_header = f"\n--- Section {chunk_number} ---\n\n"
                chunks.append(chunk_header + ''.join(current_chunk))
                
                # Start new chunk
                current_chunk = [formatted]
                current_word_count = word_count
                chunk_number += 1
            else:
                # Add to current chunk
                current_chunk.append(formatted)
                current_word_count += word_count
        
        # Add final chunk
        if current_chunk:
            chunk_header = f"\n--- Section {chunk_number} ---\n\n"
            chunks.append(chunk_header + ''.join(current_chunk))
        
        # NO decorative header - just return clean text
        return '\n'.join(chunks)
    
    def score_url_importance(self, url: str, link_text: str = "") -> Tuple[int, List[str]]:
        """
        IMPROVED: Score URL based on importance
        Returns (score, matched_keywords)
        """
        url_lower = url.lower()
        text_lower = link_text.lower()
        
        score = 0
        matched_keywords = []
        
        # Check high priority paths
        for keyword, points in self.priority_paths.items():
            if keyword in url_lower or keyword in text_lower:
                score += points
                matched_keywords.append(keyword)
        
        # Check acceptable paths
        for keyword, points in self.acceptable_paths.items():
            if keyword in url_lower or keyword in text_lower:
                score += points
                matched_keywords.append(keyword)
        
        # Penalty for unwanted patterns
        unwanted_patterns = [
            'blog/20', 'news/20', 'article/', '/tag/', '/category/',
            'author/', 'archive/', 'wp-content', '/feed', '/rss'
        ]
        for pattern in unwanted_patterns:
            if pattern in url_lower:
                score -= 50  # Heavy penalty
        
        # Base score for home or root pages
        parsed = urlparse(url)
        if parsed.path in ['', '/']:
            score += 10
        
        return max(0, score), matched_keywords
    
    def extract_and_prioritize_links(self, url: str, soup: BeautifulSoup) -> List[Dict]:
        """
        IMPROVED: Extract internal links and prioritize smartly
        Only returns high-value links
        """
        base_domain = urlparse(url).netloc
        all_links = []
        seen_normalized = set()
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Convert to absolute URL
            absolute_url = urljoin(url, href)
            
            # Check if same domain
            link_domain = urlparse(absolute_url).netloc
            if link_domain != base_domain:
                continue
            
            # Skip if unwanted
            if not self._is_valid_internal_link(absolute_url):
                continue
            
            # Normalize and deduplicate
            normalized = self.normalize_url(absolute_url)
            if normalized in seen_normalized:
                continue
            seen_normalized.add(normalized)
            
            # Get link text
            link_text = link.get_text(strip=True)
            
            # Score importance
            score, keywords = self.score_url_importance(absolute_url, link_text)
            
            # Only keep links with positive scores
            if score > 0:
                all_links.append({
                    'url': absolute_url,
                    'text': link_text,
                    'score': score,
                    'keywords': keywords
                })
        
        # Sort by score (highest first)
        all_links.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"      🔗 Found {len(all_links)} high-priority internal links")
        
        return all_links
    
    def _is_valid_internal_link(self, url: str) -> bool:
        """Check if internal link should be scraped"""
        url_lower = url.lower()
        
        # Skip unwanted paths
        if any(path in url_lower for path in self.skip_paths):
            return False
        
        # Skip file downloads
        if any(url_lower.endswith(ext) for ext in self.skip_extensions):
            return False
        
        # Skip blog posts with dates
        if re.search(r'/\d{4}/\d{2}/', url_lower):  # /2024/01/
            return False
        
        # Skip pagination
        if re.search(r'[?&]page=\d+', url_lower):
            return False
        
        return True
    
    def crawl_website_bfs(self, start_url: str, max_pages: int) -> List[Dict]:
        """
        BFS (Breadth-First Search) crawling
        Explores level by level - good for finding important pages early
        If max_pages is inf, scrapes ALL found links
        """
        print(f"\n      🔄 BFS Crawling from: {start_url}")
        
        unlimited = max_pages == float('inf')
        if unlimited:
            print(f"      ♾️  UNLIMITED MODE: Will scrape ALL found links")
        
        base_domain = urlparse(start_url).netloc
        visited = set()
        queue = deque([start_url])
        scraped_pages = []
        
        normalized_start = self.normalize_url(start_url)
        visited.add(normalized_start)
        
        while queue:
            # Check limit only if not unlimited
            if not unlimited and len(scraped_pages) >= max_pages:
                break
                
            current_url = queue.popleft()
            
            progress = f"[{len(scraped_pages)+1}]" if unlimited else f"[{len(scraped_pages)+1}/{max_pages}]"
            print(f"      📄 {progress} {current_url[:60]}...", end=' ')
            
            try:
                # Scrape page
                response = self.session.get(current_url, timeout=15)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Extract content
                title = soup.title.string.strip() if soup.title and soup.title.string else ""
                plain_text = self.extract_readable_text(soup, remove_nav=True)
                
                # Score this page
                score, keywords = self.score_url_importance(current_url)
                
                scraped_pages.append({
                    'url': current_url,
                    'title': title,
                    'text': plain_text,
                    'score': score,
                    'keywords': keywords
                })
                
                print(f"✅ {len(plain_text):,} chars")
                
                # Extract links for next level
                priority_links = self.extract_and_prioritize_links(current_url, soup)
                
                for link_info in priority_links:
                    link_url = link_info['url']
                    normalized_link = self.normalize_url(link_url)
                    
                    if normalized_link not in visited:
                        visited.add(normalized_link)
                        queue.append(link_url)
                
                time.sleep(0.5)
                
            except Exception as e:
                print(f"❌ {str(e)[:30]}")
                continue
        
        print(f"\n      ✅ BFS crawled {len(scraped_pages)} pages")
        return scraped_pages
    
    def crawl_website_dfs(self, start_url: str, max_pages: int, visited: Set[str] = None, scraped_pages: List[Dict] = None, depth: int = 0, max_depth: int = 10) -> List[Dict]:
        """
        DFS (Depth-First Search) crawling
        Goes deep into one path before backtracking - good for thorough exploration
        If max_pages is inf, scrapes ALL found links
        """
        if visited is None:
            visited = set()
            unlimited = max_pages == float('inf')
            if unlimited:
                print(f"\n      🔄 DFS Crawling from: {start_url}")
                print(f"      ♾️  UNLIMITED MODE: Will scrape ALL found links")
            else:
                print(f"\n      🔄 DFS Crawling from: {start_url}")
        
        if scraped_pages is None:
            scraped_pages = []
        
        unlimited = max_pages == float('inf')
        
        # Stop conditions
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
            # Scrape page
            response = self.session.get(start_url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Extract content
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            plain_text = self.extract_readable_text(soup, remove_nav=True)
            
            # Score this page
            score, keywords = self.score_url_importance(start_url)
            
            scraped_pages.append({
                'url': start_url,
                'title': title,
                'text': plain_text,
                'score': score,
                'keywords': keywords
            })
            
            print(f"✅ {len(plain_text):,} chars")
            
            # Extract links and recurse
            priority_links = self.extract_and_prioritize_links(start_url, soup)
            
            for link_info in priority_links:
                if not unlimited and len(scraped_pages) >= max_pages:
                    break
                
                link_url = link_info['url']
                self.crawl_website_dfs(link_url, max_pages, visited, scraped_pages, depth + 1, max_depth)
                time.sleep(0.3)
            
        except Exception as e:
            print(f"❌ {str(e)[:30]}")
        
        if depth == 0:
            print(f"\n      ✅ DFS crawled {len(scraped_pages)} pages")
        
        return scraped_pages
    
    def crawl_website_priority(self, start_url: str, max_pages: int) -> List[Dict]:
        """
        PRIORITY-BASED crawling (RECOMMENDED)
        Always crawls highest-priority pages first
        Ensures critical pages (pricing, features, etc.) are scraped
        If max_pages is inf, scrapes ALL found links
        """
        print(f"\n      🎯 Priority-Based Crawling from: {start_url}")
        
        unlimited = max_pages == float('inf')
        if unlimited:
            print(f"      ♾️  UNLIMITED MODE: Will scrape ALL found links")
        
        base_domain = urlparse(start_url).netloc
        visited = set()
        priority_queue = []  # List of (score, url, keywords) tuples
        scraped_pages = []
        
        # Start with homepage
        normalized_start = self.normalize_url(start_url)
        visited.add(normalized_start)
        
        # Scrape homepage first
        progress = "[1]" if unlimited else f"[1/{max_pages}]"
        print(f"      🏠 {progress} Homepage: {start_url[:60]}...", end=' ')
        
        try:
            response = self.session.get(start_url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            
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
            
            # Extract all links from homepage
            priority_links = self.extract_and_prioritize_links(start_url, soup)
            
            # Add to priority queue
            for link_info in priority_links:
                link_url = link_info['url']
                normalized_link = self.normalize_url(link_url)
                
                if normalized_link not in visited:
                    priority_queue.append((link_info['score'], link_url, link_info['keywords']))
                    visited.add(normalized_link)
            
        except Exception as e:
            print(f"❌ {str(e)[:30]}")
            return scraped_pages
        
        # Sort by priority (highest score first)
        priority_queue.sort(key=lambda x: x[0], reverse=True)
        
        # Crawl in priority order
        while priority_queue:
            # Check limit only if not unlimited
            if not unlimited and len(scraped_pages) >= max_pages:
                break
                
            score, current_url, keywords = priority_queue.pop(0)
            
            keyword_str = ', '.join(keywords[:2]) if keywords else 'general'
            progress = f"[{len(scraped_pages)+1}]" if unlimited else f"[{len(scraped_pages)+1}/{max_pages}]"
            print(f"      🎯 {progress} [{score}] {keyword_str}: {current_url[:45]}...", end=' ')
            
            try:
                response = self.session.get(current_url, timeout=15)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'lxml')
                
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
                
                # Extract more links from this page
                new_links = self.extract_and_prioritize_links(current_url, soup)
                
                for link_info in new_links:
                    link_url = link_info['url']
                    normalized_link = self.normalize_url(link_url)
                    
                    if normalized_link not in visited:
                        priority_queue.append((link_info['score'], link_url, link_info['keywords']))
                        visited.add(normalized_link)
                
                # Re-sort priority queue
                priority_queue.sort(key=lambda x: x[0], reverse=True)
                
                time.sleep(0.5)
                
            except Exception as e:
                print(f"❌ {str(e)[:30]}")
                continue
        
        print(f"\n      ✅ Priority crawl completed: {len(scraped_pages)} pages")
        return scraped_pages
    
    # async def crawl_website_playwright(self, start_url: str, max_pages: int) -> List[Dict]:
    #     """
    #     PLAYWRIGHT-BASED crawling for JavaScript-heavy sites
    #     Uses headless browser to render dynamic content
    #     If max_pages is inf, scrapes ALL found links
    #     """
    #     print(f"\n      🎭 Playwright Crawling (JS-enabled): {start_url}")
        
    #     unlimited = max_pages == float('inf')
    #     if unlimited:
    #         print(f"      ♾️  UNLIMITED MODE: Will scrape ALL found links")
        
    #     await self._init_playwright()
        
    #     if not self.playwright_browser:
    #         print("      ❌ Playwright unavailable, falling back to requests")
    #         return self.crawl_website_priority(start_url, max_pages)
        
    #     base_domain = urlparse(start_url).netloc
    #     visited = set()
    #     priority_queue = []
    #     scraped_pages = []
        
    #     normalized_start = self.normalize_url(start_url)
    #     visited.add(normalized_start)
        
    #     # Scrape homepage with Playwright
    #     progress = "[1]" if unlimited else "[1]"
    #     print(f"      🏠 {progress} Homepage (Playwright): {start_url[:50]}...", end=' ')
        
    #     try:
    #         html_content = await self._fetch_with_playwright(start_url)
            
    #         if html_content:
    #             soup = BeautifulSoup(html_content, 'lxml')
                
    #             title = soup.title.string.strip() if soup.title and soup.title.string else ""
    #             plain_text = self.extract_readable_text(soup, remove_nav=True)
    #             score, keywords = self.score_url_importance(start_url)
                
    #             scraped_pages.append({
    #                 'url': start_url,
    #                 'title': title,
    #                 'text': plain_text,
    #                 'score': score,
    #                 'keywords': keywords
    #             })
                
    #             print(f"✅ {len(plain_text):,} chars")
                
    #             # Extract links
    #             priority_links = self.extract_and_prioritize_links(start_url, soup)
                
    #             for link_info in priority_links:
    #                 link_url = link_info['url']
    #                 normalized_link = self.normalize_url(link_url)
                    
    #                 if normalized_link not in visited:
    #                     priority_queue.append((link_info['score'], link_url, link_info['keywords']))
    #                     visited.add(normalized_link)
            
    #     except Exception as e:
    #         print(f"❌ {str(e)[:30]}")
        
    #     # Sort by priority
    #     priority_queue.sort(key=lambda x: x[0], reverse=True)
        
    #     # Crawl remaining pages
    #     while priority_queue:
    #         # Check limit only if not unlimited
    #         if not unlimited and len(scraped_pages) >= max_pages:
    #             break
                
    #         score, current_url, keywords = priority_queue.pop(0)
            
    #         keyword_str = ', '.join(keywords[:2]) if keywords else 'general'
    #         progress = f"[{len(scraped_pages)+1}]" if unlimited else f"[{len(scraped_pages)+1}/{max_pages}]"
    #         print(f"      🎯 {progress} [{score}] {keyword_str}: {current_url[:40]}...", end=' ')
            
    #         try:
    #             html_content = await self._fetch_with_playwright(current_url)
                
    #             if html_content:
    #                 soup = BeautifulSoup(html_content, 'lxml')
                    
    #                 title = soup.title.string.strip() if soup.title and soup.title.string else ""
    #                 plain_text = self.extract_readable_text(soup, remove_nav=True)
                    
    #                 scraped_pages.append({
    #                     'url': current_url,
    #                     'title': title,
    #                     'text': plain_text,
    #                     'score': score,
    #                     'keywords': keywords
    #                 })
                    
    #                 print(f"✅ {len(plain_text):,} chars")
                    
    #                 # Extract more links
    #                 new_links = self.extract_and_prioritize_links(current_url, soup)
                    
    #                 for link_info in new_links:
    #                     link_url = link_info['url']
    #                     normalized_link = self.normalize_url(link_url)
                        
    #                     if normalized_link not in visited:
    #                         priority_queue.append((link_info['score'], link_url, link_info['keywords']))
    #                         visited.add(normalized_link)
                    
    #                 priority_queue.sort(key=lambda x: x[0], reverse=True)
                    
    #                 await asyncio.sleep(0.5)
            
    #         except Exception as e:
    #             print(f"❌ {str(e)[:30]}")
    #             continue
        
    #     print(f"\n      ✅ Playwright crawl completed: {len(scraped_pages)} pages")
    #     return scraped_pages
    
    def scrape_website_basic(self, url: str) -> Dict:
        """
        BASIC SCRAPING: Single page, readable chunks
        """
        print(f"\n   📄 [BASIC] Scraping: {url}")
        
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Extract title
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            
            # Extract metadata
            metadata_parts = []
            desc = soup.find('meta', attrs={'name': 'description'})
            if desc and desc.get('content'):
                metadata_parts.append(desc['content'].strip())
            
            og_desc = soup.find('meta', attrs={'property': 'og:description'})
            if og_desc and og_desc.get('content') and og_desc['content'] not in metadata_parts:
                metadata_parts.append(og_desc['content'].strip())
            
            metadata = ' | '.join(metadata_parts)
            
            # Extract readable text
            plain_text = self.extract_readable_text(soup, remove_nav=True)
            
            # DETAILED TERMINAL OUTPUT
            print(f"\n      ✅ SCRAPING SUCCESS!")
            print(f"      ═══════════════════════════════════════════════════════════════════")
            print(f"      📌 Title: {title if title else '(no title found)'}...")
            print(f"      📝 Metadata: {metadata if metadata else '(no metadata found)'}...")
            print(f"\n      📄 PLAIN TEXT SCRAPED ({len(plain_text):,} characters):")
            
            # Show plain text in terminal (first 1000 chars for preview)
            if len(plain_text) > 1000:
                preview_text = plain_text[:1000]
                for line in preview_text.split('\n'):
                    if line.strip():
                        print(f"      │ {line[:65]}")
                print(f"      │")
                print(f"      │ ... [showing first 1000 of {len(plain_text):,} total chars]")
                print(f"      │")
                print(f"      │ ✅ Full text will be stored in JSON")
            else:
                # Show all text if less than 1000 chars
                for line in plain_text.split('\n'):
                    if line.strip():
                        print(f"      │ {line[:65]}")
            
            print(f"      └─────────────────────────────────────────────────────────────────┘")
            
            return {
                'website_link': url,
                'title': title if title else 'No title found',
                'metadata': metadata if metadata else 'No metadata found',
                'plain_text': plain_text if plain_text else 'No content extracted'
            }
        except Exception as e:
            error_msg = str(e)
            print(f"\n      ❌ SCRAPING FAILED!")
            print(f"      ═══════════════════════════════════════════════════════════════════")
            print(f"      Error: {error_msg}")
            print(f"      ⚠️  Website may be blocked or inaccessible")
            
            return {
                'website_link': url,
                'title': 'Error - Failed to scrape',
                'metadata': f'Error: {error_msg}',
                'plain_text': f'Failed to scrape website. Error: {error_msg}'
            }
    
    def scrape_website_deep(self, url: str) -> Dict:
        """
        DEEP SCRAPING: More comprehensive extraction
        """
        print(f"\n   📄 [DEEP] Scraping: {url}")
        
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Extract title
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            
            # Extract comprehensive metadata
            metadata_parts = []
            
            for meta in soup.find_all('meta'):
                name = meta.get('name', '').lower()
                prop = meta.get('property', '').lower()
                content = meta.get('content', '').strip()
                
                if content and (name in ['description', 'keywords', 'author'] or 
                               prop in ['og:description', 'og:title']):
                    if content not in metadata_parts:
                        metadata_parts.append(content)
            
            metadata = ' | '.join(metadata_parts)
            
            # Extract readable text (more aggressive)
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
        """
        MULTI-PAGE SCRAPING: Uses selected crawl method
        Supports: BFS, DFS, Priority-based, or Playwright
        """
        if max_subpages is None:
            max_subpages = self.max_subpages_per_site
        
        print(f"\n   📄 [MULTI-PAGE - {self.crawl_method.upper()}] Scraping: {url}")
        
        # Use appropriate crawl method
        if self.use_playwright:
            # Playwright crawling (async)
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in async context, create new loop
                import nest_asyncio
                nest_asyncio.apply()
            
            scraped_pages = loop.run_until_complete(
                self.crawl_website_playwright(url, max_subpages)
            )
        elif self.crawl_method == "bfs":
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
        
        # Combine all pages
        homepage = scraped_pages[0]
        title = homepage['title']
        
        # Create metadata
        all_keywords = []
        for page in scraped_pages:
            all_keywords.extend(page.get('keywords', []))
        
        unique_keywords = list(set(all_keywords))
        top_keywords = sorted(unique_keywords, key=all_keywords.count, reverse=True)[:5]
        
        metadata = f"Crawled {len(scraped_pages)} pages using {self.crawl_method.upper()}"
        if top_keywords:
            metadata += f" | Sections: {', '.join(top_keywords)}"
        
        # Combine all content
        all_pages_content = []
        
        # Add simple summary header - NO decorative boxes
        summary = f"""MULTI-PAGE CRAWL RESULTS
Website: {url}
Method: {self.crawl_method.upper()}
Pages Scraped: {len(scraped_pages)}
Top Sections: {', '.join(top_keywords[:3])}

"""
        all_pages_content.append(summary)
        
        # Add each page
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
        """Main scraper - delegates based on depth"""
        # Validate and fix URL first
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
        """
        Validate and fix URL before scraping
        Returns None if URL cannot be fixed
        """
        if not url or not isinstance(url, str):
            return None
        
        url = url.strip()
        
        # Fix missing scheme
        if url.startswith('//'):
            url = 'https:' + url
        elif not url.startswith('http'):
            url = 'https://' + url
        
        # Decode if it's a DuckDuckGo redirect
        url = self._decode_duckduckgo_url(url)
        
        # Validate
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return None
            return url
        except:
            return None
    
    def filter_already_scraped(self, urls: List[str], scraped_urls: Set[str]) -> List[str]:
        """Filter out already scraped URLs"""
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
        print(f"🚀 ENHANCED QUERY SCRAPER - DEEP CRAWLING EDITION")
        print(f"{'='*70}")
        print(f"Query: '{query}'")
        print(f"Depth: {self.scraping_depth.upper()}")
        print(f"Crawl Method: {self.crawl_method.upper()}")
        print(f"Playwright: {'ENABLED' if self.use_playwright else 'DISABLED'}")
        
        if already_scraped is None:
            already_scraped = set()
        
        print(f"Already scraped: {len(already_scraped)} URLs")
        
        # Search
        search_count = max_websites * 3
        urls = self.search_duckduckgo(query, max_results=search_count)
        
        if not urls:
            print("\n❌ No URLs found!")
            return []
        
        # Filter
        if already_scraped:
            print(f"\n🔍 Checking for duplicates...")
            urls = self.filter_already_scraped(urls, already_scraped)
        
        urls = urls[:max_websites]
        
        if not urls:
            print("\n⚠️  All URLs already scraped!")
            return []
        
        print(f"\n📄 Scraping {len(urls)} websites...")
        
        # Scrape
        results = []
        
        for i, url in enumerate(urls, 1):
            print(f"\n{'='*70}")
            print(f"[WEBSITE {i}/{len(urls)}]")
            
            data = self.scrape_website(url)
            results.append(data)
            
            # Smart delay
            if i < len(urls):
                delay = 1 if self.scraping_depth == "basic" else 2
                time.sleep(delay)
        
        # Cleanup Playwright if used
        if self.use_playwright and self.playwright_browser:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self._close_playwright())
        
        print(f"\n{'='*70}")
        print(f"✅ SCRAPING COMPLETE")
        print(f"{'='*70}")
        
        successful = [r for r in results if r['title'] != 'Error']
        print(f"  Successful: {len(successful)}/{len(results)}")
        
        if successful:
            char_counts = [len(r['plain_text']) for r in successful]
            print(f"  Total text: {sum(char_counts):,} chars")
            print(f"  Avg per site: {sum(char_counts) // len(char_counts):,} chars")
        
        return results


# Example usage
if __name__ == "__main__":
    # OPTION 1: Priority-based crawling - UNLIMITED (scrapes ALL found links)
    scraper = EnhancedQueryScraper(
        scraping_depth="multipage",
        max_subpages_per_site=None,  # None = unlimited (scrapes all found links)
        crawl_method="priority",  # Smart priority-based
        use_playwright=False
    )
    
    
    results = scraper.process_query("AI coding assistant tools", max_websites=3)
    
    # Save results
    import json
    with open('scraped_data.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved to scraped_data.json")