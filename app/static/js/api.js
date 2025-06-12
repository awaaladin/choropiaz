// Django API Integration
const DJANGO_API_BASE_URL = 'https://gax-2.onrender.com/api';

class DjangoAPI {
    static async register(userData) {
        try {
            const response = await fetch(`${DJANGO_API_BASE_URL}/register/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(userData)
            });
            const data = await response.json();
            return { success: response.ok, data };
        } catch (error) {
            console.error('Registration error:', error);
            return { success: false, error: 'Network error during registration' };
        }
    }

    static async login(username, password) {
        try {
            const response = await fetch(`${DJANGO_API_BASE_URL}/login/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password })
            });
            const data = await response.json();
            if (response.ok && data.token) {
                // Store the token in localStorage
                localStorage.setItem('django_api_token', data.token);
                return { success: true, data };
            }
            return { success: false, error: data.detail || 'Login failed' };
        } catch (error) {
            console.error('Login error:', error);
            return { success: false, error: 'Network error during login' };
        }
    }

    static async getBankingData() {
        try {
            const token = localStorage.getItem('django_api_token');
            if (!token) {
                return { success: false, error: 'Not authenticated with banking service' };
            }

            const response = await fetch(`${DJANGO_API_BASE_URL}/banking/data/`, {
                headers: {
                    'Authorization': `Token ${token}`,
                    'Content-Type': 'application/json',
                }
            });
            const data = await response.json();
            return { success: response.ok, data };
        } catch (error) {
            console.error('Banking data error:', error);
            return { success: false, error: 'Network error fetching banking data' };
        }
    }

    // Add more API methods as needed
}
