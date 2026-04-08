# -*- coding: utf-8 -*-
import json
from flask import Flask, jsonify
import sqlite3
import requests
import os
from dotenv import load_dotenv
import sys
if hasattr(sys, 'setdefaultencoding'):
    reload(sys)
    sys.setdefaultencoding('utf8')

load_dotenv()

app = Flask(__name__)
DATABASE = 'bookcase.db'
EXTERNAL_API_URL = os.getenv("EXTERNAL_API_URL", "https://openlibrary.org/api/books")

def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                isbn TEXT UNIQUE NOT NULL,
                title TEXT,
                authors TEXT,
                publisher TEXT,
                publish_date TEXT,
                pages INTEGER,
                language TEXT,
                cover_url TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def get_book_from_db(isbn):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM books WHERE isbn = ?', (isbn,))
        book = cursor.fetchone()
        if book:
            return {
                'id': book[0],
                'isbn': book[1],
                'title': book[2],
                'authors': book[3],
                'publisher': book[4],
                'publish_date': book[5],
                'pages': book[6],
                'language': book[7],
                'cover_url': book[8],
                'description': book[9],
                'created_at': book[10],
                'updated_at': book[11]
            }
    return None

def save_book_to_db(book_data):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO books 
            (isbn, title, authors, publisher, publish_date, pages, language, cover_url, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            book_data['isbn'],
            book_data['title'],
            book_data['authors'],
            book_data['publisher'],
            book_data['publish_date'],
            book_data['pages'],
            book_data['language'],
            book_data['cover_url'],
            book_data['description']
        ))
        conn.commit()

def get_book_from_external_api(isbn):
    try:
        # 从环境变量获取API名称，默认使用配置文件中的default
        api_name = os.getenv('API_NAME', None)
        
        from api_adapter import APIAdapter
        adapter = APIAdapter(api_name=api_name)
        book_data = adapter.call_api(isbn)
        
        return book_data
        
    except Exception as e:
        print(f'[ERROR] Error fetching book from external API: {e}')
        return None

@app.route('/book/<isbn>')
def get_book(isbn):
    book = get_book_from_db(isbn)
    if book:
        return app.response_class(
            response=json.dumps(book, ensure_ascii=False),
            status=200,
            mimetype='application/json; charset=utf-8'
        )
    
    book_data = get_book_from_external_api(isbn)
    if not book_data:
        return app.response_class(
            response=json.dumps({'error': 'Book not found'}, ensure_ascii=False),
            status=404,
            mimetype='application/json; charset=utf-8'
        )
    
    save_book_to_db(book_data)
    book = get_book_from_db(isbn)
    return app.response_class(
        response=json.dumps(book, ensure_ascii=False),
        status=200,
        mimetype='application/json; charset=utf-8'
    )

@app.route('/')
def index():
    return jsonify({'message': 'Welcome to Bookcase API'})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=8001)