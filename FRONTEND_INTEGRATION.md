# Frontend Integration Guide

This guide explains how to integrate your frontend with the Google OAuth2 authentication system.

## 🔐 **Authentication Flow Options**

### **Option 1: Redirect Flow (Recommended)**

#### **Backend Endpoints:**
- `GET /auth/google/login` - Get authorization URL
- `GET /auth/google/callback/redirect` - Handle callback and redirect to frontend
- `GET /auth/google/redirect` - Direct redirect to Google

#### **Frontend Implementation:**

```javascript
// React/Next.js Example
import { useEffect } from 'react';
import { useRouter } from 'next/router';

const LoginPage = () => {
  const router = useRouter();
  
  const handleGoogleLogin = async () => {
    try {
      // Get the authorization URL from backend
      const response = await fetch('http://localhost:8000/auth/google/login');
      const { authorization_url } = await response.json();
      
      // Redirect to Google
      window.location.href = authorization_url;
    } catch (error) {
      console.error('Login failed:', error);
    }
  };
  
  return (
    <div>
      <button onClick={handleGoogleLogin}>
        Login with Google
      </button>
    </div>
  );
};

// Dashboard page to handle the callback
const Dashboard = () => {
  const router = useRouter();
  
  useEffect(() => {
    // Check if we have authentication data in URL
    const urlParams = new URLSearchParams(window.location.search);
    const auth = urlParams.get('auth');
    const userData = urlParams.get('user');
    
    if (auth === 'success' && userData) {
      try {
        // Parse user data
        const user = JSON.parse(decodeURIComponent(userData));
        
        // Store user data and token
        localStorage.setItem('user', JSON.stringify(user));
        localStorage.setItem('access_token', user.access_token);
        
        // Clear URL parameters
        router.replace('/dashboard', undefined, { shallow: true });
        
        console.log('User authenticated:', user);
      } catch (error) {
        console.error('Failed to parse user data:', error);
      }
    } else if (auth === 'error') {
      const error = urlParams.get('error');
      console.error('Authentication failed:', error);
      // Handle error (show error message, redirect to login, etc.)
    }
  }, [router]);
  
  return (
    <div>
      <h1>Dashboard</h1>
      {/* Your dashboard content */}
    </div>
  );
};
```

#### **Vue.js Example:**

```javascript
// Login component
<template>
  <div>
    <button @click="handleGoogleLogin">Login with Google</button>
  </div>
</template>

<script>
export default {
  methods: {
    async handleGoogleLogin() {
      try {
        const response = await fetch('http://localhost:8000/auth/google/login');
        const { authorization_url } = await response.json();
        window.location.href = authorization_url;
      } catch (error) {
        console.error('Login failed:', error);
      }
    }
  }
}
</script>

// Dashboard component
<template>
  <div>
    <h1>Dashboard</h1>
    <div v-if="user">
      <p>Welcome, {{ user.name }}!</p>
      <img :src="user.picture" :alt="user.name" />
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      user: null
    }
  },
  mounted() {
    this.handleCallback();
  },
  methods: {
    handleCallback() {
      const urlParams = new URLSearchParams(window.location.search);
      const auth = urlParams.get('auth');
      const userData = urlParams.get('user');
      
      if (auth === 'success' && userData) {
        try {
          const user = JSON.parse(decodeURIComponent(userData));
          this.user = user;
          localStorage.setItem('user', JSON.stringify(user));
          localStorage.setItem('access_token', user.access_token);
          
          // Clear URL parameters
          this.$router.replace('/dashboard');
        } catch (error) {
          console.error('Failed to parse user data:', error);
        }
      }
    }
  }
}
</script>
```

### **Option 2: Direct Redirect**

```javascript
// Simple redirect to backend endpoint
const handleGoogleLogin = () => {
  window.location.href = 'http://localhost:8000/auth/google/redirect';
};
```

## 🔧 **Configuration**

### **Update Google OAuth2 Redirect URI:**

1. Go to Google Cloud Console
2. Update your OAuth2 credentials
3. Add redirect URI: `http://localhost:8000/auth/google/callback/redirect`

### **Environment Variables:**

```env
# Backend (.env)
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback/redirect

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 🛡️ **Security Best Practices**

### **1. Token Storage:**
```javascript
// Store token securely
localStorage.setItem('access_token', token);

// Use token for API calls
const makeAuthenticatedRequest = async (url) => {
  const token = localStorage.getItem('access_token');
  const response = await fetch(url, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return response.json();
};
```

### **2. Token Validation:**
```javascript
// Check if token is valid
const isAuthenticated = () => {
  const token = localStorage.getItem('access_token');
  return !!token;
};

// Redirect if not authenticated
const requireAuth = () => {
  if (!isAuthenticated()) {
    window.location.href = '/login';
  }
};
```

### **3. Logout:**
```javascript
const logout = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('user');
  window.location.href = '/login';
};
```

## 📱 **Mobile App Integration**

### **React Native:**
```javascript
import { Linking } from 'react-native';

const handleGoogleLogin = async () => {
  try {
    const response = await fetch('http://localhost:8000/auth/google/login');
    const { authorization_url } = await response.json();
    
    // Open in-app browser
    await Linking.openURL(authorization_url);
  } catch (error) {
    console.error('Login failed:', error);
  }
};

// Handle deep linking back to app
const handleDeepLink = (url) => {
  // Parse URL parameters and handle authentication
  // Similar to web implementation
};
```

## 🚀 **Testing**

### **1. Test the Flow:**
```bash
# Start backend
uvicorn app.main:app --reload

# Visit in browser
http://localhost:8000/auth/google/redirect
```

### **2. Test Frontend Integration:**
```javascript
// Test URL parsing
const testUrl = 'http://localhost:3000/dashboard?auth=success&user=%7B%22id%22%3A%22123%22%7D';
const urlParams = new URLSearchParams(new URL(testUrl).search);
console.log(urlParams.get('auth')); // 'success'
console.log(urlParams.get('user')); // '{"id":"123"}'
```

## 🔍 **Debugging**

### **Common Issues:**

1. **CORS Errors:** Ensure backend CORS is configured
2. **Redirect URI Mismatch:** Check Google OAuth2 configuration
3. **Token Expiry:** Implement token refresh logic
4. **URL Encoding:** Ensure proper URL encoding/decoding

### **Debug Logs:**
```javascript
// Add to your frontend
console.log('URL Parameters:', window.location.search);
console.log('User Data:', localStorage.getItem('user'));
console.log('Access Token:', localStorage.getItem('access_token'));
```

This setup provides a complete authentication flow with proper frontend integration! 🎉 