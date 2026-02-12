"""
main.py — FIXED FastAPI scraper endpoint
✅ Batch JSON writes (reduces lock contention)
✅ Better error handling for embeddings
✅ Retry logic for queryController
✅ Proper cleanup on errors
"""

from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from query_scraper import EnhancedQueryScraper
from excel_handler import JSONHandler
from generate_embeddings import run_embedding
import os
import httpx
import asyncio
import threading
from typing import List, Dict
import traceback
import time

app = FastAPI(title="Web Scraper API")

NODE_API_URL = os.getenv("NODE_API_URL", "http://localhost:3000/api/query")


class ScrapeRequest(BaseModel):
    query: str
    session_id: str = None


# ✅ Thread-safe batch collector
class BatchCollector:
    """Collects scraped data and writes in batches to reduce file I/O"""
    def __init__(self, batch_size: int = 3):
        self.batch_size = batch_size
        self.batch = []
        self.lock = threading.Lock()
        self.saved_count = 0
        self.failed_count = 0
        
    def add(self, data: Dict, json_handler: JSONHandler, output_file: str) -> bool:
        """
        Add data to batch. Writes when batch is full.
        Returns True if data was processed successfully.
        """
        with self.lock:
            self.batch.append(data)
            
            # Write batch when full
            if len(self.batch) >= self.batch_size:
                return self._flush_batch(json_handler, output_file)
            
            return True
    
    def _flush_batch(self, json_handler: JSONHandler, output_file: str) -> bool:
        """Write current batch to file"""
        if not self.batch:
            return True
            
        try:
            print(f"\n💾 Writing batch of {len(self.batch)} items...")
            
            # Write all items at once
            if os.path.exists(output_file):
                json_handler.append_to_json(output_file, self.batch)
            else:
                json_handler.export_to_json(self.batch, "k.json")
            
            self.saved_count += len(self.batch)
            self.batch = []
            
            print(f"   ✅ Batch written successfully")
            return True
            
        except Exception as e:
            print(f"   ❌ Batch write failed: {e}")
            traceback.print_exc()
            self.failed_count += len(self.batch)
            self.batch = []  # Clear failed batch
            return False
    
    def flush(self, json_handler: JSONHandler, output_file: str) -> bool:
        """Force write remaining items"""
        with self.lock:
            return self._flush_batch(json_handler, output_file)


@app.post("/scrape")
async def scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    ✅ FIXED: Batch processing + better error handling
    """
    try:
        query = request.query.strip()
        if not query:
            return {"error": "Query is required"}

        session_id = request.session_id or f"session_{hash(query)}"

        json_handler = JSONHandler()
        output_file  = os.path.join(json_handler.output_dir, "k.json")

        # Load already-scraped URLs
        already_scraped = set()
        if os.path.exists(output_file):
            try:
                already_scraped = json_handler.read_scraped_urls(output_file)
            except Exception as e:
                print(f"⚠️  Warning: Could not read scraped URLs: {e}")

        # ✅ Batch collector (writes every 3 items instead of every 1)
        batch_collector = BatchCollector(batch_size=3)

        # ✅ IMPROVED CALLBACK
        def on_website_scraped(scraped_data: dict):
            """
            Batch-based callback:
            - Collects data in batches of 3
            - Writes batch when full
            - Runs embedding after each batch write
            """
            url = scraped_data.get("website_link", "N/A")
            thread_name = threading.current_thread().name

            # Add to batch (will auto-write when batch_size reached)
            success = batch_collector.add(scraped_data, json_handler, output_file)
            
            if not success:
                print(f"   ⚠️  [{thread_name}] Failed to save {url[:50]}")
                return

        # ✅ Run scraper with optimized threading
        scraper = EnhancedQueryScraper(
            scraping_depth="multipage",
            max_subpages_per_site=10,
            crawl_method="bfs",
            max_workers=5  # Limit to 5 concurrent threads
        )

        results = scraper.process_query(
            query=query,
            max_websites=5,
            already_scraped=already_scraped,
            on_website_scraped=on_website_scraped
        )

        # ✅ Flush any remaining batch items
        print(f"\n🔄 Flushing remaining batch items...")
        batch_collector.flush(json_handler, output_file)

        # ✅ Run embedding ONCE after all scraping is done
        if batch_collector.saved_count > 0:
            print(f"\n🧠 Running embedding for {batch_collector.saved_count} new items...")
            try:
                run_embedding()
                print(f"   ✅ Embedding complete")
            except Exception as embed_err:
                print(f"   ❌ Embedding failed: {embed_err}")
                traceback.print_exc()

        # Check results
        if not results:
            return {
                "message"  : "No new results found",
                "new_urls" : 0,
                "session_id": session_id
            }

        successful = [
            r for r in results
            if r.get("title") not in ("Error", "Error - Failed to scrape")
        ]

        print(f"\n{'='*55}")
        print(f"🏁 Scraping complete")
        print(f"   Saved: {batch_collector.saved_count} | Failed: {batch_collector.failed_count}")
        print(f"{'='*55}")

        # ✅ Trigger queryController with retry logic
        if batch_collector.saved_count > 0:
            # Use background task to avoid blocking response
            background_tasks.add_task(
                trigger_query_controller_with_retry,
                query,
                session_id,
                max_retries=3
            )

        return {
            "message"            : "Scraping completed",
            "new_urls"           : len(successful),
            "total_urls"         : len(already_scraped) + len(successful),
            "saved_successfully" : batch_collector.saved_count,
            "failed"             : batch_collector.failed_count,
            "embedding_generated": batch_collector.saved_count > 0,
            "session_id"         : session_id
        }

    except Exception as e:
        print(f"\n❌ SCRAPE ENDPOINT ERROR:")
        traceback.print_exc()
        return {
            "error": str(e),
            "session_id": request.session_id
        }


# ✅ IMPROVED: Retry logic for queryController
async def trigger_query_controller_with_retry(
    query: str, 
    session_id: str, 
    max_retries: int = 3
):
    """
    Call Node.js queryController with retry logic.
    Waits 2 seconds before first attempt to ensure embeddings are ready.
    """
    # ✅ Wait for embeddings to be fully indexed
    print(f"\n⏳ Waiting 2s for embeddings to be indexed...")
    await asyncio.sleep(2)
    
    for attempt in range(max_retries):
        try:
            print(f"\n🔄 Calling queryController (attempt {attempt + 1}/{max_retries})...")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    NODE_API_URL,
                    json={
                        "session_id"   : session_id,
                        "query"        : query,
                        "skip_scraping": True  # ✅ CRITICAL: prevents loop
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    answer = result.get("answer", "No answer")
                    print(f"✅ queryController success: {answer[:120]}")
                    return  # Success!
                    
                else:
                    print(f"⚠️  queryController returned {response.status_code}")
                    print(f"   Response: {response.text[:200]}")
                    
                    # Retry on 500 errors
                    if response.status_code == 500 and attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        print(f"   Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"   ❌ Not retrying (status {response.status_code})")
                        return

        except httpx.ConnectError:
            print(f"❌ Cannot reach Node.js on {NODE_API_URL}")
            if attempt < max_retries - 1:
                print(f"   Retrying in 2s...")
                await asyncio.sleep(2)
            else:
                print(f"   ❌ Giving up after {max_retries} attempts")
            
        except Exception as e:
            print(f"❌ queryController error: {e}")
            traceback.print_exc()
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"   Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                print(f"   ❌ Giving up after {max_retries} attempts")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "scraper-api"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)