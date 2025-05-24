# KIT Web Backend

This is the backend service for the KIT Web application. It provides a REST API interface to the existing KIT functionality.

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
cd api
pip install -r requirements.txt
```

3. Create a `.env` file:
Copy `.env.example` to `.env` and fill in the required values:
- `SECRET_KEY`: A secure random string for JWT token generation
- `GEMINI_API_KEY`: Your Gemini API key
- Other configuration values as needed

## Running the Application

1. Start the development server:
```bash
cd api
uvicorn app:app --reload
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, you can access:
- Interactive API documentation: `http://localhost:8000/docs`
- Alternative API documentation: `http://localhost:8000/redoc`

## Project Structure

```
backend/
├── api/                    # API layer
│   ├── app.py             # Main FastAPI application
│   ├── routes/            # API route definitions
│   └── services/          # Service layer for KITCore integration
├── KITCore/               # Existing core functionality
└── KIT/                   # Existing AI agent
```

## Development

1. The API is built using FastAPI and follows REST principles
2. Authentication is handled using JWT tokens
3. The service layer provides a bridge between the API and existing KITCore functionality
4. CORS is configured to allow frontend development

## Testing

Run the test suite:
```bash
pytest
```

## Deployment

1. Set up a production database (PostgreSQL recommended)
2. Configure environment variables for production
3. Use a production-grade ASGI server (e.g., Gunicorn)
4. Set up proper CORS configuration for production domains 