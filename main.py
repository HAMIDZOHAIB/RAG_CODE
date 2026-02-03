"""
Main Runner - Smart Version
✅ Asks for scraped file upload
✅ Reads website links and creates list
✅ Option to append to existing file
✅ Prevents duplicate websites
"""

from query_scraper import EnhancedQueryScraper
from excel_handler import JSONHandler
import os
import json


def print_banner():
    print("\n" + "="*70)
    print("🚀 SMART WEB SCRAPER")
    print("="*70)
    print("\n📋 Output: Clean JSON with no duplicates")


def choose_scraping_depth() -> str:
    print("\n" + "="*70)
    print("🎯 CHOOSE SCRAPING DEPTH")
    print("="*70)
    
    print("\n1️⃣  BASIC")
    print("   ⚡ Fast - Single page")
    print("   📊 Good for quick results")
    
    print("\n2️⃣  DEEP")
    print("   🔍 Medium - More sections")
    print("   📊 Better structured content")
    
    print("\n3️⃣  MULTI-PAGE")
    print("   🌊 Deep - Multiple pages per site")
    print("   📊 Most comprehensive data")
    
    while True:
        choice = input("\n🎯 Choose [1/2/3] (default=1): ").strip()
        
        if choice in ['1', '2', '3', '']:
            return {'1': 'basic', '2': 'deep', '3': 'multipage', '': 'basic'}[choice or '1']
        print("   ❌ Invalid. Enter 1, 2, or 3")


