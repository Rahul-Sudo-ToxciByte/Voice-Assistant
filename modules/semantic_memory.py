import chromadb
from sentence_transformers import SentenceTransformer

client = chromadb.Client()
collection = client.create_collection("jarvis_memory")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

def add_memory(text, memory_id):
    embedding = embedding_model.encode(text)
    collection.add(documents=[text], embeddings=[embedding], ids=[memory_id]) 