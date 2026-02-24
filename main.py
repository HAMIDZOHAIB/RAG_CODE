"""
main.py — FastAPI scraper endpoint (FIXED)

Bugs fixed in this version:
  BUG 4: embed_thread.join() had no timeout — if embedding crashed silently,
          the thread would hang forever and trigger_query_controller never ran.
          Fix: join with 120s timeout, continue even if thread is still alive.

  BUG 5: trigger_query_controller had no retries and poor error messages.
          If Node.js was briefly busy or returned 5xx, it silently failed.
          Fix: 3 attempts with exponential backoff, clear error messages that
          tell you exactly what's wrong (wrong port, wrong path, timeout, etc.)

CORRECT FLOW:
──────────────────────────────────────────────────────────────────────
1. scraper.process_query()  → returns list of scraped dicts
2. We spin up our own embed_thread (run_embedding_queue via threading.Thread)
3. Each result is saved to k.json → embed_single_entry() called one-by-one
4. After embed_thread finishes (with timeout) → wait 1s → call queryController
──────────────────────────────────────────────────────────────────────
"""

from fastapi import FastAPI
from pydantic import BaseModel
from query_scraper import EnhancedQueryScraper
from excel_handler import JSONHandler
from generate_embeddings import embed_single_entry
import os
import json
import httpx
import asyncio
import threading
import queue

app = FastAPI(title="Web Scraper API")

NODE_API_URL = os.getenv("NODE_API_URL", "http://localhost:3000/api/query")


