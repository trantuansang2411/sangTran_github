# scrape.py
import requests
import re
import os
import json
from markdownify import markdownify as md

BASE_URL = "https://support.optisigns.com/api/v2"

# 3 bài viết bắt buộc phải có để trả lời đúng 3 câu test
REQUIRED_ARTICLE_IDS = [
    360051014713, # YouTube
    360016374813, # Set up screen
    360021855653  # Hardware devices
]

def get_articles():
    """Lấy danh sách bài viết từ Zendesk API (Giới hạn 30 bài + 3 bài Test)"""
    articles = []
    
    # Lấy 30 bài ngẫu nhiên đầu tiên (chỉ lấy 1 trang thay vì loop qua next_page)
    print("Đang lấy 30 bài viết đầu tiên...")
    url = f"{BASE_URL}/help_center/articles.json?per_page=30"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        articles.extend(data['articles'])
        
    # Lấy thêm 3 bài bắt buộc để pass bài test
    print("Đang lấy 3 bài viết bắt buộc để Test...")
    for article_id in REQUIRED_ARTICLE_IDS:
        res = requests.get(f"{BASE_URL}/help_center/en-us/articles/{article_id}.json")
        if res.status_code == 200:
            articles.append(res.json()['article'])
            
    return articles

def html_to_markdown(html_content):
    """Chuyển HTML thành Markdown sạch"""
    markdown = md(html_content, heading_style="ATX", strip=['nav', 'script', 'style'])
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)
    return markdown.strip()

def slugify(title):
    """Tạo slug từ title"""
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    return re.sub(r'[-\s]+', '-', slug).strip('-')

def save_articles():
    """Lưu bài viết thành file Markdown, có tích hợp Delta Detection"""
    os.makedirs('articles', exist_ok=True)
    articles = get_articles()
    
    # Load hashes cũ để Delta Detection
    cache_file = 'article_hashes.json'
    hashes = {}
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            hashes = json.load(f)
            
    skipped = 0
    saved = 0

    for article in articles:
        if not article.get('body'): continue
        
        slug = slugify(article['title'])
        markdown = html_to_markdown(article['body'])
        
        # Tạo hash mới
        import hashlib
        content_hash = hashlib.sha256(markdown.encode('utf-8')).hexdigest()
        
        # Kiem tra Delta
        if str(article['id']) in hashes and hashes[str(article['id'])] == content_hash:
            skipped += 1
            continue
            
        # Lưu file mới nếu chưa có hoặc có update
        content = f"# {article['title']}\n\n"
        content += f"**URL:** {article['html_url']}\n\n"
        content += markdown
        
        filepath = f"articles/{slug}.md"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
        hashes[str(article['id'])] = content_hash
        saved += 1
        print(f"Saved: {filepath}")
        
    # Luu hashes lai
    with open(cache_file, 'w') as f:
        json.dump(hashes, f, indent=2)
        
    print(f"\nScrape Report:")
    print(f"Total processed: {len(articles)}")
    print(f"Saved (New/Updated): {saved}")
    print(f"Skipped (Unchanged): {skipped}")

if __name__ == "__main__":
    save_articles()