# test_assistant.py
# Test OptiBot dung Qdrant Vector Database + Gemini API (RAG Pipeline)

import os
import json
from google import genai
from google.genai import types
from qdrant_client import QdrantClient
from dotenv import load_dotenv

load_dotenv()

# Config
COLLECTION_NAME = "optisigns_articles"
EMBEDDING_MODEL = "gemini-embedding-001"
QDRANT_URL = os.environ.get("QDRANT_URL", "").strip()
if not QDRANT_URL:
    QDRANT_URL = "http://localhost:6333"

if os.environ.get("GITHUB_ACTIONS") == "true" and ("localhost" in QDRANT_URL or QDRANT_URL == ""):
    raise ValueError(f"\n[LỖI NGHIÊM TRỌNG] Github Actions không nhận được QDRANT_URL. "
                     f"\nHãy kiểm tra lại trang Github: Settings -> Secrets and variables -> Actions. "
                     f"\nĐảm bảo lưu ở mục 'Repository secrets', KHÔNG PHẢI mục 'Environment secrets' hay 'Variables'.")
TOP_K = 5  # So luong chunks lien quan nhat de lay ra

# Khoi tao clients
gemini_client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
qdrant_api_key = os.environ.get("QDRANT_API_KEY", None)
qdrant_client = QdrantClient(url=QDRANT_URL, api_key=qdrant_api_key)
SYSTEM_PROMPT = """You are OptiBot, the customer-support bot for OptiSigns.com.
• Tone: helpful, factual, concise.
• Only answer using the uploaded docs.
• Max 5 bullet points; else link to the doc.
• Cite up to 3 "Article URL:" lines per reply."""


def get_embedding(text):
    """Lay embedding vector tu Gemini API"""
    result = gemini_client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text
    )
    return result.embeddings[0].values


def search_relevant_chunks(question):
    """Tim kiem cac chunks lien quan nhat tu Qdrant bang Semantic Search"""
    try:
        # Kiem tra collection co ton tai va co du lieu khong
        collection_info = qdrant_client.get_collection(COLLECTION_NAME)
        if collection_info.points_count == 0:
            return []
    except Exception:
        return []

    # Embedding cau hoi
    question_vector = get_embedding(question)

    # Tim kiem trong Qdrant
    results = qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        query=question_vector,
        limit=TOP_K,
        with_payload=True
    )

    return results.points


def build_context(chunks):
    """Xay dung context tu cac chunks tim duoc"""
    if not chunks:
        return ""

    context_parts = []
    seen_titles = set()
    
    for chunk in chunks:
        payload = chunk.payload
        title = payload.get("title", "Unknown")
        url = payload.get("url", "")
        text = payload.get("text", "")
        
        # Danh dau cac bai da xuat hien
        if title not in seen_titles:
            context_parts.append(f"--- Document: {title} ---")
            if url:
                context_parts.append(f"Article URL: {url}")
            seen_titles.add(title)
        
        context_parts.append(text)
        context_parts.append("")  # Dong trong de phan cach

    return "\n".join(context_parts)


def ask_question(question):
    """Gui cau hoi qua RAG Pipeline: Search Qdrant → Build Context → Gemini tra loi"""
    print(f"\nQuestion: {question}")
    print("-" * 60)

    # Buoc 1: Tim kiem chunks lien quan tu Qdrant
    chunks = search_relevant_chunks(question)
    
    # Buoc 2: Neu khong co du lieu, chan luon (Short-circuit)
    if not chunks:
        answer = "I don't know because no relevant documents were found."
        print(f"Answer:\n{answer}")
        return answer

    # Buoc 3: Xay dung context tu cac chunks
    context = build_context(chunks)
    print(f"  [RAG] Found {len(chunks)} relevant chunks from Qdrant")

    # Buoc 4: Gui context + cau hoi cho Gemini (co retry khi bi rate limit)
    prompt = (
        f"Context documents:\n{context}\n\n"
        f"Based ONLY on the context documents above, answer the following question: '{question}'\n\n"
        f"If the answer is not found in the context, reply with: "
        f"'I don't know because no relevant documents were found.' "
        f"DO NOT use outside knowledge."
    )

    import time
    models_to_try = ["gemini-2.5-flash-lite", "gemini-flash-latest", "gemini-3.5-flash"]
    
    for model_name in models_to_try:
        for attempt in range(3):
            try:
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.2,
                    )
                )
                print(f"Answer:\n{response.text}")
                return response.text
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "503" in error_str or "UNAVAILABLE" in error_str:
                    wait_time = (attempt + 1) * 10  # 10s, 20s, 30s
                    print(f"  [API ERROR {model_name}] Waiting {wait_time}s ({attempt+1}/3) - {error_str.split('.')[0]}...")
                    time.sleep(wait_time)
                else:
                    print(f"Answer:\nError: {e}")
                    return f"Error: {e}"
        print(f"  Model {model_name} exhausted, trying next...")
    
    print("Answer:\nFailed after all retries.")
    return "Failed after retries"


def main():
    print("=" * 60)
    print("OptiBot Test - Qdrant RAG + Gemini API")
    print("=" * 60)

    # Kiem tra Qdrant co du lieu khong
    try:
        info = qdrant_client.get_collection(COLLECTION_NAME)
        point_count = info.points_count
        print(f"Qdrant collection '{COLLECTION_NAME}': {point_count} chunks")
        if point_count == 0:
            print("\n[CẢNH BÁO] Qdrant chưa có dữ liệu! AI sẽ không thể trả lời.")
    except Exception:
        print(f"\n[CẢNH BÁO] Collection '{COLLECTION_NAME}' chưa tồn tại! Hãy chạy main.py trước.")

    import time
    # Cau hoi bat buoc theo de bai (sanity check)
    ask_question("How do I add a YouTube video?")
    
    print("\n[Delay 15s để tránh Google Rate Limit...]")
    time.sleep(15)

    # Test them
    ask_question("How do I set up a new screen?")
    
    print("\n[Delay 15s để tránh Google Rate Limit...]")
    time.sleep(15)
    
    ask_question("What devices are supported by OptiSigns?")

    print("\n" + "=" * 60)
    print("All tests completed!")


if __name__ == "__main__":
    main()
