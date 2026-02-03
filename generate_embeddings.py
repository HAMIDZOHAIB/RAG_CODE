import json
import requests
from sentence_transformers import SentenceTransformer

# ----------------------
# CONFIG
# ----------------------
JSON_FILE = "scraped_data/k.json"      # your JSON file
API_URL = "http://localhost:3000/api/website-data"  # Node.js endpoint
CHUNK_SIZE = 500  # words per chunk
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"  # embedding model

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

# ----------------------
# LOAD JSON
# ----------------------
with open(JSON_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

# ----------------------
# PROCESS EACH ENTRY
# ----------------------
for entry in data:
    if should_skip(entry):
        print(f"Skipping entry id={entry.get('id')} - Not enough text")
        continue

    website_id = entry.get("id")
    website_link = entry.get("website_link")
    plain_text = entry.get("plain_text")

    # Split text into chunks
    chunks = split_text_into_chunks(plain_text, CHUNK_SIZE)

    for chunk in chunks:
        # Generate embedding
        embedding_vector = model.encode(chunk).tolist()  # list of floats

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
                print(f"Inserted chunk for website_id={website_id}")
            else:
                print(f"Error inserting chunk: {response.text}")
        except Exception as e:
            print(f"Request failed: {e}")
