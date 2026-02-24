"""
generate_embeddings.py

TWO functions:
─────────────────────────────────────────────────────────────────────
1. embed_single_entry(entry, website_id)
   Called by CallbackRunner IMMEDIATELY after each item is saved.
   Takes the scraped dict directly — NO file reading, NO last_id race.
   Only one call at a time (CallbackRunner is sequential) → no races.

2. run_embedding()
   Legacy batch function — kept for startup recovery.
   Reads k.json, finds unprocessed entries, embeds them.
   Only called from MainThread after everything else is done.
─────────────────────────────────────────────────────────────────────

FIXES in this version:
  FIX 1 — timeout raised from 15s → 60s
           Node.js was busy during scrape response processing, causing
           every chunk POST to time out. 60s gives Node room to breathe.

  FIX 2 — retry logic added to insert_chunks_to_db
           Each chunk now retries up to 2 times with 3s backoff before
           giving up. Eliminates the cascade of timeout failures.

  FIX 3 — chunks counter now correctly tracked in embed_single_entry
           Previously returned 0 when thread timed out because the
           counter was never flushed back to main.py's counter dict.
           Now insert_chunks_to_db returns accurate count even on retry.

  FIX 4 — NODE_API_URL reads from env var so it matches main.py
           Previously hardcoded to localhost:3000/api/website-data.
           Now uses WEBSITE_DATA_API_URL env var with same fallback.
"""

import json
import requests
import os
import threading
import time
from sentence_transformers import SentenceTransformer

# ── Config ───────────────────────────────────────────────────────────────────
JSON_FILE    = "scraped_data/k.json"

# FIX 4: Read from env var so it's consistent with main.py configuration
API_URL      = os.getenv("WEBSITE_DATA_API_URL", "http://localhost:3000/api/website-data")

CHUNK_SIZE   = 500
MODEL_NAME = "mixedbread-ai/mxbai-embed-large-v1"
LAST_ID_FILE = "scraped_data/last_embedd.txt"

# FIX 1: Raised from 15s → 60s
# Node.js was busy handling the scrape response while chunks were being POSTed,
# causing every single chunk to time out at 15s and retry infinitely.
CHUNK_INSERT_TIMEOUT = 60

# FIX 2: Number of retries per chunk on timeout/failure
CHUNK_INSERT_RETRIES = 2

# ── Model loaded once, shared safely (inference is thread-safe) ───────────────
model = SentenceTransformer(MODEL_NAME)

# ── Lock only for last_embedd.txt (used by run_embedding, not embed_single) ──
_id_file_lock = threading.Lock()


