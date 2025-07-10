# OAuth2 Flow Implementation

This document describes the OAuth2 authorization code flow implementation for JusFinn.

## Flow Overview

### 1. Frontend Initiates Login
- User clicks "Sign in with Google" button
- Frontend calls `GET /auth/google/login` to get authorization URL
- Frontend redirects user to Google's authorization endpoint

### 2. Google Authorization
- User authenticates with Google
- Google redirects back to backend with authorization code
- Backend endpoint: `GET /auth/google/callback?code=...`

### 3. Backend Token Exchange
- Backend exchanges authorization code for access token
- Backend fetches user info from Google
- Backend creates/updates user in database
- Backend generates JWT token for the user

### 4. Frontend Callback
- Backend redirects to frontend with user data
- Frontend endpoint: `/auth/callback`
- Frontend stores authentication data and redirects to dashboard

## Security Features

### State Parameter
- Random state parameter generated for CSRF protection
- Included in authorization URL

### Token Validation
- Backend validates Google ID tokens
- JWT tokens for session management
- Secure token storage in localStorage

## API Endpoints

### GET /auth/google/login
Returns Google authorization URL for frontend to redirect to.

**Response:**
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
}
```

### GET /auth/google/callback
Handles Google OAuth callback and token exchange.

**Parameters:**
- `code` (string): Authorization code from Google
- `state` (string, optional): State parameter for CSRF protection

**Response:**
Redirects to frontend with user data or error.

### POST /auth/google/verify
Alternative endpoint for ID token verification (for future use).

## Frontend Routes

### /signin
Login page with Google OAuth button.

### /auth/callback
Handles OAuth callback from backend, stores authentication data.

## Configuration

### Google OAuth2 Settings
- Client ID: Configured in Google Cloud Console
- Client Secret: Stored securely in backend
- Redirect URI: `http://localhost:8000/auth/google/callback`

### CORS Configuration
- Frontend origins: `http://localhost:8080`, `http://127.0.0.1:8080`
- Credentials: Enabled
- Methods: All allowed
- Headers: All allowed

## Port Configuration
- Frontend: `http://localhost:8080`
- Backend: `http://localhost:8000`

## Testing the Flow

1. Start backend server: `uvicorn app.main:app --reload --port 8000`
2. Start frontend: `npm run dev`
3. Navigate to `http://localhost:8080/signin`
4. Click "Sign in with Google"
5. Complete Google authentication
6. Verify redirect to dashboard with user data

## Error Handling

- Invalid authorization codes
- Network errors during token exchange
- User creation/update failures
- JWT token generation errors

All errors are properly handled and redirected to frontend with appropriate error messages. 