// Add this to a new file named social_interactions.js in your static/js folder
document.addEventListener('DOMContentLoaded', function() {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    
    // Handle likes for posts
    document.querySelectorAll('.like-button').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const postId = this.getAttribute('data-post-id');
            const likeCount = document.getElementById(`like-count-${postId}`);
            
            fetch(`/like/${postId}`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                // Update the like button appearance
                if (data.liked) {
                    this.classList.add('text-red-500');
                    this.innerHTML = '<i class="bi bi-heart-fill"></i>';
                } else {
                    this.classList.remove('text-red-500');
                    this.innerHTML = '<i class="bi bi-heart"></i>';
                }
                
                // Update like count
                if (likeCount) {
                    likeCount.textContent = data.likes_count;
                }
            })
            .catch(error => console.error('Error:', error));
        });
    });
    
    // Handle follow/unfollow
    document.querySelectorAll('.follow-button').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const userId = this.getAttribute('data-user-id');
            
            fetch(`/follow/${userId}`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                // Update button text and style based on follow status
                if (data.following) {
                    this.textContent = 'Following';
                    this.classList.add('bg-gray-300');
                    this.classList.remove('bg-choropia-blue');
                } else {
                    this.textContent = 'Follow';
                    this.classList.remove('bg-gray-300');
                    this.classList.add('bg-choropia-blue');
                }
            })
            .catch(error => console.error('Error:', error));
        });
    });
});