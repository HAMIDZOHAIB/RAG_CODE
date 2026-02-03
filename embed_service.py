from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

app = FastAPI()

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

class EmbedRequest(BaseModel):
    text: str
@app.get("/")
def root():
    return {"message": "Embedding API is running"}

@app.post("/embed")
def embed_text(req: EmbedRequest):
    """
    Receives a user query and returns its embedding.
    """
    embedding = model.encode(req.text).tolist()  # 768-dimension float array
    return {"embedding": embedding}
