import json
import time
import hashlib
import threading
import uuid
import queue
from flask import Flask, jsonify, request, send_from_directory, make_response
import sqlite3
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)
DATABASE = os.path.join(BASE_DIR, "bookcase.db")
FRONTEND_DIST = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend", "dist"))
DEFAULT_CORS_ORIGINS = "http://127.0.0.1:3000,http://localhost:3000,http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8001,http://localhost:8001"
ANALYSIS_WORKER_CONCURRENCY = max(1, int(os.getenv("ANALYSIS_WORKER_CONCURRENCY", "1")))

from tos_client import tos_client
from llm_adapter import LLMAdapterError
from reading_agent import ReadingPreferenceAgent

reading_preference_agent = ReadingPreferenceAgent()
analysis_task_queue = queue.Queue()
analysis_workers_started = False
analysis_workers_lock = threading.Lock()


def get_allowed_origins():
    configured = os.getenv("CORS_ALLOW_ORIGINS", DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


def is_api_request(path):
    return path.startswith("/admin/api/") or path.startswith("/agent/") or path.startswith("/book/")


def resolve_cors_origin():
    request_origin = request.headers.get("Origin")
    allowed_origins = get_allowed_origins()
    if not request_origin:
        return None
    if "*" in allowed_origins:
        return "*"
    if request_origin in allowed_origins:
        return request_origin
    return None


def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


@app.before_request
def handle_preflight():
    if request.method == "OPTIONS" and is_api_request(request.path):
        response = make_response("", 204)
        return add_cors_headers(response)


@app.after_request
def add_cors_headers(response):
    if not is_api_request(request.path):
        return response

    allowed_origin = resolve_cors_origin()
    if not allowed_origin:
        return response

    response.headers["Access-Control-Allow-Origin"] = allowed_origin
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Max-Age"] = "86400"
    response.headers["Vary"] = "Origin"
    return response

def init_db():
    with get_connection() as conn:
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
                cover_url_tos TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                books_hash TEXT UNIQUE NOT NULL,
                book_titles_json TEXT NOT NULL,
                analysis TEXT NOT NULL,
                provider TEXT,
                model TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_tasks (
                task_id TEXT PRIMARY KEY,
                books_hash TEXT NOT NULL,
                book_titles_json TEXT NOT NULL,
                status TEXT NOT NULL,
                analysis TEXT,
                provider TEXT,
                model TEXT,
                error_message TEXT,
                cache_hit INTEGER DEFAULT 0,
                result_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(result_id) REFERENCES analysis_results(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS llm_usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                reasoning_tokens INTEGER DEFAULT 0,
                raw_response_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def get_book_from_db(isbn):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM books WHERE isbn = ?', (isbn,))
        book = cursor.fetchone()
        if book:
            result = {
                'id': book[0],
                'isbn': book[1],
                'title': book[2],
                'authors': book[3],
                'publisher': book[4],
                'publish_date': book[5],
                'pages': book[6],
                'language': book[7],
                'cover_url': book[8],
                'cover_url_tos': book[9],
                'description': book[10],
                'created_at': book[11],
                'updated_at': book[12]
            }
            # 如果存在 TOS 图片地址，优先使用
            if result.get('cover_url_tos'):
                result['cover_url'] = result['cover_url_tos']
            return result
    return None

def save_book_to_db(book_data):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO books 
            (isbn, title, authors, publisher, publish_date, pages, language, cover_url, cover_url_tos, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            book_data['isbn'],
            book_data['title'],
            book_data['authors'],
            book_data['publisher'],
            book_data['publish_date'],
            book_data['pages'],
            book_data['language'],
            book_data.get('cover_url'),
            book_data.get('cover_url_tos'),
            book_data['description']
        ))
        conn.commit()


def normalize_book_titles(payload):
    book_titles = payload.get("book_titles") or payload.get("books") or []
    if not isinstance(book_titles, list) or not book_titles:
        raise ValueError("Field 'book_titles' must be a non-empty list")

    normalized_titles = []
    for title in book_titles:
        normalized_title = str(title).strip()
        if not normalized_title:
            raise ValueError("Each item in 'book_titles' must be a non-empty string")
        normalized_titles.append(normalized_title)

    return normalized_titles


def compute_books_hash(book_titles):
    canonical_titles = sorted(book_titles)
    canonical_json = json.dumps(canonical_titles, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def get_cached_analysis_result(books_hash):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT id, books_hash, book_titles_json, analysis, provider, model, created_at, updated_at
            FROM analysis_results
            WHERE books_hash = ?
            ''',
            (books_hash,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_unfinished_task(books_hash):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT task_id, books_hash, status, created_at, updated_at
            FROM analysis_tasks
            WHERE books_hash = ? AND status IN ('pending', 'processing')
            ORDER BY created_at DESC
            LIMIT 1
            ''',
            (books_hash,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def create_analysis_task(book_titles, books_hash, status="pending", cache_hit=0, cached_result=None):
    task_id = str(uuid.uuid4())
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO analysis_tasks
            (task_id, books_hash, book_titles_json, status, analysis, provider, model, error_message, cache_hit, result_id, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''',
            (
                task_id,
                books_hash,
                json.dumps(book_titles, ensure_ascii=False),
                status,
                cached_result["analysis"] if cached_result else None,
                cached_result["provider"] if cached_result else None,
                cached_result["model"] if cached_result else None,
                None,
                cache_hit,
                cached_result["id"] if cached_result else None,
            ),
        )
        conn.commit()
    return task_id


def update_task_status(task_id, status, analysis=None, provider=None, model=None, error_message=None, cache_hit=None, result_id=None):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE analysis_tasks
            SET status = ?,
                analysis = COALESCE(?, analysis),
                provider = COALESCE(?, provider),
                model = COALESCE(?, model),
                error_message = ?,
                cache_hit = COALESCE(?, cache_hit),
                result_id = COALESCE(?, result_id),
                updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
            ''',
            (status, analysis, provider, model, error_message, cache_hit, result_id, task_id),
        )
        conn.commit()


def save_analysis_result(books_hash, book_titles, result):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO analysis_results (books_hash, book_titles_json, analysis, provider, model, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(books_hash) DO UPDATE SET
                book_titles_json = excluded.book_titles_json,
                analysis = excluded.analysis,
                provider = excluded.provider,
                model = excluded.model,
                updated_at = CURRENT_TIMESTAMP
            ''',
            (
                books_hash,
                json.dumps(book_titles, ensure_ascii=False),
                result["analysis"],
                result["provider"],
                result["model"],
            ),
        )
        conn.commit()
        cursor.execute(
            '''
            SELECT id, books_hash, book_titles_json, analysis, provider, model, created_at, updated_at
            FROM analysis_results
            WHERE books_hash = ?
            ''',
            (books_hash,),
        )
        row = cursor.fetchone()
        return dict(row)


def get_analysis_task(task_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT task_id, books_hash, book_titles_json, status, analysis, provider, model,
                   error_message, cache_hit, result_id, created_at, updated_at
            FROM analysis_tasks
            WHERE task_id = ?
            ''',
            (task_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_queue_position(task):
    if not task or task["status"] not in {"pending", "processing"}:
        return None

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT COUNT(*) AS ahead_count
            FROM analysis_tasks
            WHERE status IN ('pending', 'processing')
              AND (
                created_at < ?
                OR (created_at = ? AND task_id <= ?)
              )
            ''',
            (task["created_at"], task["created_at"], task["task_id"]),
        )
        row = cursor.fetchone()
        return int(row["ahead_count"]) if row else None


def serialize_task(task):
    serialized = {
        "task_id": task["task_id"],
        "status": task["status"],
        "cache_hit": bool(task["cache_hit"]),
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
    }

    queue_position = get_queue_position(task)
    if queue_position is not None:
        serialized["queue_position"] = queue_position

    if task.get("analysis"):
        book_titles = json.loads(task["book_titles_json"]) if task.get("book_titles_json") else []
        serialized["result"] = {
            "analysis": task["analysis"],
            "provider": task["provider"],
            "model": task["model"],
            "input_summary": {
                "book_titles_count": len(book_titles),
            },
        }

    if task.get("error_message"):
        serialized["error"] = task["error_message"]

    return serialized


def log_api_response(endpoint, status_code, payload):
    print(
        f"[INFO] API response {endpoint} status={status_code}: "
        + json.dumps(payload, ensure_ascii=False)
    )


def serialize_book(book_row):
    return {
        "id": book_row["id"],
        "isbn": book_row["isbn"],
        "title": book_row["title"],
        "authors": book_row["authors"],
        "publisher": book_row["publisher"],
        "publish_date": book_row["publish_date"],
        "pages": book_row["pages"],
        "language": book_row["language"],
        "cover_url": book_row["cover_url_tos"] or book_row["cover_url"],
        "cover_url_tos": book_row["cover_url_tos"],
        "description": book_row["description"],
        "created_at": book_row["created_at"],
        "updated_at": book_row["updated_at"],
    }


def get_usage_summary():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT provider,
                   model,
                   COUNT(*) AS request_count,
                   COALESCE(SUM(input_tokens), 0) AS input_tokens,
                   COALESCE(SUM(output_tokens), 0) AS output_tokens,
                   COALESCE(SUM(total_tokens), 0) AS total_tokens,
                   COALESCE(SUM(reasoning_tokens), 0) AS reasoning_tokens,
                   MAX(created_at) AS last_used_at
            FROM llm_usage_logs
            GROUP BY provider, model
            ORDER BY total_tokens DESC, provider ASC, model ASC
            '''
        )
        models = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            '''
            SELECT provider,
                   COUNT(*) AS request_count,
                   COALESCE(SUM(input_tokens), 0) AS input_tokens,
                   COALESCE(SUM(output_tokens), 0) AS output_tokens,
                   COALESCE(SUM(total_tokens), 0) AS total_tokens,
                   COALESCE(SUM(reasoning_tokens), 0) AS reasoning_tokens,
                   MAX(created_at) AS last_used_at
            FROM llm_usage_logs
            GROUP BY provider
            ORDER BY total_tokens DESC, provider ASC
            '''
        )
        providers = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            '''
            SELECT COUNT(*) AS request_count,
                   COALESCE(SUM(input_tokens), 0) AS input_tokens,
                   COALESCE(SUM(output_tokens), 0) AS output_tokens,
                   COALESCE(SUM(total_tokens), 0) AS total_tokens,
                   COALESCE(SUM(reasoning_tokens), 0) AS reasoning_tokens,
                   MAX(created_at) AS last_used_at
            FROM llm_usage_logs
            '''
        )
        totals = dict(cursor.fetchone())

    return {
        "totals": totals,
        "providers": providers,
        "models": models,
    }


def get_books_admin_data(limit=100, offset=0, search=""):
    with get_connection() as conn:
        cursor = conn.cursor()
        params = []
        where_clause = ""
        if search:
            where_clause = '''
                WHERE isbn LIKE ? OR title LIKE ? OR authors LIKE ? OR publisher LIKE ?
            '''
            search_term = f"%{search}%"
            params.extend([search_term, search_term, search_term, search_term])

        count_query = f"SELECT COUNT(*) AS total FROM books {where_clause}"
        cursor.execute(count_query, params)
        total = cursor.fetchone()["total"]

        list_query = f'''
            SELECT id, isbn, title, authors, publisher, publish_date, pages, language,
                   cover_url, cover_url_tos, description, created_at, updated_at
            FROM books
            {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
        '''
        cursor.execute(list_query, params + [limit, offset])
        books = [serialize_book(row) for row in cursor.fetchall()]

    return {
        "items": books,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total,
        },
    }


def process_analysis_task(task_id, book_titles, books_hash):
    started_at = time.time()
    try:
        print(f"[INFO] Reading preference task {task_id} started")
        update_task_status(task_id, "processing")

        cached_result = get_cached_analysis_result(books_hash)
        if cached_result:
            update_task_status(
                task_id,
                "completed",
                analysis=cached_result["analysis"],
                provider=cached_result["provider"],
                model=cached_result["model"],
                cache_hit=1,
                result_id=cached_result["id"],
            )
            print(f"[INFO] Reading preference task {task_id} completed from cache in {time.time() - started_at:.2f}s")
            return

        result = reading_preference_agent.analyze({"book_titles": book_titles})
        saved_result = save_analysis_result(books_hash, book_titles, result)
        update_task_status(
            task_id,
            "completed",
            analysis=result["analysis"],
            provider=result["provider"],
            model=result["model"],
            cache_hit=0,
            result_id=saved_result["id"],
        )
        print(f"[INFO] Reading preference task {task_id} finished in {time.time() - started_at:.2f}s")
    except Exception as exc:
        update_task_status(task_id, "failed", error_message=str(exc))
        print(f"[ERROR] Reading preference task {task_id} failed after {time.time() - started_at:.2f}s: {exc}")


def analysis_worker_loop(worker_index):
    while True:
        task_payload = analysis_task_queue.get()
        try:
            if task_payload is None:
                continue
            task_id, book_titles, books_hash = task_payload
            process_analysis_task(task_id, book_titles, books_hash)
        finally:
            analysis_task_queue.task_done()


def enqueue_task(task_id, book_titles, books_hash):
    analysis_task_queue.put((task_id, book_titles, books_hash))


def requeue_pending_tasks():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE analysis_tasks
            SET status = 'pending',
                updated_at = CURRENT_TIMESTAMP
            WHERE status = 'processing'
            '''
        )
        conn.commit()
        cursor.execute(
            '''
            SELECT task_id, book_titles_json, books_hash
            FROM analysis_tasks
            WHERE status = 'pending'
            ORDER BY created_at ASC, task_id ASC
            '''
        )
        rows = cursor.fetchall()

    for row in rows:
        enqueue_task(row["task_id"], json.loads(row["book_titles_json"]), row["books_hash"])


def ensure_analysis_workers_started():
    global analysis_workers_started
    with analysis_workers_lock:
        if analysis_workers_started:
            return
        requeue_pending_tasks()
        for worker_index in range(ANALYSIS_WORKER_CONCURRENCY):
            worker = threading.Thread(
                target=analysis_worker_loop,
                args=(worker_index,),
                daemon=True,
                name=f"analysis-worker-{worker_index + 1}",
            )
            worker.start()
        analysis_workers_started = True
        print(f"[INFO] Analysis worker queue started with concurrency={ANALYSIS_WORKER_CONCURRENCY}")

def upload_cover_to_tos(isbn: str, cover_url: str) -> str:
    """
    将封面图片上传到 TOS 对象存储
    
    Args:
        isbn: 图书 ISBN
        cover_url: 原始封面图片 URL
        
    Returns:
        TOS 上的图片访问 URL
    """
    if not cover_url:
        return None
    
    # 生成 object_key: covers/{isbn}/{timestamp}.jpg
    import time
    timestamp = int(time.time())
    # 从原始 URL 提取扩展名
    from urllib.parse import urlparse
    parsed_url = urlparse(cover_url)
    path = parsed_url.path
    ext = os.path.splitext(path)[1]
    if not ext or ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
        ext = '.jpg'
    
    object_key = f"covers/{isbn}/{timestamp}{ext}"
    
    # 上传到 TOS
    tos_url = tos_client.upload_image_from_url(cover_url, object_key)
    return tos_url

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

    # 上传封面图片到 TOS
    original_cover_url = book_data.get('cover_url')
    if original_cover_url:
        print(f"[INFO] Uploading cover image to TOS for ISBN: {isbn}")
        tos_cover_url = upload_cover_to_tos(isbn, original_cover_url)
        if tos_cover_url:
            book_data['cover_url_tos'] = tos_cover_url
            print(f"[INFO] Cover image uploaded to TOS: {tos_cover_url}")
        else:
            print(f"[WARNING] Failed to upload cover image to TOS, using original URL")

    save_book_to_db(book_data)
    book = get_book_from_db(isbn)
    return app.response_class(
        response=json.dumps(book, ensure_ascii=False),
        status=200,
        mimetype='application/json; charset=utf-8'
    )

@app.route('/')
def index():
    return jsonify(
        {
            'message': 'Welcome to Bookcase API',
            'capabilities': [
                'book_lookup',
                'reading_preference_analysis'
            ]
        }
    )


@app.route('/admin/api/usage')
def admin_usage():
    response_payload = get_usage_summary()
    log_api_response('/admin/api/usage', 200, response_payload)
    return jsonify(response_payload)


@app.route('/admin/api/books')
def admin_books():
    try:
        limit = max(1, min(int(request.args.get("limit", 100)), 200))
        offset = max(0, int(request.args.get("offset", 0)))
        search = str(request.args.get("search", "")).strip()
    except ValueError:
        response_payload = {"error": "Invalid pagination parameters"}
        log_api_response('/admin/api/books', 400, response_payload)
        return jsonify(response_payload), 400

    response_payload = get_books_admin_data(limit=limit, offset=offset, search=search)
    log_api_response('/admin/api/books', 200, response_payload)
    return jsonify(response_payload)


@app.route('/admin')
def admin_index():
    if os.path.exists(os.path.join(FRONTEND_DIST, "index.html")):
        return send_from_directory(FRONTEND_DIST, "index.html")
    return jsonify({"error": "Frontend build not found"}), 404


@app.route('/admin/<path:path>')
def admin_assets(path):
    target_path = os.path.join(FRONTEND_DIST, path)
    if os.path.exists(target_path):
        return send_from_directory(FRONTEND_DIST, path)
    if os.path.exists(os.path.join(FRONTEND_DIST, "index.html")):
        return send_from_directory(FRONTEND_DIST, "index.html")
    return jsonify({"error": "Frontend build not found"}), 404


@app.route('/agent/reading-preferences/analyze', methods=['POST'])
def analyze_reading_preferences():
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({'error': 'Request body must be valid JSON'}), 400

    started_at = time.time()
    try:
        print("[INFO] Reading preference analysis started")
        result = reading_preference_agent.analyze(payload)
        print(f"[INFO] Reading preference analysis finished in {time.time() - started_at:.2f}s")
        return jsonify(result)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except LLMAdapterError as exc:
        print(f"[ERROR] Reading preference analysis failed after {time.time() - started_at:.2f}s: {exc}")
        return jsonify({'error': str(exc)}), 503
    except Exception as exc:
        print(f'[ERROR] Failed to analyze reading preferences after {time.time() - started_at:.2f}s: {exc}')
        return jsonify({'error': 'Failed to analyze reading preferences'}), 500


@app.route('/agent/reading-preferences/tasks', methods=['POST'])
def create_reading_preference_task():
    payload = request.get_json(silent=True)
    if not payload:
        response_payload = {'error': 'Request body must be valid JSON'}
        log_api_response('/agent/reading-preferences/tasks', 400, response_payload)
        return jsonify(response_payload), 400

    try:
        ensure_analysis_workers_started()
        book_titles = normalize_book_titles(payload)
        books_hash = compute_books_hash(book_titles)

        cached_result = get_cached_analysis_result(books_hash)
        if cached_result:
            task_id = create_analysis_task(
                book_titles=book_titles,
                books_hash=books_hash,
                status="completed",
                cache_hit=1,
                cached_result=cached_result,
            )
            task = get_analysis_task(task_id)
            response_payload = serialize_task(task)
            log_api_response('/agent/reading-preferences/tasks', 200, response_payload)
            return jsonify(response_payload), 200

        unfinished_task = get_unfinished_task(books_hash)
        if unfinished_task:
            task = get_analysis_task(unfinished_task["task_id"])
            response_payload = {
                **serialize_task(task),
                "reused_task": True,
            }
            log_api_response('/agent/reading-preferences/tasks', 202, response_payload)
            return jsonify(response_payload), 202

        task_id = create_analysis_task(book_titles=book_titles, books_hash=books_hash, status="pending")
        enqueue_task(task_id, book_titles, books_hash)

        task = get_analysis_task(task_id)
        response_payload = serialize_task(task)
        log_api_response('/agent/reading-preferences/tasks', 202, response_payload)
        return jsonify(response_payload), 202
    except ValueError as exc:
        response_payload = {'error': str(exc)}
        log_api_response('/agent/reading-preferences/tasks', 400, response_payload)
        return jsonify(response_payload), 400
    except Exception as exc:
        print(f"[ERROR] Failed to create reading preference task: {exc}")
        response_payload = {'error': 'Failed to create reading preference task'}
        log_api_response('/agent/reading-preferences/tasks', 500, response_payload)
        return jsonify(response_payload), 500


@app.route('/agent/reading-preferences/tasks/<task_id>', methods=['GET'])
def get_reading_preference_task(task_id):
    task = get_analysis_task(task_id)
    if not task:
        response_payload = {'error': 'Task not found'}
        log_api_response(f'/agent/reading-preferences/tasks/{task_id}', 404, response_payload)
        return jsonify(response_payload), 404
    response_payload = serialize_task(task)
    log_api_response(f'/agent/reading-preferences/tasks/{task_id}', 200, response_payload)
    return jsonify(response_payload)

init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8001, threaded=True)
