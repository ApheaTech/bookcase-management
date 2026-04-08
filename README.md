# Bookcase Backend

A FastAPI-based backend service that provides book information based on ISBN numbers.

## Features

- **Caching**: Stores book information in a database to avoid repeated API calls
- **External API Integration**: Fetches book data from Open Library API
- **RESTful API**: Simple and intuitive API interface

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy environment variables:
```bash
cp .env.example .env
```

3. Run the server:
```bash
uvicorn main:app --reload
```

## API Usage

### Get Book by ISBN

**Endpoint**: `GET /book/{isbn}`

**Example**:
```bash
curl http://localhost:8000/book/9780134685991
```

**Response**:
```json
{
  "isbn": "9780134685991",
  "title": "Effective Python: 90 Specific Ways to Write Better Python",
  "authors": "Brett Slatkin",
  "publisher": "Addison-Wesley Professional",
  "publish_date": "2019-05-14",
  "pages": 448,
  "language": "eng",
  "cover_url": "https://covers.openlibrary.org/b/id/123456-M.jpg",
  "description": "...",
  "id": 1,
  "created_at": "2023-12-01T12:00:00Z",
  "updated_at": null
}
```

## Technology Stack

- **FastAPI**: Modern, fast (high-performance) web framework for building APIs
- **SQLAlchemy**: SQL toolkit and Object-Relational Mapping (ORM)
- **SQLite**: Lightweight database for storing book information
- **Requests**: HTTP library for making external API calls

## Environment Variables

- `DATABASE_URL`: Database connection URL (default: `sqlite:///./bookcase.db`)
- `EXTERNAL_API_URL`: External API URL for fetching book data (default: `https://openlibrary.org/api/books`)

## License

MIT