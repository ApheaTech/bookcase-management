import requests
import json

def test_book_api(isbn):
    url = f'http://127.0.0.1:8001/book/{isbn}'
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        print(f"Success! ISBN: {isbn}")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return False

if __name__ == '__main__':
    print("Testing Book API with sample ISBNs...")
    print("=" * 50)
    
    test_book_api('9787212058937')
    print("\n" + "=" * 50)
    test_book_api('9780134685991')