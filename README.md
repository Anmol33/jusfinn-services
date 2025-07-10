# JusFinn Services API

A FastAPI backend with MongoDB integration and Google OAuth2 authentication.

## Features

- FastAPI REST API
- MongoDB database integration using Motor (async driver)
- Google OAuth2 authentication
- User management with CRUD operations
- Automatic token management and refresh
- Comprehensive API documentation

## Prerequisites

- Python 3.8+
- MongoDB (local or cloud instance)
- Google OAuth2 credentials

## Setup

### 1. Clone the repository
```bash
git clone <repository-url>
cd jusfinn-services
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up environment variables

**Option 1: Use the setup script (Recommended)**
```bash
python setup_env.py
```

**Option 2: Manual setup**
Copy the environment template and configure your settings:
```bash
cp env.example .env
```

Edit `.env` file with your configuration:
```env
# MongoDB Configuration
MONGODB_URL=mongodb+srv://<db_username>:<db_password>@cluster0.wdorp9f.mongodb.net/?retryWrites=true&w=majority
DATABASE_NAME=jusfinn
USER_MONGO_COLLECTION=user

# Google OAuth2 Configuration
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# JWT Configuration
JWT_SECRET_KEY=your_super_secret_jwt_key_change_this_in_production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Server Configuration
HOST=0.0.0.0
PORT=8000
```

### 4. Set up Google OAuth2

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google+ API
4. Go to Credentials → Create Credentials → OAuth 2.0 Client IDs
5. Configure authorized redirect URIs:
   - `http://localhost:8000/auth/google/callback` (for development)
   - `https://yourdomain.com/auth/google/callback` (for production)
6. Copy the Client ID and Client Secret to your `.env` file

### 5. Configure MongoDB Atlas
The application is configured to use MongoDB Atlas cloud database.

**Setup MongoDB Atlas:**
1. Replace `<db_username>` and `<db_password>` in the `MONGODB_URL` with your actual MongoDB Atlas credentials
2. Make sure your IP address is whitelisted in MongoDB Atlas Network Access
3. Ensure your database user has appropriate permissions (readWrite on your database)

## Running the Application

### Method 1: Using the Python runner script (Recommended)
```bash
python run_with_env.py
```

### Method 2: Using shell scripts

**For macOS/Linux:**
```bash
chmod +x run.sh
./run.sh
```

**For Windows:**
```cmd
run.bat
```

### Method 3: Manual environment variable setup

**macOS/Linux:**
```bash
# Load environment variables and run
export $(grep -v '^#' .env | xargs)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Windows:**
```cmd
# Load environment variables and run
for /f "tokens=1,2 delims==" %a in (.env) do set "%a=%b"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Method 4: Direct uvicorn (requires .env file)
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API Documentation

Once the server is running, you can access:
- Interactive API docs: http://localhost:8000/docs
- ReDoc documentation: http://localhost:8000/redoc

## API Endpoints

### Authentication

#### GET /auth/google/login
Get Google OAuth2 authorization URL.

**Response:**
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
}
```

#### GET /auth/google/callback
Handle Google OAuth2 callback and save user data.

**Parameters:**
- `code` (string): Authorization code from Google

**Response:**
```json
{
  "id": "user_id",
  "email": "user@example.com",
  "name": "John Doe",
  "given_name": "John",
  "family_name": "Doe",
  "picture": "https://example.com/picture.jpg",
  "locale": "en",
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T10:00:00Z"
}
```

#### GET /auth/google/redirect
Redirect to Google OAuth2 authorization URL.

### Users

#### GET /users/
Get all users (without sensitive data).

#### GET /users/{user_id}
Get a specific user by ID.

#### DELETE /users/{user_id}
Delete a user by ID.

### Health Check

#### GET /health
Health check endpoint.

## Project Structure

```
jusfinn-services/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration settings
│   ├── database.py          # MongoDB connection
│   ├── models.py            # Pydantic models
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py         # Authentication endpoints
│   │   └── users.py        # User management endpoints
│   └── services/
│       ├── __init__.py
│       ├── google_oauth.py  # Google OAuth2 service
│       └── user_service.py  # User data operations
├── requirements.txt
├── env.example
└── README.md
```

## Database Schema

### Users Collection
```json
{
  "_id": "ObjectId",
  "google_id": "string",
  "email": "string",
  "name": "string",
  "given_name": "string",
  "family_name": "string",
  "picture": "string",
  "locale": "string",
  "access_token": "string",
  "refresh_token": "string",
  "token_expires_at": "datetime",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

## Security Features

- OAuth2 authentication with Google
- Secure token storage
- Automatic token refresh
- CORS middleware for cross-origin requests
- Input validation with Pydantic models

## Development

### Adding New Endpoints
1. Create a new router in `app/routers/`
2. Add the router to `app/main.py`
3. Update this README with endpoint documentation

### Adding New Services
1. Create a new service in `app/services/`
2. Import and use in routers as needed

## Production Deployment

1. Set up a production MongoDB instance
2. Configure proper CORS origins
3. Use environment variables for all sensitive data
4. Set up proper logging
5. Use a production ASGI server like Gunicorn with Uvicorn workers

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Add your license here] 