from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

app = FastAPI()

model = SentenceTransformer("mixedbread-ai/mxbai-embed-large-v1")

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
    embedding = model.encode(req.text).tolist()  
    return {"embedding": embedding}