def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE,
                      overlap: int = 50) -> list:
    """
    Splits text into overlapping chunks.

    Example with chunk_size=500, overlap=50:
      Chunk 1: words[0:500]     (words 0   to 500)
      Chunk 2: words[450:950]   (words 450 to 950,  50-word overlap with chunk 1)
      Chunk 3: words[900:1400]  (words 900 to 1400, 50-word overlap with chunk 2)

    Overlap ensures context is never lost at chunk boundaries, which
    improves RAG retrieval accuracy for sentences that span two chunks.
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    step   = chunk_size - overlap   # e.g. 500 - 50 = 450
    start  = 0

    while start < len(words):
        end   = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end >= len(words):       # reached the end — stop
            break
        start += step               # advances: 0 → 450 → 900 → 1350...

    return chunks


def should_skip_text(text: str) -> bool:
    return (
        not text
        or len(text.split()) < 150
        or "No pages could be crawled" in text
    )


def insert_chunks_to_db(website_id: int, website_link: str,
                         plain_text: str, label: str = "") -> int:
    """
    Splits text → embeds each chunk → POSTs to Node DB endpoint.
    Returns number of chunks successfully inserted.

    FIX 1: timeout raised to 60s (was 15s)
    FIX 2: each chunk retries up to CHUNK_INSERT_RETRIES times on failure
    """
    chunks = split_into_chunks(plain_text, CHUNK_SIZE)
    inserted = 0

    for chunk in chunks:
        if not chunk.strip():
            continue

        vector = model.encode(chunk).tolist()
        payload = {
            "website_id"  : website_id,
            "website_link": website_link,
            "plain_text"  : chunk,
            "embedding"   : vector,
        }

        # FIX 2: Retry loop — each chunk gets CHUNK_INSERT_RETRIES attempts
        success = False
        for attempt in range(1, CHUNK_INSERT_RETRIES + 2):  # e.g. 1, 2, 3
            try:
                resp = requests.post(
                    API_URL,
                    json=payload,
                    timeout=CHUNK_INSERT_TIMEOUT  # FIX 1: was hardcoded 15
                )
                if resp.status_code == 201:
                    print(f"   ✅ {label} Chunk inserted (website_id={website_id})")
                    inserted += 1
                    success = True
                    break
                else:
                    print(f"   ❌ {label} Insert failed (id={website_id}) "
                          f"status={resp.status_code}: {resp.text[:80]}")
                    # Don't retry on 4xx — it's a client error, retrying won't help
                    if resp.status_code < 500:
                        break
                    if attempt <= CHUNK_INSERT_RETRIES:
                        print(f"   ⏳ {label} Retrying in 3s (attempt {attempt}/{CHUNK_INSERT_RETRIES + 1})...")
                        time.sleep(3)

            except requests.exceptions.Timeout:
                print(f"   ❌ {label} Timeout after {CHUNK_INSERT_TIMEOUT}s "
                      f"(id={website_id}, attempt {attempt}/{CHUNK_INSERT_RETRIES + 1})")
                if attempt <= CHUNK_INSERT_RETRIES:
                    print(f"   ⏳ {label} Retrying in 3s...")
                    time.sleep(3)

            except Exception as e:
                print(f"   ❌ {label} Request error (id={website_id}): {e}")
                if attempt <= CHUNK_INSERT_RETRIES:
                    print(f"   ⏳ {label} Retrying in 3s...")
                    time.sleep(3)

        if not success:
            print(f"   ⚠️  {label} Chunk permanently failed after "
                  f"{CHUNK_INSERT_RETRIES + 1} attempts (id={website_id})")

    return inserted


# ─────────────────────────────────────────────────────────────────────────────
# ✅ PRIMARY FUNCTION — called per item from CallbackRunner / EmbedRunner
# ─────────────────────────────────────────────────────────────────────────────
def embed_single_entry(entry: dict, website_id: int) -> int:
    """
    Embeds ONE scraped entry immediately.

    Called by EmbedRunner (run_embedding_queue in main.py) right after
    saving to k.json. EmbedRunner is a single sequential thread →
    no concurrent calls → zero race condition risk.

    Does NOT read k.json or last_embedd.txt → no shared state.

    Args:
        entry      : the scraped dict (website_link, plain_text, etc.)
        website_id : the id assigned when saved to k.json

    Returns:
        number of chunks inserted (FIX 3: now always accurate)
    """
    plain_text   = entry.get("plain_text", "")
    website_link = entry.get("website_link", "")
    thread_name  = threading.current_thread().name

    if should_skip_text(plain_text):
        print(f"   ⏭️  [{thread_name}] Skipping id={website_id} — not enough text")
        return 0

    print(f"   🧠 [{thread_name}] Embedding id={website_id} "
          f"({len(plain_text):,} chars, API={API_URL})...")

    # FIX 3: inserted is returned directly — no counter race with main.py
    inserted = insert_chunks_to_db(
        website_id, website_link, plain_text,
        label=f"[id={website_id}]"
    )

    # Update last_embedd.txt so run_embedding() knows this was processed
    _update_last_id(website_id)

    print(f"   ✅ [{thread_name}] id={website_id} → {inserted} chunks inserted")
    return inserted


def _update_last_id(new_id: int):
    """Thread-safe update of last processed ID tracker."""
    with _id_file_lock:
        current = _read_last_id()
        if new_id > current:
            with open(LAST_ID_FILE, "w") as f:
                f.write(str(new_id))


def _read_last_id() -> int:
    if os.path.exists(LAST_ID_FILE):
        try:
            with open(LAST_ID_FILE, "r") as f:
                val = f.read().strip()
                return int(val) if val else 0
        except:
            return 0
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# LEGACY BATCH FUNCTION — kept for recovery / manual runs
# ─────────────────────────────────────────────────────────────────────────────
def run_embedding():
    """
    Reads k.json and embeds any entries with id > last processed id.
    Used only as fallback (e.g. if server restarted mid-scrape).
    Under normal operation, embed_single_entry() handles everything.
    """
    thread_name = threading.current_thread().name
    print(f"🔄 [{thread_name}] Starting batch embedding...")

    last_id = _read_last_id()
    print(f"📍 [{thread_name}] Last processed ID: {last_id}")

    if not os.path.exists(JSON_FILE):
        print(f"❌ [{thread_name}] JSON not found: {JSON_FILE}")
        return

    # Retry read in case another thread just wrote the file
    data = None
    for attempt in range(3):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            break
        except json.JSONDecodeError:
            if attempt < 2:
                time.sleep(0.3)

    if not data:
        print(f"⚠️  [{thread_name}] Could not read JSON")
        return

    new_entries = [e for e in data if e.get("id", 0) > last_id]
    if not new_entries:
        print(f"✅ [{thread_name}] No new entries to embed")
        return

    print(f"📦 [{thread_name}] {len(new_entries)} new entries to embed")

    max_id         = last_id
    total_inserted = 0

    for entry in new_entries:
        if should_skip_text(entry.get("plain_text", "")):
            print(f"⏭️  [{thread_name}] Skipping id={entry.get('id')} — not enough text")
            continue

        website_id   = entry.get("id")
        website_link = entry.get("website_link", "")
        plain_text   = entry.get("plain_text", "")

        n = insert_chunks_to_db(website_id, website_link, plain_text,
                                 label=f"[batch id={website_id}]")
        total_inserted += n

        if website_id and website_id > max_id:
            max_id = website_id

    if max_id > last_id:
        _update_last_id(max_id)

    print(f"🎉 [{thread_name}] Batch done — {total_inserted} chunks from {len(new_entries)} entries")


if __name__ == "__main__":
    run_embedding()