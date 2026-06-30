# main.py - Daily job: scrape + delta detect + chunking + embedding + upsert to Qdrant

import hashlib
import json
import os
import logging
from dotenv import load_dotenv
from scrape import get_articles, slugify, html_to_markdown
from upload_vectorstore import upload_files

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

HASH_FILE = "article_hashes.json"
ARTICLES_DIR = "articles"


def load_hashes():
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_hashes(hashes):
    with open(HASH_FILE, 'w', encoding='utf-8') as f:
        json.dump(hashes, f, indent=2)


def compute_hash(content):
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def main():
    old_hashes = load_hashes()
    new_hashes = {}

    added = 0
    updated = 0
    skipped = 0

    # ========== BUOC 1: SCRAPE ==========
    logger.info("=" * 40)
    logger.info("BƯỚC 1: SCRAPING ARTICLES")
    logger.info("=" * 40)
    
    articles = get_articles()
    logger.info(f"Found {len(articles)} articles")

    os.makedirs(ARTICLES_DIR, exist_ok=True)

    for article in articles:
        if not article.get('body'):
            continue
            
        slug = slugify(article['title'])
        content = html_to_markdown(article['body'])
        content_hash = compute_hash(content)
        new_hashes[slug] = content_hash

        if slug not in old_hashes:
            # Bai moi - Luu file Markdown
            md_content = f"# {article['title']}\n\n**Article URL:** {article['html_url']}\n\n{content}"
            filepath = os.path.join(ARTICLES_DIR, f"{slug}.md")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md_content)
            logger.info(f"[NEW] {article['title']}")
            added += 1
        elif old_hashes[slug] != content_hash:
            # Bai cu nhung co cap nhat - Luu lai file Markdown
            md_content = f"# {article['title']}\n\n**Article URL:** {article['html_url']}\n\n{content}"
            filepath = os.path.join(ARTICLES_DIR, f"{slug}.md")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md_content)
            logger.info(f"[UPDATED] {article['title']}")
            updated += 1
        else:
            skipped += 1

    save_hashes(new_hashes)

    logger.info(f"Scrape Report: Added={added}, Updated={updated}, Skipped={skipped}")

    # ========== BUOC 2: UPLOAD TO QDRANT ==========
    if added > 0 or updated > 0:
        logger.info("")
        logger.info("=" * 40)
        logger.info("BƯỚC 2: CHUNKING + EMBEDDING → QDRANT")
        logger.info("=" * 40)
        upload_files()
    else:
        logger.info("")
        logger.info("Không có bài viết mới/cập nhật. Bỏ qua bước upload.")

    logger.info("")
    logger.info("=" * 40)
    logger.info("=== Daily Job Complete ===")
    logger.info(f"Total articles: {len(articles)}")
    logger.info(f"Added:   {added}")
    logger.info(f"Updated: {updated}")
    logger.info(f"Skipped: {skipped}")
    logger.info("=" * 40)


if __name__ == "__main__":
    main()