// ===== Configuration =====
const API_BASE = '';

// ===== Sidebar =====
const hamburgerBtn = document.getElementById('hamburgerBtn');
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebarOverlay');
const sidebarClose = document.getElementById('sidebarClose');
const logoutBtn = document.getElementById('logoutBtn');

function openSidebar() {
  hamburgerBtn.classList.add('active');
  sidebar.classList.add('open');
  sidebarOverlay.classList.add('visible');
}

function closeSidebar() {
  hamburgerBtn.classList.remove('active');
  sidebar.classList.remove('open');
  sidebarOverlay.classList.remove('visible');
}

hamburgerBtn.addEventListener('click', () => {
  if (sidebar.classList.contains('open')) closeSidebar();
  else openSidebar();
});

sidebarClose.addEventListener('click', closeSidebar);
sidebarOverlay.addEventListener('click', closeSidebar);
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeSidebar();
});

logoutBtn.addEventListener('click', (e) => {
  e.preventDefault();
  localStorage.removeItem('access_token');
  window.location.href = '/';
});

// ===== Admin Tabs =====
function switchAdminTab(tab) {
  document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
  document.querySelector(`[data-tab="${tab}"]`).classList.add('active');

  document.getElementById('articlesSection').classList.toggle('hidden', tab !== 'articles');
  document.getElementById('eventsSection').classList.toggle('hidden', tab !== 'events');

  if (tab === 'articles') loadArticles();
  if (tab === 'events') loadEvents();
}

// ===== Message Helpers =====
function showMessage(elementId, text, type) {
  const el = document.getElementById(elementId);
  el.textContent = text;
  el.className = `message ${type}`;
  setTimeout(() => { el.textContent = ''; el.className = 'message'; }, 5000);
}

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleDateString('ru-RU', {
    year: 'numeric', month: 'long', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

// ===== Articles =====
let editingArticleId = null;

function showArticleForm(article = null) {
  const form = document.getElementById('articleForm');
  form.classList.remove('hidden');
  document.getElementById('articleFormTitle').textContent = article ? 'Edit Article' : 'New Article';

  if (article) {
    editingArticleId = article.id;
    document.getElementById('articleTitle').value = article.title;
    document.getElementById('articleExcerpt').value = article.excerpt || '';
    document.getElementById('articleContent').value = article.content;
  } else {
    editingArticleId = null;
    document.getElementById('articleTitle').value = '';
    document.getElementById('articleExcerpt').value = '';
    document.getElementById('articleContent').value = '';
  }

  form.scrollIntoView({ behavior: 'smooth' });
}

function hideArticleForm() {
  document.getElementById('articleForm').classList.add('hidden');
  editingArticleId = null;
}

async function saveArticle() {
  const token = localStorage.getItem('access_token');
  if (!token) { window.location.href = '/'; return; }

  const title = document.getElementById('articleTitle').value.trim();
  const content = document.getElementById('articleContent').value.trim();
  const excerpt = document.getElementById('articleExcerpt').value.trim();

  if (!title || !content) {
    showMessage('articleMessage', 'Title and content are required', 'error');
    return;
  }

  const btn = document.querySelector('#articleForm .btn-primary');
  btn.disabled = true;
  btn.textContent = editingArticleId ? 'Saving...' : 'Publishing...';

  try {
    const url = editingArticleId
      ? `${API_BASE}/admin/articles/${editingArticleId}`
      : `${API_BASE}/admin/articles`;

    const method = editingArticleId ? 'PUT' : 'POST';
    const body = editingArticleId
      ? JSON.stringify({ title, content, excerpt })
      : JSON.stringify({ title, content, excerpt });

    const response = await fetch(url, {
      method,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body,
    });

    if (response.ok) {
      showMessage('articleMessage', editingArticleId ? 'Article updated!' : 'Article published!', 'success');
      hideArticleForm();
      loadArticles();
    } else {
      const data = await response.json();
      showMessage('articleMessage', data.detail || 'Error', 'error');
    }
  } catch (err) {
    showMessage('articleMessage', 'Network error', 'error');
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.textContent = editingArticleId ? 'Save Article' : 'Save Article';
  }
}

async function deleteArticle(id) {
  if (!confirm('Delete this article?')) return;

  const token = localStorage.getItem('access_token');
  if (!token) return;

  try {
    const response = await fetch(`${API_BASE}/admin/articles/${id}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` },
    });

    if (response.ok) {
      loadArticles();
    } else {
      alert('Error deleting article');
    }
  } catch (err) {
    alert('Network error');
  }
}

async function loadArticles() {
  const token = localStorage.getItem('access_token');
  if (!token) { window.location.href = '/'; return; }

  const listEl = document.getElementById('articlesList');
  const loadingEl = document.getElementById('articlesLoading');
  loadingEl.classList.remove('hidden');
  listEl.innerHTML = '';

  try {
    const response = await fetch(`${API_BASE}/admin/articles`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });

    if (!response.ok) {
      if (response.status === 403) {
        window.location.href = '/dashboard';
        return;
      }
      throw new Error('Failed to load articles');
    }

    const articles = await response.json();
    loadingEl.classList.add('hidden');

    if (articles.length === 0) {
      listEl.innerHTML = '<div class="empty-state"><p>No articles yet. Create your first one!</p></div>';
      return;
    }

    articles.forEach(article => {
      const item = document.createElement('div');
      item.className = 'admin-list-item';
      item.innerHTML = `
        <div class="list-item-header">
          <h3 class="list-item-title">${escapeHtml(article.title)}</h3>
          <span class="list-item-date">${formatDate(article.created_at)}</span>
        </div>
        ${article.excerpt ? `<p class="list-item-excerpt">${escapeHtml(article.excerpt)}</p>` : ''}
        <div class="list-item-actions">
          <button class="btn-small btn-edit" onclick='editArticle(${JSON.stringify(article).replace(/'/g, "&#39;")})'>Edit</button>
          <button class="btn-small btn-delete" onclick="deleteArticle(${article.id})">Delete</button>
        </div>
      `;
      listEl.appendChild(item);
    });
  } catch (err) {
    loadingEl.classList.add('hidden');
    listEl.innerHTML = '<div class="empty-state"><p>Error loading articles</p></div>';
    console.error(err);
  }
}

