import asyncio
from datetime import datetime
from playwright.sync_api import sync_playwright
import requests
import json
from telegram import Bot
import re

# Telegram Bot Configuration
BOT_TOKEN = 'XXXX'  # Replace with your bot token
CHAT_ID = 'XXXX'  # Replace with your Telegram chat ID

# Configuration file path
BOOKMARK_FILE = "/home/debian/bookmark_bot/bookmarks.txt"
ARTICLE_LIMIT = 1  # Limit on the number of articles to summarize per run

# Function to send messages via Telegram
async def send_message_to_telegram(message):
    bot = Bot(token=BOT_TOKEN)
    
    # Escape special characters for Markdown
    def escape_markdown(text):
        escape_chars = r"_*[]()~`>#+-=|{}.!"
        return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

    # Escape the message
    escaped_message = escape_markdown(message)

    # Split message if it exceeds Telegram's 4096-character limit
    max_length = 4096
    if len(escaped_message) > max_length:
        chunks = [escaped_message[i:i + max_length] for i in range(0, len(escaped_message), max_length)]
        for chunk in chunks:
            await bot.send_message(chat_id=CHAT_ID, text=chunk, parse_mode="MarkdownV2")
    else:
        await bot.send_message(chat_id=CHAT_ID, text=escaped_message, parse_mode="MarkdownV2")

# Function to read bookmarks from the file
def read_bookmarks(file_path):
    try:
        with open(file_path, 'r') as file:
            bookmarks = []
            for line in file.readlines():
                url, date_added, too_large = line.strip().split(',')
                bookmarks.append({
                    "url": url,
                    "date_added": date_added,
                    "too_large": too_large == "true"
                })
            return bookmarks
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
        return []

# Function to remove a bookmark from the file
def remove_bookmark(file_path, url):
    bookmarks = read_bookmarks(file_path)
    for bookmark in bookmarks:
        if bookmark["url"] == url:
            bookmarks.remove(bookmark)
            break
    with open(file_path, "w") as file:
        for bookmark in bookmarks:
            file.write(f"{bookmark['url']},{bookmark['date_added']},{str(bookmark['too_large']).lower()}\n")

# Function to update the "too_large" flag
def update_size_flag(file_path, url, is_too_large):
    bookmarks = read_bookmarks(file_path)
    for bookmark in bookmarks:
        if bookmark["url"] == url:
            bookmark["too_large"] = is_too_large
            break
    with open(file_path, "w") as file:
        for bookmark in bookmarks:
            file.write(f"{bookmark['url']},{bookmark['date_added']},{str(bookmark['too_large']).lower()}\n")

# Scraping with Playwright
def scrape_website(url):
    print(f"Scraping website: {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/114.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        page.goto(url)
        page.wait_for_selector("body")
        
        # Extract visible content
        data = {
            "title": page.title(),
            "meta_description": page.evaluate("() => document.querySelector('meta[name=\"description\"]')?.content || 'No Description'"),
            "content": page.evaluate("() => document.body.innerText"),
        }
        browser.close()
        return data

# Check and update size flag
def check_and_update_size(file_path, url, content):
    token_limit = 60000  # Token limit for flagging too large
    token_count = len(content.split()) * 2  # Approximate token count using word count
    is_too_large = token_count >= token_limit
    update_size_flag(file_path, url, is_too_large)
    return is_too_large

# Summarization with External API
def summarize_with_external_api(data):
    api_url = "http://10.1.1.96:1234/v1/chat/completions"  # Endpoint from Script A
    payload = {
        "model": "llama 3.2 8b",
        "messages": [
            {
                "role": "system",
                "content": "Summarize the content of this webpage. Ensure all responses are in English."
            },
            {
                "role": "user",
                "content": f"Title: {data['title']}\n\nContent: {data['content']}",
            }
        ],
        "temperature": 0.7,
        "max_tokens": -1,
        "stream": False
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()
        summary = result.get("choices", [{}])[0].get("message", {}).get("content", "No summary available.")
        return summary
    except requests.RequestException as e:
        print(f"Error calling API: {e}")
        return "Error: Unable to summarize content."

# Main Function
def main():
    bookmarks = read_bookmarks(BOOKMARK_FILE)
    if not bookmarks:
        print("No URLs found in bookmarks file.")
        return

    summaries = []
    articles_processed = 0
    for bookmark in bookmarks:
        if articles_processed >= ARTICLE_LIMIT:
            break

        url = bookmark["url"]
        if bookmark["too_large"]:
            continue

        try:
            data = scrape_website(url)
            content = data["content"]
            if check_and_update_size(BOOKMARK_FILE, url, content):
                continue

            summary = summarize_with_external_api(data)
            if "Error" in summary:
                print(f"Marking URL {url} as too large due to summarization error.")
                update_size_flag(BOOKMARK_FILE, url, True)  # Mark as too large
                continue

            title_with_link = f"[{data['title']}]({url})"
            summaries.append(f"{title_with_link}\n\n{summary}\n{'-'*40}")
            remove_bookmark(BOOKMARK_FILE, url)
            articles_processed += 1
        except Exception as e:
            print(f"Error processing URL {url}: {e}")

    # Send summaries via Telegram
    if summaries:
        content = "\n\n".join(summaries)
        try:
            asyncio.run(send_message_to_telegram(content))
        except Exception as e:
            print(f"Error sending message to Telegram: {e}")
    else:
        try:
            asyncio.run(send_message_to_telegram("No summaries generated."))
        except Exception as e:
            print(f"Error sending message to Telegram: {e}")

if __name__ == "__main__":
    main()
