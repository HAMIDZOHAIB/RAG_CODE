import json
import requests
from sentence_transformers import SentenceTransformer
import os

# ----------------------
# CONFIG
# ----------------------
JSON_FILE = "scraped_data/k.json"
API_URL = "http://localhost:3000/api/website-data"
CHUNK_SIZE = 500
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
LAST_ID_FILE = "scraped_data/last_embedd.txt"  # NEW: Track last processed ID

# ----------------------
# LOAD MODEL
# ----------------------
model = SentenceTransformer(MODEL_NAME)

# ----------------------
# HELPER FUNCTIONS
# ----------------------
def split_text_into_chunks(text, chunk_size=CHUNK_SIZE):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i+chunk_size])
        chunks.append(chunk)
    return chunks

def should_skip(entry):
    text = entry.get("plain_text", "")
    if "No pages could be crawled" in text or "Crawled 10 pages using BFS | Sections: blog" in text or len(text.split()) < 150:
        return True
    return False

def get_last_processed_id():
    """Read last processed ID from file"""
    if os.path.exists(LAST_ID_FILE):
        with open(LAST_ID_FILE, "r") as f:
            content = f.read().strip()
            return int(content) if content else 0
    return 0

def save_last_processed_id(last_id):
    """Save last processed ID to file"""
    with open(LAST_ID_FILE, "w") as f:
        f.write(str(last_id))

def run_embedding():
    """Main function to generate embeddings for new entries only"""
    print("🔄 Starting embedding generation...")
    
    # Get last processed ID
    last_processed_id = get_last_processed_id()
    print(f"📍 Last processed ID: {last_processed_id}")
    
    # Load JSON data
    if not os.path.exists(JSON_FILE):
        print(f"❌ JSON file not found: {JSON_FILE}")
        return
    
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    if not data:
        print("⚠️ No data in JSON file")
        return
    
    # Filter only new entries (ID > last_processed_id)
    new_entries = [entry for entry in data if entry.get("id", 0) > last_processed_id]
    
    if not new_entries:
        print(f"✅ No new entries to process (all IDs <= {last_processed_id})")
        return
    
    print(f"📦 Found {len(new_entries)} new entries to process")
    
    max_id = last_processed_id
    processed_count = 0
    
    # Process each new entry
    for entry in new_entries:
        if should_skip(entry):
            print(f"⏭️ Skipping entry id={entry.get('id')} - Not enough text")
            continue

        website_id = entry.get("id")
        website_link = entry.get("website_link")
        plain_text = entry.get("plain_text")

        # Split text into chunks
        chunks = split_text_into_chunks(plain_text, CHUNK_SIZE)

        for chunk in chunks:
            # Generate embedding
            embedding_vector = model.encode(chunk).tolist()

            # Prepare payload
            payload = {
                "website_id": website_id,
                "website_link": website_link,
                "plain_text": chunk,
                "embedding": embedding_vector
            }

            # Send to Node.js API
            try:
                response = requests.post(API_URL, json=payload)
                if response.status_code == 201:
                    print(f"✅ Inserted chunk for website_id={website_id}")
                    processed_count += 1
                else:
                    print(f"❌ Error inserting chunk: {response.text}")
            except Exception as e:
                print(f"❌ Request failed: {e}")
        
        # Update max_id
        if website_id > max_id:
            max_id = website_id
    
    # Save the new last processed ID
    if max_id > last_processed_id:
        save_last_processed_id(max_id)
        print(f"💾 Updated last processed ID to: {max_id}")
    
    print(f"🎉 Embedding generation complete! Processed {processed_count} chunks from {len(new_entries)} entries")

# ----------------------
# MAIN EXECUTION
# ----------------------
if __name__ == "__main__":
    run_embedding()