class ScrapeRequest(BaseModel):
    query: str
    session_id: str = None


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: get the assigned id for a URL from k.json
# ─────────────────────────────────────────────────────────────────────────────
def _get_entry_id(output_file: str, url: str):
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            data = f.read().strip()
            if not data:
                return None
            entries = json.loads(data)
        for entry in reversed(entries):
            if entry.get("website_link", "").rstrip("/") == url.rstrip("/"):
                return entry.get("id")
    except Exception as e:
        print(f"   ⚠️  Could not read id from k.json: {e}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# EMBEDDING RUNNER — processes items one at a time from a Queue
# ─────────────────────────────────────────────────────────────────────────────
def run_embedding_queue(work_queue: queue.Queue,
                        json_handler: JSONHandler,
                        output_file: str,
                        counter: dict):
    """
    Runs in a background thread.
    Pulls scraped_data dicts from work_queue and:
      1. Appends to k.json
      2. Calls embed_single_entry()
    Stops when it receives None (sentinel).
    """
    while True:
        scraped_data = work_queue.get()
        if scraped_data is None:          # sentinel → exit
            work_queue.task_done()
            break

        url = scraped_data.get("website_link", "N/A")
        print(f"\n{'─'*55}")
        print(f"💾 [EmbedRunner] → {url[:50]}")

        # ── Step 1: Save to k.json ─────────────────────────────────
        website_id = None
        try:
            if os.path.exists(output_file):
                json_handler.append_to_json(output_file, [scraped_data])
            else:
                json_handler.export_to_json([scraped_data], "k.json")

            website_id = _get_entry_id(output_file, url)
            print(f"   ✅ Saved → website_id={website_id}")
        except Exception as e:
            print(f"   ❌ Save failed: {e}")
            counter["failed"] += 1
            work_queue.task_done()
            continue

        # ── Step 2: Embed this entry ───────────────────────────────
        if website_id:
            try:
                n = embed_single_entry(scraped_data, website_id)
                counter["chunks"] += n
                counter["saved"]  += 1
                print(f"   ✅ Embedded → {n} chunks (id={website_id})")
            except Exception as e:
                import traceback
                print(f"   ❌ Embed failed: {e}")
                traceback.print_exc()
                counter["failed"] += 1
        else:
            print(f"   ⚠️  Could not determine website_id — skipping embed")
            counter["failed"] += 1

        print(f"{'─'*55}")
        work_queue.task_done()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/scrape")
async def scrape(request: ScrapeRequest):
    try:
        query = request.query.strip()
        if not query:
            return {"error": "Query is required"}

        session_id = request.session_id or f"session_{hash(query)}"

        json_handler = JSONHandler()
        output_file  = os.path.join(json_handler.output_dir, "k.json")

        already_scraped = set()
        if os.path.exists(output_file):
            already_scraped = json_handler.read_scraped_urls(output_file)

        # ── Counters ───────────────────────────────────────────────
        counter = {"saved": 0, "failed": 0, "chunks": 0}

        # ── Scrape ────────────────────────────────────────────────
        scraper = EnhancedQueryScraper(
            scraping_depth="multipage",
            max_subpages_per_site=10,
            crawl_method="bfs",
            max_workers=5
        )

        # ── Capture return value safely ────────────────────────────
        raw_return = scraper.process_query(
            query=query,
            max_websites=2,
            already_scraped=already_scraped,
        )

        results = _normalize_results(raw_return)

        if not results:
            return {
                "message"   : "No new results found",
                "new_urls"  : 0,
                "session_id": session_id
            }

        successful = [
            r for r in results
            if isinstance(r, dict) and
               r.get("title") not in ("Error", "Error - Failed to scrape") and
               r.get("website_link")
        ]

        print(f"\n{'='*55}")
        print(f"🏁 Scraping done — {len(successful)} usable sites out of {len(results)}")
        print(f"{'='*55}")

        if not successful:
            return {
                "message"   : "No new results found",
                "new_urls"  : 0,
                "session_id": session_id
            }

        # ── Start embedding in a background thread ─────────────────
        work_queue   = queue.Queue()
        embed_thread = threading.Thread(
            target=run_embedding_queue,
            args=(work_queue, json_handler, output_file, counter),
            daemon=True,
            name="EmbedRunner"
        )
        embed_thread.start()

        # Push all successful results into the queue
        for item in successful:
            work_queue.put(item)
        work_queue.put(None)   # sentinel — tells runner to stop after last item

        # ── Wait for embedding + call queryController ───────────────
        asyncio.create_task(
            wait_for_embed_then_query(embed_thread, query, session_id, counter)
        )

        return {
            "message"    : "Scraping complete, embedding in progress",
            "new_urls"   : len(successful),
            "total_urls" : len(already_scraped) + len(successful),
            "session_id" : session_id
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# NORMALIZE: handle whatever process_query() returns
# ─────────────────────────────────────────────────────────────────────────────
def _normalize_results(raw):
    """
    Accepts any of these return shapes from process_query():
      - list of dicts                    → return as-is
      - tuple of dicts                   → convert to list
      - tuple of (list_of_dicts, thread) → return first element
      - tuple of (list_of_dicts, X, Y…)  → return first element if it's a list
    """
    if raw is None:
        return []

    if isinstance(raw, list):
        if not raw or isinstance(raw[0], dict):
            return raw
        if isinstance(raw[0], list):
            return raw[0]

    if isinstance(raw, tuple):
        first = raw[0] if raw else None

        if isinstance(first, list) and (not first or isinstance(first[0], dict)):
            print(f"ℹ️  process_query returned tuple — using first element (list of {len(first)} results)")
            return first

        if isinstance(first, dict):
            print(f"ℹ️  process_query returned flat tuple of {len(raw)} dicts")
            return list(raw)

        if len(raw) >= 2 and isinstance(raw[1], list):
            return raw[1]

    print(f"⚠️  Unexpected return type from process_query(): {type(raw)} — attempting list()")
    try:
        return list(raw)
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# WAIT FOR EMBED → CALL QUERY CONTROLLER
# BUG FIX 4: Added 120s timeout on embed_thread.join() so a crashed embed
# thread doesn't block forever and prevent trigger_query_controller from running.
# ─────────────────────────────────────────────────────────────────────────────
async def wait_for_embed_then_query(embed_thread: threading.Thread,
                                     query: str,
                                     session_id: str,
                                     counter: dict):
    loop = asyncio.get_event_loop()

    # BUG FIX 4: join with timeout — if embed thread hangs/crashes, don't block forever
    def join_with_timeout():
        embed_thread.join(timeout=120)
        if embed_thread.is_alive():
            print("⚠️  [EmbedRunner] Thread did not finish within 120s — continuing anyway")

    await loop.run_in_executor(None, join_with_timeout)

    saved  = counter.get("saved", 0)
    chunks = counter.get("chunks", 0)
    failed = counter.get("failed", 0)
    print(f"\n✅ Embedding complete — saved={saved}, chunks={chunks}, failed={failed}")

    if saved > 0:
        await asyncio.sleep(1)   # let DB finish committing
        print(f"🔄 Calling queryController (skip_scraping=True)...")
        await trigger_query_controller(query, session_id)
    elif failed > 0 and saved == 0:
        # Even if all embeds failed, still call queryController so it can respond to
        # the session with "couldn't find info" instead of leaving frontend hanging
        print(f"⚠️  All {failed} embeds failed — still notifying queryController")
        await trigger_query_controller(query, session_id)
    else:
        print(f"⚠️  Nothing was embedded and no failures recorded — skipping queryController call")


# ─────────────────────────────────────────────────────────────────────────────
# TRIGGER QUERY CONTROLLER
# BUG FIX 5: Added retries with backoff + detailed error messages so you
# know exactly whether Node is unreachable, returning errors, or timing out.
#
# IMPORTANT: NODE_API_URL must match your Express router mount path exactly.
# Default: http://localhost:3000/api/query
# If your route is mounted differently (e.g. /api/v1/query), set NODE_API_URL env var.
# ─────────────────────────────────────────────────────────────────────────────
async def trigger_query_controller(query: str, session_id: str, retries: int = 2):
    for attempt in range(1, retries + 2):
        try:
            async with httpx.AsyncClient() as client:
                print(f"   🔄 POST {NODE_API_URL} (attempt {attempt}/{retries+1})")
                response = await client.post(
                    NODE_API_URL,
                    json={
                        "session_id"   : session_id,
                        "query"        : query,
                        "skip_scraping": True
                    },
                    timeout=45.0  # increased from 30s — LLM generation can be slow
                )
                if response.status_code == 200:
                    result = response.json()
                    answer = result.get("answer", "")
                    print(f"✅ queryController responded ({len(answer)} chars): {answer[:120]}")
                    return  # success — stop retrying

                print(f"⚠️  queryController HTTP {response.status_code}: {response.text[:300]}")

                # 4xx = client error (wrong URL, bad payload) — no point retrying
                if response.status_code < 500:
                    print(f"   👉 4xx error — check NODE_API_URL path and request format")
                    return

        except httpx.ConnectError:
            print(f"❌ Cannot connect to Node.js at {NODE_API_URL} (attempt {attempt})")
            print(f"   👉 Is Node.js running? Is the port correct?")
            print(f"   👉 Current NODE_API_URL = '{NODE_API_URL}'")
            print(f"   👉 Set NODE_API_URL env var if your server uses a different port/path")

        except httpx.TimeoutException:
            print(f"⏱️  Request to queryController timed out after 45s (attempt {attempt})")
            print(f"   👉 LLM or DB may be overloaded")

        except Exception as e:
            print(f"❌ Unexpected error calling queryController (attempt {attempt}): {e}")

        # Wait before retrying (exponential backoff: 2s, 4s)
        if attempt <= retries:
            wait = 2 * attempt
            print(f"   ⏳ Retrying in {wait}s...")
            await asyncio.sleep(wait)

    print(f"❌ trigger_query_controller failed after {retries+1} attempts — frontend may be stuck")
    print(f"   👉 User will see '✅ Found new information. Please ask your question again.'")
    print(f"   👉 They can re-ask to get the answer from the freshly scraped data")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)