def get_existing_data(json_handler: JSONHandler) -> tuple:
    """Get existing JSON file and read scraped URLs"""
    print("\n" + "="*70)
    print("📂 UPLOAD EXISTING DATA")
    print("="*70)
    
    already_scraped = set()
    existing_file = None
    
    # List available JSON files
    files = json_handler.list_json_files()
    
    if files:
        print("\n📁 Available JSON files in 'scraped_data' folder:")
        for i, filepath in enumerate(files, 1):
            filename = os.path.basename(filepath)
            size = os.path.getsize(filepath) / 1024
            print(f"   {i}. {filename} ({size:.1f} KB)")
    
    use_existing = input("\n📎 Upload existing JSON file? (y/n): ").strip().lower()
    
    if use_existing == 'y':
        file_input = input("📄 Enter file number or full path: ").strip()
        
        if file_input.isdigit():
            idx = int(file_input) - 1
            if 0 <= idx < len(files):
                existing_file = files[idx]
        else:
            # Check different possible paths
            possible_paths = [
                file_input,
                os.path.join(json_handler.output_dir, file_input),
                os.path.join(".", file_input),
                os.path.abspath(file_input)
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    existing_file = path
                    break
        
        if existing_file and os.path.exists(existing_file):
            print(f"\n📂 Loading: {os.path.basename(existing_file)}")
            already_scraped = json_handler.read_scraped_urls(existing_file)
            print(f"✅ Found {len(already_scraped)} already scraped URLs")
        else:
            print("⚠️  File not found, starting fresh")
    else:
        print("✅ Starting fresh scrape")
    
    return already_scraped, existing_file


def get_search_query() -> str:
    """Get search query from user"""
    print("\n" + "="*70)
    print("🔍 SEARCH QUERY")
    print("="*70)
    
    query = input("\n🔍 Enter search query: ").strip()
    if not query:
        query = "web development tools"
        print(f"⚠️  Using default query: '{query}'")
    
    print(f"✅ Query: '{query}'")
    return query


def get_scraping_config() -> int:
    """Get scraping configuration from user"""
    print("\n" + "="*70)
    print("⚙️  CONFIGURATION")
    print("="*70)
    
    max_sites = input(f"\n🔢 Max websites to scrape (default=5): ").strip()
    max_websites = int(max_sites) if max_sites else 5
    
    print(f"✅ Will search for up to {max_websites * 3} results")
    print(f"✅ Target: {max_websites} new websites")
    
    return max_websites


def confirm_scraping(query: str, depth: str, max_websites: int, already_scraped: set) -> bool:
    """Confirm scraping with user"""
    print("\n" + "="*70)
    print("✅ READY TO START")
    print("="*70)
    
    print(f"\n📋 Configuration Summary:")
    print(f"   🔍 Query: {query}")
    print(f"   🎯 Depth: {depth.upper()}")
    print(f"   📊 Target: {max_websites} new websites")
    print(f"   📁 Existing URLs: {len(already_scraped)}")
    
    confirm = input("\n▶️  Start scraping? (y/n): ").strip().lower()
    return confirm == 'y'


def save_results(json_handler: JSONHandler, results: list, existing_file: str = None) -> str:
    """Save results to JSON file with append/new file option"""
    print("\n" + "="*70)
    print("💾 SAVING RESULTS")
    print("="*70)
    
    if not results:
        print("⚠️  No results to save")
        return None
    
    if existing_file and os.path.exists(existing_file):
        print(f"\n📁 Existing file: {os.path.basename(existing_file)}")
        choice = input("📎 Append to existing file? (y/n): ").strip().lower()
        
        if choice == 'y':
            output_file = json_handler.append_to_json(existing_file, results)
            if output_file:
                print(f"\n✅ Appended to existing file")
                return output_file
        
        # If user chose 'n' or append failed, ask for new filename
        new_name = input("\n💾 Enter new filename (or press Enter for auto): ").strip()
        if not new_name:
            output_file = json_handler.export_to_json(results)
        else:
            output_file = json_handler.export_to_json(results, new_name)
    else:
        # No existing file, ask for filename
        new_name = input("\n💾 Enter filename (or press Enter for auto): ").strip()
        if not new_name:
            output_file = json_handler.export_to_json(results)
        else:
            output_file = json_handler.export_to_json(results, new_name)
    
    return output_file


def show_final_summary(output_file: str, results: list, already_scraped: set):
    """Show final summary of scraping"""
    if output_file and os.path.exists(output_file):
        print("\n" + "="*70)
        print("✅ SCRAPING COMPLETE!")
        print("="*70)
        
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                successful = sum(1 for item in data if isinstance(item, dict) and 
                               'Error' not in item.get('title', ''))
                total_chars = sum(len(item.get('plain_text', '')) for item in data 
                                if isinstance(item, dict))
                
                print(f"\n📊 FINAL SUMMARY:")
                print(f"   📁 File: {os.path.basename(output_file)}")
                print(f"   📄 Total entries: {len(data)}")
                print(f"   ✅ Successful scrapes: {successful}")
                print(f"   📝 Total characters: {total_chars:,}")
                print(f"   🌐 Total unique URLs in database: {len(already_scraped)}")
                
                print(f"\n📍 File saved at: {os.path.abspath(output_file)}")
        
        except Exception as e:
            print(f"⚠️  Could not read saved file: {e}")
            print(f"📁 File saved at: {output_file}")


def main():
    try:
        print_banner()
        
        # Initialize handlers
        json_handler = JSONHandler()
        
        # Step 1: Choose scraping depth
        depth = choose_scraping_depth()
        print(f"✅ Depth: {depth.upper()}")
        
        # Step 2: Get existing data
        already_scraped, existing_file = get_existing_data(json_handler)
        
        # Step 3: Get search query
        query = get_search_query()
        
        # Step 4: Get scraping configuration
        max_websites = get_scraping_config()
        
        # Step 5: Confirm scraping
        if not confirm_scraping(query, depth, max_websites, already_scraped):
            print("⚠️  Scraping cancelled")
            return
        
        print("\n" + "="*70)
        print("🚀 STARTING SCRAPING")
        print("="*70)
        
        # Step 6: Initialize scraper and process query
        scraper = EnhancedQueryScraper(scraping_depth=depth, max_subpages_per_site=10)
        
        print(f"\n🔍 Processing query: '{query}'...")
        results = scraper.process_query(
            query=query,
            max_websites=max_websites,
            already_scraped=already_scraped
        )
        
        if not results:
            print("\n❌ No results obtained!")
            return
        
        # Step 7: Update already_scraped set with newly scraped URLs
        print(f"\n📊 Updating scraped URLs database...")
        initial_count = len(already_scraped)
        
        for result in results:
            if isinstance(result, dict):
                url = result.get('website_link', '')
                if url and url not in ['No URL', 'Error', 'Invalid URL']:
                    normalized_url = scraper.normalize_url(url)
                    already_scraped.add(normalized_url)
        
        new_count = len(already_scraped) - initial_count
        print(f"✅ Added {new_count} new URLs to database")
        
        # Step 8: Save results
        output_file = save_results(json_handler, results, existing_file)
        
        # Step 9: Show final summary
        show_final_summary(output_file, results, already_scraped)
        
        print("\n🎉 Done! Happy analyzing!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        print("📁 Partial results may be available")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()