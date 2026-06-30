# upload_vectorstore.py
# Chunking + Embedding bang Gemini API + Luu vao Qdrant Vector Database

import os
import json
import logging
from google import genai
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Config
ARTICLES_DIR = "articles"
COLLECTION_NAME = "optisigns_articles"
EMBEDDING_MODEL = "gemini-embedding-001"
VECTOR_SIZE = 3072  # Kich thuoc vector cua gemini-embedding-001
CHUNK_SIZE = 800   # So tu toi da moi chunk
CHUNK_OVERLAP = 100  # So tu chong lap giua cac chunk
QDRANT_URL = os.environ.get("QDRANT_URL")
UPLOADED_FILES_CACHE = "uploaded_files.json"

# Khoi tao clients
gemini_client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
qdrant_api_key = os.environ.get("QDRANT_API_KEY", None)
qdrant_client = QdrantClient(url=QDRANT_URL, api_key=qdrant_api_key)


def chunk_text(text, title, url, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Chia van ban thanh cac doan nho (chunks) voi metadata"""
    words = text.split()
    chunks = []
    start = 0
    
    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words)
        
        chunks.append({
            "text": chunk_text,
            "title": title,
            "url": url,
            "chunk_index": len(chunks)
        })
        
        # Di chuyen toi vi tri tiep theo, co overlap
        start = end - overlap
        if start >= len(words):
            break
    
    return chunks


def get_embedding(text, max_retries=5):
    """Lay embedding vector tu Gemini API, co retry khi bi rate limit"""
    import time as _time
    for attempt in range(max_retries):
        try:
            result = gemini_client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text
            )
            return result.embeddings[0].values
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait_time = 2 ** attempt * 5  # 5s, 10s, 20s, 40s, 80s
                logger.warning(f"Rate limited! Waiting {wait_time}s before retry ({attempt+1}/{max_retries})...")
                _time.sleep(wait_time)
            else:
                raise e
    raise Exception(f"Failed after {max_retries} retries")


def ensure_collection():
    """Tao collection trong Qdrant neu chua co"""
    collections = qdrant_client.get_collections().collections
    collection_names = [c.name for c in collections]
    
    if COLLECTION_NAME not in collection_names:
        qdrant_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE
            )
        )
        logger.info(f"Created Qdrant collection: {COLLECTION_NAME}")
    else:
        logger.info(f"Collection '{COLLECTION_NAME}' already exists")


def load_uploaded_cache():
    """Doc cache file da upload"""
    if os.path.exists(UPLOADED_FILES_CACHE):
        with open(UPLOADED_FILES_CACHE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_uploaded_cache(cache):
    """Luu cache file da upload"""
    with open(UPLOADED_FILES_CACHE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2)


def upload_files():
    """Chunking + Embedding + Upsert vao Qdrant"""
    ensure_collection()
    cache = load_uploaded_cache()
    
    uploaded = 0
    skipped = 0
    failed = 0
    total_chunks = 0

    md_files = [f for f in os.listdir(ARTICLES_DIR) if f.endswith('.md')]
    logger.info(f"Found {len(md_files)} Markdown files to process...")

    for filename in md_files:
        if filename in cache:
            skipped += 1
            continue

        filepath = os.path.join(ARTICLES_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # Trich xuat title va URL tu noi dung Markdown
            lines = content.split('\n')
            title = lines[0].replace('# ', '') if lines else filename
            url = ""
            for line in lines:
                if line.startswith('**Article URL:**') or line.startswith('**URL:**'):
                    url = line.split(':', 1)[-1].strip().rstrip('*').strip()
                    break

            # Chunking
            chunks = chunk_text(content, title, url)
            logger.info(f"Processing: {filename} → {len(chunks)} chunks")

            # Embedding + Upsert tung chunk
            points = []
            for i, chunk in enumerate(chunks):
                embedding = get_embedding(chunk["text"])
                
                # Tao ID duy nhat cho moi chunk (hash cua filename + chunk_index)
                import hashlib
                point_id = int(hashlib.md5(f"{filename}_{i}".encode()).hexdigest()[:16], 16)
                
                points.append(PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "text": chunk["text"],
                        "title": chunk["title"],
                        "url": chunk["url"],
                        "filename": filename,
                        "chunk_index": chunk["chunk_index"]
                    }
                ))

            # Upsert batch vao Qdrant
            if points:
                qdrant_client.upsert(
                    collection_name=COLLECTION_NAME,
                    points=points
                )
                total_chunks += len(points)

            cache[filename] = f"qdrant:{len(chunks)}_chunks"
            save_uploaded_cache(cache)
            uploaded += 1
            
            # Delay giua cac file de tranh rate limit
            import time
            time.sleep(2)

        except Exception as e:
            logger.error(f"Failed: {filename} - {e}")
            failed += 1

    logger.info("=" * 40)
    logger.info("=== Upload to Qdrant Complete ===")
    logger.info(f"Files processed: {uploaded}")
    logger.info(f"Files skipped (cached): {skipped}")
    logger.info(f"Files failed: {failed}")
    logger.info(f"Total chunks in Qdrant: {total_chunks}")
    logger.info("=" * 40)

    return cache


if __name__ == "__main__":
    upload_files()