function editArticle(article) {
  showArticleForm(article);
}

// ===== Events =====
let editingEventId = null;

function showEventForm(event = null) {
  const form = document.getElementById('eventForm');
  form.classList.remove('hidden');
  document.getElementById('eventFormTitle').textContent = event ? 'Edit Event' : 'New Event';

  if (event) {
    editingEventId = event.id;
    document.getElementById('eventTitle').value = event.title;
    document.getElementById('eventDescription').value = event.description;
    document.getElementById('eventDate').value = event.date ? event.date.slice(0, 16) : '';
    document.getElementById('eventLocation').value = event.location || '';
    document.getElementById('eventMaxParticipants').value = event.max_participants;
  } else {
    editingEventId = null;
    document.getElementById('eventTitle').value = '';
    document.getElementById('eventDescription').value = '';
    document.getElementById('eventDate').value = '';
    document.getElementById('eventLocation').value = '';
    document.getElementById('eventMaxParticipants').value = '50';
  }

  form.scrollIntoView({ behavior: 'smooth' });
}

function hideEventForm() {
  document.getElementById('eventForm').classList.add('hidden');
  editingEventId = null;
}

async function saveEvent() {
  const token = localStorage.getItem('access_token');
  if (!token) { window.location.href = '/'; return; }

  const title = document.getElementById('eventTitle').value.trim();
  const description = document.getElementById('eventDescription').value.trim();
  const date = document.getElementById('eventDate').value;
  const location = document.getElementById('eventLocation').value.trim();
  const maxParticipants = parseInt(document.getElementById('eventMaxParticipants').value) || 50;

  if (!title || !description || !date) {
    showMessage('eventMessage', 'Title, description, and date are required', 'error');
    return;
  }

  const btn = document.querySelector('#eventForm .btn-primary');
  btn.disabled = true;
  btn.textContent = editingEventId ? 'Saving...' : 'Creating...';

  try {
    const url = editingEventId
      ? `${API_BASE}/admin/events/${editingEventId}`
      : `${API_BASE}/admin/events`;

    const method = editingEventId ? 'PUT' : 'POST';
    const body = JSON.stringify({
      title,
      description,
      date: new Date(date).toISOString(),
      location,
      max_participants: maxParticipants,
    });

    const response = await fetch(url, {
      method,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body,
    });

    if (response.ok) {
      showMessage('eventMessage', editingEventId ? 'Event updated!' : 'Event created!', 'success');
      hideEventForm();
      loadEvents();
    } else {
      const data = await response.json();
      showMessage('eventMessage', data.detail || 'Error', 'error');
    }
  } catch (err) {
    showMessage('eventMessage', 'Network error', 'error');
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.textContent = editingEventId ? 'Save Event' : 'Save Event';
  }
}

async function deleteEvent(id) {
  if (!confirm('Delete this event?')) return;

  const token = localStorage.getItem('access_token');
  if (!token) return;

  try {
    const response = await fetch(`${API_BASE}/admin/events/${id}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` },
    });

    if (response.ok) loadEvents();
    else alert('Error deleting event');
  } catch (err) {
    alert('Network error');
  }
}

async function loadEvents() {
  const token = localStorage.getItem('access_token');
  if (!token) { window.location.href = '/'; return; }

  const listEl = document.getElementById('eventsList');
  const loadingEl = document.getElementById('eventsLoading');
  loadingEl.classList.remove('hidden');
  listEl.innerHTML = '';

  try {
    const response = await fetch(`${API_BASE}/admin/events`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });

    if (!response.ok) {
      if (response.status === 403) {
        window.location.href = '/dashboard';
        return;
      }
      throw new Error('Failed to load events');
    }

    const events = await response.json();
    loadingEl.classList.add('hidden');

    if (events.length === 0) {
      listEl.innerHTML = '<div class="empty-state"><p>No events yet. Create your first one!</p></div>';
      return;
    }

    events.forEach(event => {
      const item = document.createElement('div');
      item.className = 'admin-list-item';
      item.innerHTML = `
        <div class="list-item-header">
          <h3 class="list-item-title">${escapeHtml(event.title)}</h3>
          <span class="list-item-date">${formatDate(event.date)}</span>
        </div>
        <p class="list-item-excerpt">${escapeHtml(event.description)}</p>
        <div class="list-item-meta">
          <span>📍 ${escapeHtml(event.location || 'TBD')}</span>
          <span>👥 Max: ${event.max_participants}</span>
        </div>
        <div class="list-item-actions">
          <button class="btn-small btn-edit" onclick='editEvent(${JSON.stringify(event).replace(/'/g, "&#39;")})'>Edit</button>
          <button class="btn-small btn-delete" onclick="deleteEvent(${event.id})">Delete</button>
        </div>
      `;
      listEl.appendChild(item);
    });
  } catch (err) {
    loadingEl.classList.add('hidden');
    listEl.innerHTML = '<div class="empty-state"><p>Error loading events</p></div>';
    console.error(err);
  }
}

function editEvent(event) {
  showEventForm(event);
}

// ===== Helpers =====
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ===== Init =====
loadArticles();
