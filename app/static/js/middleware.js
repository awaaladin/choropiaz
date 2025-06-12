// Middleware to handle Django API token and authentication
class APIMiddleware {
    static getToken() {
        return localStorage.getItem('django_api_token');
    }

    static setToken(token) {
        localStorage.setItem('django_api_token', token);
    }

    static clearToken() {
        localStorage.removeItem('django_api_token');
    }

    static isAuthenticated() {
        return !!this.getToken();
    }

    static async fetchWithAuth(url, options = {}) {
        const token = this.getToken();
        if (token) {
            options.headers = {
                ...options.headers,
                'Authorization': `Token ${token}`
            };
        }
        
        try {
            const response = await fetch(url, options);
            if (response.status === 401) {
                // Token might be expired or invalid
                this.clearToken();
                window.location.href = '/auth/login';
                return null;
            }
            return response;
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }
}
