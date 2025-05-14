// Theme switching functionality
document.addEventListener('DOMContentLoaded', function() {
    // Theme switching core functionality
    function applyTheme(theme) {
        if (theme === 'system') {
            const prefersDarkScheme = window.matchMedia('(prefers-color-scheme: dark)').matches;
            document.documentElement.setAttribute('data-theme', prefersDarkScheme ? 'dark' : 'light');
        } else {
            document.documentElement.setAttribute('data-theme', theme);
        }
        localStorage.setItem('theme', theme);
        updateThemeToggleIcon(theme);
    }
    
    // Listen for system theme changes if using system theme
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
        if (localStorage.getItem('theme') === 'system') {
            document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
            updateThemeToggleIcon(e.matches ? 'dark' : 'light');
        }
    });
    
    // If on settings page, connect the theme options to our applyTheme function
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
    
    // Theme toggle button in the navbar
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', function() {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            applyTheme(newTheme);
        });
        
        // Initialize the toggle button icon based on current theme
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        updateThemeToggleIcon(currentTheme);
    }
    
    function updateThemeToggleIcon(theme) {
        const toggleIcon = document.getElementById('themeToggleIcon');
        if (toggleIcon) {
            if (theme === 'dark') {
                toggleIcon.classList.remove('bi-moon');
                toggleIcon.classList.add('bi-sun');
            } else {
                toggleIcon.classList.remove('bi-sun');
                toggleIcon.classList.add('bi-moon');
            }
        }
    }
    
    // Make sure the theme is applied on page load
    const savedTheme = localStorage.getItem('theme') || 'light';
    applyTheme(savedTheme);
});