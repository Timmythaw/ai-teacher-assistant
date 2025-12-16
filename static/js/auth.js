// @ts-nocheck
// static/js/auth.js
/**
 * Authentication helper for Google OAuth + Flask Session
 * Handles logout and session expiry redirects
 */

// Intercept all fetch requests to catch 401 errors
const originalFetch = window.fetch;
window.fetch = function(input, init) {
    return originalFetch.call(this, input, init).then(async function(response) {
        // Check for 401 Unauthorized (session expired)
        if (response.status === 401) {
            try {
                const data = await response.clone().json();
                
                // Check if it's an auth error
                if (data.code === 'AUTH_REQUIRED' && data.redirect_to) {
                    console.warn('Session expired. Redirecting to login...');
                    
                    // Save current page for redirect after login
                    sessionStorage.setItem('redirect_after_login', window.location.pathname);
                    
                    // Redirect to login
                    window.location.href = data.redirect_to;
                    return Promise.reject(new Error('Authentication required'));
                }
            } catch (e) {
                // If response is not JSON, just redirect
                window.location.href = '/auth/login';
                return Promise.reject(new Error('Authentication required'));
            }
        }
        
        return response;
    });
};

// Handle XMLHttpRequest for older AJAX calls
(function() {
    const originalOpen = XMLHttpRequest.prototype.open;
    const originalSend = XMLHttpRequest.prototype.send;
    
    XMLHttpRequest.prototype.open = function(method, url) {
        this._url = url;
        return originalOpen.apply(this, arguments);
    };
    
    XMLHttpRequest.prototype.send = function() {
        this.addEventListener('load', function() {
            if (this.status === 401) {
                try {
                    const data = JSON.parse(this.responseText);
                    if (data.code === 'AUTH_REQUIRED') {
                        console.warn('Session expired. Redirecting to login...');
                        sessionStorage.setItem('redirect_after_login', window.location.pathname);
                        window.location.href = data.redirect_to || '/auth/login';
                    }
                } catch (e) {
                    window.location.href = '/auth/login';
                }
            }
        });
        return originalSend.apply(this, arguments);
    };
})();

/**
 * Logout function
 * Calls backend logout endpoint
 */
async function logout() {
    try {
        const response = await fetch('/auth/logout', {
            method: 'POST',
            credentials: 'include'
        });
        
        // Redirect to login regardless of response
        window.location.href = '/auth/login';
        
    } catch (error) {
        console.error('Logout failed:', error);
        // Force redirect on error
        window.location.href = '/auth/login';
    }
}

// Export helpers
window.authHelpers = {
    logout: logout
};
