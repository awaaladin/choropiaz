// Add this to a new file named media_handlers.js in your static/js folder
document.addEventListener('DOMContentLoaded', function() {
    // Enable video playback for reels
    const videos = document.querySelectorAll('video');
    videos.forEach(video => {
        // Make videos playable with click
        video.addEventListener('click', function() {
            if (video.paused) {
                // Pause all other videos first
                videos.forEach(v => {
                    if (v !== video && !v.paused) {
                        v.pause();
                    }
                });
                
                video.play();
            } else {
                video.pause();
            }
        });
        
        // Add play button overlay
        const videoContainer = video.parentElement;
        if (!videoContainer.querySelector('.play-overlay')) {
            const playOverlay = document.createElement('div');
            playOverlay.className = 'play-overlay absolute inset-0 flex items-center justify-center';
            playOverlay.innerHTML = '<i class="bi bi-play-circle text-white text-5xl opacity-70"></i>';
            
            // Show overlay only when video is paused
            video.addEventListener('play', () => {
                playOverlay.style.display = 'none';
            });
            
            video.addEventListener('pause', () => {
                playOverlay.style.display = 'flex';
            });
            
            // Apply initial state
            playOverlay.style.display = video.paused ? 'flex' : 'none';
            
            // Add overlay to video container
            videoContainer.style.position = 'relative';
            videoContainer.appendChild(playOverlay);
            
            // Make overlay clickable to control video
            playOverlay.addEventListener('click', () => {
                video.play();
            });
        }
    });
    
    // Profile picture upload preview
    const profilePictureInput = document.getElementById('profile_picture');
    const profilePreview = document.getElementById('profile-preview');
    
    if (profilePictureInput && profilePreview) {
        profilePictureInput.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    profilePreview.src = e.target.result;
                    profilePreview.style.display = 'block';
                };
                reader.readAsDataURL(file);
            }
        });
    }
});