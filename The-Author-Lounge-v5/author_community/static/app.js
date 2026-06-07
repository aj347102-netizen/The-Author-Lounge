// ── LIKE BUTTONS ─────────────────────────────────────────────────
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.like-btn');
  if (!btn) return;
  e.preventDefault();

  const postId = btn.dataset.postId;
  const icon = btn.querySelector('.action-icon');
  const countEl = btn.querySelector('.like-count');

  try {
    const res = await fetch(`/post/${postId}/like`, { method: 'POST' });
    const data = await res.json();
    if (data.liked) {
      btn.classList.add('liked');
      icon.textContent = '❤️';
    } else {
      btn.classList.remove('liked');
      icon.textContent = '🤍';
    }
    countEl.textContent = data.count;
  } catch (err) {
    console.error('Like failed', err);
  }
});

// ── FOLLOW BUTTONS ───────────────────────────────────────────────
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.follow-btn');
  if (!btn) return;
  e.preventDefault();

  const username = btn.dataset.username;
  try {
    const res = await fetch(`/follow/${username}`, { method: 'POST' });
    const data = await res.json();
    if (data.following) {
      btn.textContent = '✓ Following';
      btn.classList.add('following');
    } else {
      btn.textContent = '+ Follow';
      btn.classList.remove('following');
    }
    btn.dataset.followers = data.follower_count;
  } catch (err) {
    console.error('Follow failed', err);
  }
});

// ── CREATE POST: TYPE SWITCHER ───────────────────────────────────
const typeButtons = document.querySelectorAll('.type-btn');
const postTypeInput = document.getElementById('post_type_input');
const mediaField = document.getElementById('media-field');
const eventFields = document.getElementById('event-fields');
const mediaLabel = document.getElementById('media-label');
const mediaUrlInput = document.getElementById('media_url');
const hints = document.querySelectorAll('.hint');

function showHint(type) {
  hints.forEach(h => h.classList.toggle('visible', h.dataset.type === type));
}

function switchType(type) {
  typeButtons.forEach(b => b.classList.toggle('active', b.dataset.type === type));
  if (postTypeInput) postTypeInput.value = type;

  if (mediaField) {
    mediaField.style.display = (type === 'snap' || type === 'reel') ? 'block' : 'none';
  }
  if (mediaLabel) {
    mediaLabel.textContent = type === 'reel' ? '🎬 Video URL' : '📸 Image URL';
  }
  if (eventFields) {
    eventFields.style.display = type === 'event' ? 'block' : 'none';
  }
  showHint(type);
}

typeButtons.forEach(btn => {
  btn.addEventListener('click', () => switchType(btn.dataset.type));
});

// Init hint on page load
if (postTypeInput) showHint(postTypeInput.value);

// ── CHARACTER COUNTER ────────────────────────────────────────────
const textarea = document.getElementById('post-content');
const charCount = document.getElementById('char-count');
if (textarea && charCount) {
  textarea.addEventListener('input', () => {
    charCount.textContent = textarea.value.length;
  });
}

// ── AUTO-DISMISS FLASH MESSAGES ──────────────────────────────────
setTimeout(() => {
  document.querySelectorAll('.flash').forEach(el => {
    el.style.transition = 'opacity .4s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 400);
  });
}, 3500);
