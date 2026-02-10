from fastapi import FastAPI
from pydantic import BaseModel
from query_scraper import EnhancedQueryScraper
from excel_handler import JSONHandler
from generate_embeddings import run_embedding
import os
import json
import httpx
import asyncio

app = FastAPI(title="Web Scraper API")

# ✅ Configuration for Node.js API
NODE_API_URL = os.getenv("NODE_API_URL", "http://localhost:3000/api/query")

class ScrapeRequest(BaseModel):
    query: str
    session_id: str = None

@app.post("/scrape")
async def scrape(request: ScrapeRequest):
    try:
        query = request.query.strip()
        if not query:
            return {"error": "Query is required"}

        # Generate session_id if not provided
        session_id = request.session_id or f"session_{hash(query)}"

        json_handler = JSONHandler()
        output_file = os.path.join(json_handler.output_dir, "k.json")
        
        # Load existing URLs
        already_scraped = set()
        if os.path.exists(output_file):
            already_scraped = json_handler.read_scraped_urls(output_file)

        # Scraper config
        depth = "multipage"
        max_websites = 2
        scraper = EnhancedQueryScraper(scraping_depth=depth, max_subpages_per_site=10)

        results = scraper.process_query(query=query, max_websites=max_websites, already_scraped=already_scraped)

        if not results:
            return {"message": "No new results found"}

        # Update already_scraped
        for result in results:
            if isinstance(result, dict):
                url = result.get('website_link', '')
                if url and url not in ['No URL', 'Error', 'Invalid URL']:
                    already_scraped.add(scraper.normalize_url(url))

        # Append to k.json
        if os.path.exists(output_file):
            json_handler.append_to_json(output_file, results)
        else:
            json_handler.export_to_json(results, "k.json")
        
        # ✅ AUTO RUN EMBEDDING WHEN NEW DATA ADDED
        print("=" * 50)
        print("🚀 New data added, generating embeddings...")
        print("=" * 50)
        
        embedding_success = False
        try:
            from generate_embeddings import run_embedding
            run_embedding()
            print("✅ Embedding generation completed successfully!")
            embedding_success = True
        except Exception as embed_error:
            print(f"❌ Embedding generation failed: {embed_error}")
            import traceback
            traceback.print_exc()

        # ✅ AUTOMATICALLY CALL NODE.JS QUERY CONTROLLER AFTER EMBEDDING
        if embedding_success:
            print("=" * 50)
            print("🔄 Triggering query controller with the same query...")
            print("=" * 50)
            
            # Fire and forget - don't wait for response
            asyncio.create_task(trigger_query_controller(query, session_id))

        return {
            "message": "Scraping and embedding completed",
            "new_urls": len(results),
            "total_urls": len(already_scraped),
            "embedding_generated": embedding_success,
            "session_id": session_id
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


# ✅ ASYNC FUNCTION TO TRIGGER QUERY CONTROLLER (FIRE AND FORGET)
async def trigger_query_controller(query: str, session_id: str):
    """
    Trigger the Node.js query controller without waiting for response
    ✅ IMPORTANT: skip_scraping=true to prevent infinite loop
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                NODE_API_URL,
                json={
                    "session_id": session_id,
                    "query": query,
                    "skip_scraping": True  # ✅ CRITICAL: Prevent re-scraping
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                print("✅ Query controller triggered successfully!")
                result = response.json()
                print(f"📝 Answer: {result.get('answer', 'No answer')[:100]}...")
            else:
                print(f"⚠️ Query controller returned status {response.status_code}")
                
    except httpx.ConnectError:
        print("❌ Could not connect to Node.js server. Is it running on port 3000?")
    except Exception as api_error:
        print(f"❌ Error triggering query controller: {api_error}")


# ADD THIS AT THE END
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)