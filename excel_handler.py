"""
JSON Handler - Smart Version
✅ Clean, readable text output
✅ Removes duplicates and decorative characters
✅ Smart duplicate URL checking
✅ ALWAYS appends to same file (no new files created)
"""

import json
import os
from datetime import datetime
import re
import random
from typing import List, Dict, Set, Optional, Any


class JSONHandler:
    
    def __init__(self, output_dir: str = "scraped_data", default_filename: str = "scraped_data.json"):
        """
        Initialize JSON Handler
        
        Args:
            output_dir: Directory to store JSON files
            default_filename: Default filename to always use (no new files)
        """
        self.output_dir = output_dir
        self.default_filename = default_filename
        os.makedirs(self.output_dir, exist_ok=True)
    
    def normalize_url(self, url: str) -> str:
        """Normalize URL for duplicate checking"""
        if not isinstance(url, str):
            return ""
        
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
            tracking_params = ['utm_', 'fbclid', 'gclid', 'ref=']
            if any(param in url for param in tracking_params):
                url = base_url
        
        return url
    
    def clean_plain_text(self, text: str) -> str:
        """
        Clean plain text - remove decorative characters, duplicates, and organize content
        PRESERVES: Currency symbols ($, €, £, ¥), prices, amounts
        """
        if not isinstance(text, str):
            return ""
        
        # Remove decorative separators (but keep content)
        text = re.sub(r'=+', '', text)  # Remove ====
        text = re.sub(r'-{3,}', '', text)  # Remove --- (3 or more)
        text = re.sub(r'\*+', '', text)  # Remove ****
        text = re.sub(r'#{3,}', '', text)  # Remove ### (3 or more)
        
        # Remove CHUNK markers and page indicators
        text = re.sub(r'CHUNK \d+', '', text)
        text = re.sub(r'Section \d+', '', text)
        text = re.sub(r'URL: https?://[^\s]+', '', text)
        text = re.sub(r'Keywords?: [^\n]+', '', text)
        text = re.sub(r'Page: https?://[^\s]+', '', text)
        text = re.sub(r'MAIN PAGE:', '', text)
        text = re.sub(r'SUB-PAGE:', '', text)
        text = re.sub(r'MULTI-PAGE CRAWL RESULTS', '', text)
        text = re.sub(r'Website: https?://[^\s]+', '', text)
        text = re.sub(r'Method: \w+', '', text)
        text = re.sub(r'Pages Scraped: \d+', '', text)
        text = re.sub(r'Top Sections: [^\n]+', '', text)
        text = re.sub(r'Page 1/10+', '', text)
        text = re.sub(r'Page 1/2+', '', text)
        # Split into lines and process
        lines = text.split('\n')
        processed_lines = []
        seen_lines = set()
        
        for line in lines:
            line_stripped = line.strip()
            
            # Skip empty lines
            if not line_stripped:
                continue
            
            # Skip very short navigation lines
            if len(line_stripped) < 15:
                nav_keywords = ['home', 'login', 'sign up', 'signup', 'menu', 'search', 
                              'about', 'contact','blog', 'news', 'careers', 'help', 'support']
                if line_stripped.lower() in nav_keywords:
                    continue
            
            # Remove duplicate lines (case insensitive)
            line_lower = line_stripped.lower()
            if line_lower in seen_lines:
                continue
            
            # Skip lines that are just repeated words
            words = line_stripped.split()
            if len(words) <= 3 and len(line_stripped) < 30:
                # Check if it's a meaningful short line (like prices)
                # Keep if it has currency symbols or numbers
                has_currency = any(symbol in line_stripped for symbol in ['$', '€', '£', '¥', '₹'])
                has_price_pattern = re.search(r'\d+[.,]\d+', line_stripped)
                
                if not (has_currency or has_price_pattern):
                    if not any(keyword in line_lower for keyword in 
                              ['error', 'success', 'failed', 'loading', 'please']):
                        continue
            
            # Keep meaningful lines
            seen_lines.add(line_lower)
            processed_lines.append(line_stripped)
        
        # Join lines with proper spacing
        cleaned_text = '\n'.join(processed_lines)
        
        # Final cleanup
        cleaned_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned_text)  # Reduce multiple newlines
        cleaned_text = re.sub(r'[ \t]{2,}', ' ', cleaned_text)  # Reduce multiple spaces
        
        return cleaned_text.strip()
    
    def prepare_simple_data(self, result: Dict) -> Dict:
        """
        Convert scraper result to simple format
        Cleans text and extracts essential information
        PRESERVES: Currency symbols and prices
        """
        try:
            if not isinstance(result, dict):
                return {
                    'title': 'Error - Invalid data',
                    'website_link': 'No URL',
                    'metadata': 'Data format error',
                    'plain_text': 'Invalid data received'
                }
            
            # Extract basic fields
            title = result.get('title', 'No title')
            website_link = result.get('website_link', 'No URL')
            metadata = result.get('metadata', 'No metadata')
            plain_text = result.get('plain_text', '')
            
            # Ensure text is string
            if not isinstance(plain_text, str):
                plain_text = str(plain_text) if plain_text else ''
            
            # Clean the text (preserves currency symbols)
            plain_text = self.clean_plain_text(plain_text)
            
            # Truncate if too long (for safety)
            if len(plain_text) > 500000:  # 500K chars max
                plain_text = plain_text[:500000] + "\n\n[Content truncated - too large]"
            
            return {
                'title': title[:500] if title else 'No title',
                'website_link': website_link,
                'metadata': metadata[:1000] if metadata else 'No metadata',
                'plain_text': plain_text
            }
            
        except Exception as e:
            print(f"      ⚠️  Error preparing data: {str(e)[:50]}")
            return {
                'title': 'Error - Processing failed',
                'website_link': 'Error',
                'metadata': f'Error: {str(e)[:50]}',
                'plain_text': f'Error processing data: {str(e)[:100]}'
            }
    
    def read_scraped_urls(self, json_file: str) -> Set[str]:
        """Read all URLs from a JSON file"""
        print(f"\n📂 Reading URLs from: {json_file}")
        
        if not os.path.exists(json_file):
            print(f"   ⚠️  File not found: {json_file}")
            return set()
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            scraped_urls = set()
            
            if isinstance(data, list):
                # Simple format - list of dictionaries
                for item in data:
                    if isinstance(item, dict):
                        url = item.get('website_link', '')
                        if url and url not in ['No URL', 'Error', 'Invalid URL']:
                            normalized = self.normalize_url(url)
                            if normalized:
                                scraped_urls.add(normalized)
            
            print(f"   ✅ Found {len(scraped_urls)} unique URLs")
            return scraped_urls
            
        except Exception as e:
            print(f"   ❌ Error reading JSON: {str(e)[:50]}")
            return set()
    
    def read_json_data(self, json_file: str) -> List[Dict]:
        """Read and return JSON file content"""
        if not os.path.exists(json_file):
            print(f"❌ File not found: {json_file}")
            return []
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                print(f"✅ Read {len(data)} entries from {json_file}")
                return data
            else:
                print(f"⚠️  File is not in list format")
                return []
                
        except Exception as e:
            print(f"❌ Error reading file: {str(e)[:50]}")
            return []
    
    def export_to_json(self, results: List[Dict], filename: str = None) -> str:
        """
        Export results to clean JSON format
        ALWAYS appends to the same file instead of creating new files
        """
        
        if not results:
            print("\n⚠️  No results to export")
            return None
        
        print(f"\n💾 Processing {len(results)} results...")
        
        # Use default filename (always the same file)
        if filename is None:
            filename = self.default_filename
        
        if not filename.endswith('.json'):
            filename += '.json'
        
        filepath = os.path.join(self.output_dir, filename)
        
        # Check if file exists - if yes, append instead of overwrite
        if os.path.exists(filepath):
            print(f"📎 File exists - Appending to: {filename}")
            return self.append_to_json(filepath, results)
        
        # File doesn't exist - create new
        print(f"📄 Creating new file: {filename}")
        
        # Prepare simple data
        json_data = []
        total_chars = 0
        successful = 0
        errors = 0
        
        for i, result in enumerate(results, 1):
            try:
                simple_data = self.prepare_simple_data(result)
                simple_data['id'] = i
                json_data.append(simple_data)
                
                # Count stats
                plain_text = simple_data.get('plain_text', '')
                total_chars += len(plain_text)
                
                title = simple_data.get('title', '')
                if title and 'Error' not in title:
                    successful += 1
                else:
                    errors += 1
                
                # Show progress
                website_link = simple_data.get('website_link', 'No URL')
                display_url = website_link[:50] + '...' if len(website_link) > 50 else website_link
                print(f"   [{i:2d}] {display_url} ({len(plain_text):,} chars)")
                
            except Exception as e:
                errors += 1
                print(f"   [{i:2d}] ERROR - {str(e)[:50]}")
                json_data.append({
                    'id': i,
                    'title': 'Error - Export failed',
                    'website_link': 'Error',
                    'metadata': f'Export error: {str(e)[:50]}',
                    'plain_text': f'Error exporting data: {str(e)[:100]}'
                })
        
        # Save to file
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            file_size = os.path.getsize(filepath) / 1024  # KB
            
            print(f"\n✅ Saved: {os.path.basename(filepath)}")
            print(f"📊 Summary:")
            print(f"   📄 Total entries: {len(json_data)}")
            print(f"   ✅ Successful: {successful}")
            print(f"   ❌ Errors: {errors}")
            print(f"   📝 Total characters: {total_chars:,}")
            print(f"   💾 File size: {file_size:.1f} KB")
            print(f"   📍 Location: {os.path.abspath(filepath)}")
            
            return filepath
            
        except Exception as e:
            print(f"\n❌ Failed to save: {str(e)[:50]}")
            return None
    
    def append_to_json(self, existing_file: str, new_results: List[Dict]) -> str:
        """Append new results to existing JSON file with duplicate checking"""
        print(f"\n📎 Appending to: {existing_file}")
        
        if not new_results:
            print("   ⚠️  No new results to append")
            return existing_file
        
        if not os.path.exists(existing_file):
            print("   ⚠️  File not found, creating new")
            return self.export_to_json(new_results, existing_file)
        
        try:
            # Read existing data
            with open(existing_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            if not isinstance(existing_data, list):
                print("   ❌ Invalid format, creating new file")
                return self.export_to_json(new_results, f"new_{os.path.basename(existing_file)}")
            
            print(f"   📊 Existing: {len(existing_data)} entries")
            
            # Get existing URLs
            existing_urls = set()
            for item in existing_data:
                if isinstance(item, dict):
                    url = item.get('website_link', '')
                    if url and url not in ['No URL', 'Error', 'Invalid URL']:
                        normalized = self.normalize_url(url)
                        if normalized:
                            existing_urls.add(normalized)
            
            # Find max ID
            max_id = 0
            for item in existing_data:
                if isinstance(item, dict):
                    item_id = item.get('id', 0)
                    if isinstance(item_id, (int, float)):
                        max_id = max(max_id, int(item_id))
            
            # Add new results
            added = 0
            skipped = 0
            
            for result in new_results:
                try:
                    simple_data = self.prepare_simple_data(result)
                    url = simple_data.get('website_link', '')
                    
                    # Check for duplicates
                    if url and url not in ['No URL', 'Error', 'Invalid URL']:
                        normalized = self.normalize_url(url)
                        if normalized in existing_urls:
                            skipped += 1
                            print(f"   [⏭️ ] Skipped duplicate: {url[:50]}...")
                            continue
                        existing_urls.add(normalized)
                    
                    # Add ID and append
                    max_id += 1
                    simple_data['id'] = max_id
                    existing_data.append(simple_data)
                    added += 1
                    
                    plain_text_len = len(simple_data.get('plain_text', ''))
                    print(f"   [+] Added: {url[:50]}... ({plain_text_len:,} chars)")
                    
                except Exception as e:
                    print(f"   ⚠️  Skipping result: {str(e)[:50]}")
                    skipped += 1
                    continue
            
            # Save updated file
            with open(existing_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
            
            file_size = os.path.getsize(existing_file) / 1024  # KB
            
            print(f"\n✅ Append complete:")
            print(f"   ✅ Added: {added} new entries")
            print(f"   🔄 Skipped: {skipped} duplicates/errors")
            print(f"   📊 Total: {len(existing_data)} entries")
            print(f"   💾 File size: {file_size:.1f} KB")
            
            return existing_file
            
        except Exception as e:
            print(f"   ❌ Append failed: {str(e)[:50]}")
            return self.export_to_json(new_results, f"fallback_{os.path.basename(existing_file)}")
    
    def merge_json_files(self, file1: str, file2: str, output_file: str = None) -> str:
        """Merge two JSON files, removing duplicates"""
        print(f"\n🔄 Merging: {os.path.basename(file1)} + {os.path.basename(file2)}")
        
        if not os.path.exists(file1) or not os.path.exists(file2):
            print("   ❌ One or both files not found")
            return None
        
        try:
            # Read files
            data1 = self.read_json_data(file1)
            data2 = self.read_json_data(file2)
            
            if not data1 and not data2:
                print("   ⚠️  Both files are empty")
                return None
            
            # Prepare merged data
            merged_data = []
            all_urls = set()
            
            # Process first file
            for item in data1:
                if isinstance(item, dict):
                    url = item.get('website_link', '')
                    if url and url not in ['No URL', 'Error', 'Invalid URL']:
                        normalized = self.normalize_url(url)
                        if normalized in all_urls:
                            continue
                        all_urls.add(normalized)
                    merged_data.append(item)
            
            # Process second file
            added_from_second = 0
            for item in data2:
                if isinstance(item, dict):
                    url = item.get('website_link', '')
                    if url and url not in ['No URL', 'Error', 'Invalid URL']:
                        normalized = self.normalize_url(url)
                        if normalized in all_urls:
                            continue
                        all_urls.add(normalized)
                    
                    # Update ID
                    item['id'] = len(merged_data) + 1
                    merged_data.append(item)
                    added_from_second += 1
            
            # Prepare output filename
            if output_file is None:
                output_file = self.default_filename
            
            if not output_file.endswith('.json'):
                output_file += '.json'
            
            output_path = os.path.join(self.output_dir, output_file)
            
            # Save merged data
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(merged_data, f, indent=2, ensure_ascii=False)
            
            print(f"\n✅ Merge complete:")
            print(f"   📊 Total entries: {len(merged_data)}")
            print(f"   🔄 Added from second file: {added_from_second}")
            print(f"   💾 Saved as: {output_file}")
            
            return output_path
            
        except Exception as e:
            print(f"   ❌ Merge failed: {str(e)[:50]}")
            return None
    
    def list_json_files(self) -> List[str]:
        """List all JSON files in output directory"""
        files = []
        if os.path.exists(self.output_dir):
            for filename in sorted(os.listdir(self.output_dir)):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.output_dir, filename)
                    files.append(filepath)
        
        if files:
            print(f"\n📁 JSON files in '{self.output_dir}':")
            for i, filepath in enumerate(files, 1):
                size = os.path.getsize(filepath) / 1024
                name = os.path.basename(filepath)
                modified = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%Y-%m-%d %H:%M")
                
                # Read file to count entries
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    entries = len(data) if isinstance(data, list) else 1
                    print(f"   {i:2d}. {name:<40} {entries:4d} entries, {size:6.1f} KB, {modified}")
                except:
                    print(f"   {i:2d}. {name:<40} {'---':4} entries, {size:6.1f} KB, {modified}")
        else:
            print(f"\n📁 No JSON files found in '{self.output_dir}'")
        
        return files
    
    def analyze_json_file(self, filepath: str) -> Dict:
        """Analyze JSON file and return statistics"""
        if not os.path.exists(filepath):
            return {"error": "File not found"}
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                return {"error": "Not a list format"}
            
            stats = {
                "file_name": os.path.basename(filepath),
                "total_entries": len(data),
                "file_size_kb": os.path.getsize(filepath) / 1024,
                "successful_count": 0,
                "error_count": 0,
                "total_characters": 0,
                "unique_urls": set(),
                "last_modified": datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
            }
            
            for item in data:
                if isinstance(item, dict):
                    title = item.get('title', '')
                    if title and 'Error' not in title:
                        stats["successful_count"] += 1
                    else:
                        stats["error_count"] += 1
                    
                    plain_text = item.get('plain_text', '')
                    if isinstance(plain_text, str):
                        stats["total_characters"] += len(plain_text)
                    
                    url = item.get('website_link', '')
                    if url and url not in ['No URL', 'Error', 'Invalid URL']:
                        stats["unique_urls"].add(self.normalize_url(url))
            
            stats["unique_url_count"] = len(stats["unique_urls"])
            
            return stats
            
        except Exception as e:
            return {"error": str(e)[:100]}


# Test function
def test_json_handler():
    """Test the JSON handler"""
    handler = JSONHandler()
    
    print("🧪 Testing JSON Handler")
    print("="*50)
    
    # List files
    handler.list_json_files()
    
    # Test clean text function with currency preservation
    test_text = """
    ====================
    CHUNK 1 
    --- Section 1 ---
    HOME
    HOME
    HOME
    PRICING
    PRICING
    Our plans start at $78/month.
    Enterprise: $600/month
    Pro Plan: €99.99/month
    Basic: £50/year
    This is some meaningful content that should be kept.
    Another important paragraph with useful information.
    URL: https://example.com
    Keywords: test, demo
    """
    
    cleaned = handler.clean_plain_text(test_text)
    print(f"\n🔧 Clean text test:")
    print(f"Original: {len(test_text)} chars")
    print(f"Cleaned: {len(cleaned)} chars")
    print(f"\nCleaned output:")
    print(cleaned)
    
    print("\n✅ JSON Handler ready to use!")
    print(f"💡 Default file: {handler.default_filename}")
    print(f"💡 All results will be appended to the same file")


if __name__ == "__main__":
    test_json_handler()