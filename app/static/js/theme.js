// Improved theme.js
document.addEventListener('DOMContentLoaded', function() {
    // Theme switching core functionality
    function applyTheme(theme) {
        if (theme === 'system') {
            const prefersDarkScheme = window.matchMedia('(prefers-color-scheme: dark)').matches;
            document.documentElement.setAttribute('data-theme', prefersDarkScheme ? 'dark' : 'light');
            updateThemeToggleIcon(prefersDarkScheme ? 'dark' : 'light');
        } else {
            document.documentElement.setAttribute('data-theme', theme);
            updateThemeToggleIcon(theme);
        }
        localStorage.setItem('theme', theme);
    }
    
    // Listen for system theme changes if using system theme
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
        if (localStorage.getItem('theme') === 'system') {
            document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
            updateThemeToggleIcon(e.matches ? 'dark' : 'light');
        }
    });
    
    function updateThemeToggleIcon(theme) {
        const toggleIcon = document.getElementById('themeToggleIcon');
        if (toggleIcon) {
            if (theme === 'dark') {
                toggleIcon.className = ''; // Clear classes
                toggleIcon.classList.add('bi', 'bi-sun');
            } else {
                toggleIcon.className = ''; // Clear classes
                toggleIcon.classList.add('bi', 'bi-moon');
            }
        }
    }
    
    // Theme toggle button in the navbar
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', function() {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            applyTheme(newTheme);
        });
    }
    
    // If on settings page, handle theme options
    const themeOptions = document.querySelectorAll('.theme-option');
    if (themeOptions.length > 0) {
        themeOptions.forEach(option => {
            option.addEventListener('click', function() {
                const themeValue = this.getAttribute('data-theme');
                document.getElementById('theme-' + themeValue).checked = true;
                applyTheme(themeValue);
            });
        });
        
        // Make sure the correct radio button is checked on page load
        const savedTheme = localStorage.getItem('theme') || 'light';
        const themeRadio = document.getElementById('theme-' + savedTheme);
        if (themeRadio) {
            themeRadio.checked = true;
        }
    }
    
    // Make sure the theme is applied on page load
    const savedTheme = localStorage.getItem('theme') || 'light';
    applyTheme(savedTheme);
});