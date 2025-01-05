// Like button functionality
document.querySelectorAll('.like-btn').forEach(button => {
    button.addEventListener('click', function() {
      const likeCount = this.nextElementSibling;
      let count = parseInt(likeCount.textContent);
      count++;
      likeCount.textContent = count;
    });
});
  
// Comment functionality
document.querySelectorAll('.comment-btn').forEach(button => {
    button.addEventListener('click', function() {
      const post = this.closest('.post');
      const commentInput = post.querySelector('.comment-input').value;
      
      if (commentInput) {
        const commentBox = post.querySelector('.comments');
        const comment = document.createElement('p');
        comment.textContent = commentInput;
        commentBox.appendChild(comment);
  
        post.querySelector('.comment-input').value = ''; // Clear input
      }
    });
});
  
// Follow button functionality
document.querySelector('.follow-btn').addEventListener('click', function() {
    if (this.textContent === 'Follow') {
      this.textContent = 'Unfollow';
    } else {
      this.textContent = 'Follow';
    }
});

// Search functionality
function filterUsers() {
  const input = document.getElementById('userSearch');
  const filter = input.value.toLowerCase();
  const users = document.querySelectorAll('.user-suggestion');

  users.forEach(user => {
      const userName = user.querySelector('span').textContent.toLowerCase();
      if (userName.includes(filter)) {
          user.style.display = '';
      } else {
          user.style.display = 'none';
      }
  });
}

// Ensure the search button triggers the filter function
document.addEventListener('DOMContentLoaded', function () {
  const searchBtn = document.getElementById('search-btn');
  
  searchBtn.addEventListener('click', function () {
      filterUsers();
  });
});