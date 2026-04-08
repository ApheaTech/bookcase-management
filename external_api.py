import requests
import os
from dotenv import load_dotenv
from typing import Dict, Optional

load_dotenv()

EXTERNAL_API_URL = os.getenv("EXTERNAL_API_URL", "https://openlibrary.org/api/books")

def get_book_from_external_api(isbn: str) -> Optional[Dict]:
    try:
        params = {
            "bibkeys": f"ISBN:{isbn}",
            "format": "json",
            "jscmd": "data"
        }
        response = requests.get(EXTERNAL_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        key = f"ISBN:{isbn}"
        if key not in data:
            return None
        
        book_data = data[key]
        return {
            "isbn": isbn,
            "title": book_data.get("title"),
            "authors": ", ".join([author["name"] for author in book_data.get("authors", [])]),
            "publisher": book_data.get("publishers", [{}])[0].get("name") if book_data.get("publishers") else None,
            "publish_date": book_data.get("publish_date"),
            "pages": book_data.get("number_of_pages"),
            "language": book_data.get("languages", [{}])[0].get("key", "").split("/")[-1] if book_data.get("languages") else None,
            "cover_url": book_data.get("cover", {}).get("medium"),
            "description": book_data.get("description", {}).get("value") if isinstance(book_data.get("description"), dict) else book_data.get("description")
        }
    except Exception as e:
        print(f"Error fetching book from external API: {e}")
        return None