// ===== Sidebar Menu =====
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
  if (sidebar.classList.contains('open')) {
    closeSidebar();
  } else {
    openSidebar();
  }
});

sidebarClose.addEventListener('click', closeSidebar);
sidebarOverlay.addEventListener('click', closeSidebar);

// Закрытие по Escape
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeSidebar();
});

// ===== Logout =====
logoutBtn.addEventListener('click', (e) => {
  e.preventDefault();
  localStorage.removeItem('access_token');
  window.location.href = '/';
});

// ===== Load User Data =====
const API_BASE = '';

async function loadProfile() {
  const token = localStorage.getItem('access_token');

  if (!token) {
    window.location.href = '/';
    return;
  }

  const loadingEl = document.getElementById('loading');
  const profileCard = document.getElementById('profileCard');
  const errorEl = document.getElementById('errorMessage');

  try {
    const response = await fetch(`${API_BASE}/users/me`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      if (response.status === 401) {
        localStorage.removeItem('access_token');
        window.location.href = '/';
        return;
      }
      throw new Error('Failed to load profile');
    }

    const user = await response.json();

    // Заполняем данные
    document.getElementById('profileEmail').textContent = user.email;
    document.getElementById('profileId').textContent = `#${user.id}`;
    document.getElementById('profileCreated').textContent = formatDate(user.created_at);

    // Показываем карточку, скрываем лоадер
    loadingEl.classList.add('hidden');
    profileCard.classList.remove('hidden');

    // Загружаем статьи и события
    loadContent(user.role);
  } catch (err) {
    console.error('Error loading profile:', err);
    loadingEl.classList.add('hidden');
    errorEl.textContent = 'Не удалось загрузить данные профиля';
    errorEl.classList.remove('hidden');
  }
}

function formatDate(dateStr) {
  const date = new Date(dateStr);
  return date.toLocaleDateString('ru-RU', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// ===== Load Articles & Events =====
async function loadContent(role) {
  const token = localStorage.getItem('access_token');
  if (!token) return;

  try {
    // Загружаем статьи
    const articlesResp = await fetch(`${API_BASE}/articles`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });

    if (articlesResp.ok) {
      const articles = await articlesResp.json();
      renderArticles(articles);
    }

    // Загружаем события
    const eventsResp = await fetch(`${API_BASE}/events`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });

    if (eventsResp.ok) {
      const events = await eventsResp.json();
      renderEvents(events);
    }

    // Если есть админ-панель, показываем ссылку
    if (role === 'admin') {
      const adminLink = document.createElement('a');
      adminLink.href = '/admin';
      adminLink.className = 'sidebar-link';
      adminLink.textContent = 'Admin Panel';
      adminLink.style.color = '#e5a92e';
      const section = document.querySelector('.sidebar-section');
      section.appendChild(adminLink);
    }
  } catch (err) {
    console.error('Error loading content:', err);
  }
}

function renderArticles(articles) {
  let container = document.getElementById('articlesContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'articlesContainer';
    container.className = 'dashboard-section';
    document.querySelector('.dashboard-main').appendChild(container);
  }

  container.innerHTML = `
    <h2 class="section-title">Articles</h2>
    ${articles.length === 0
      ? '<p class="empty-text">No articles yet</p>'
      : articles.map(a => `
        <div class="content-card" onclick="window.location.href='#'">
          <h3 class="content-card-title">${escapeHtml(a.title)}</h3>
          <p class="content-card-excerpt">${escapeHtml(a.excerpt)}</p>
          <span class="content-card-date">${formatDate(a.created_at)}</span>
        </div>
      `).join('')
    }
  `;
}

function renderEvents(events) {
  let container = document.getElementById('eventsContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'eventsContainer';
    container.className = 'dashboard-section';
    document.querySelector('.dashboard-main').appendChild(container);
  }

  container.innerHTML = `
    <h2 class="section-title">Upcoming Events</h2>
    ${events.length === 0
      ? '<p class="empty-text">No upcoming events</p>'
      : events.map(e => `
        <div class="content-card">
          <h3 class="content-card-title">${escapeHtml(e.title)}</h3>
          <p class="content-card-excerpt">${escapeHtml(e.description)}</p>
          <div class="content-card-meta">
            <span>📅 ${formatDate(e.date)}</span>
            <span>📍 ${escapeHtml(e.location || 'TBD')}</span>
            <span>👥 ${e.registered_count}/${e.max_participants}</span>
          </div>
          ${e.is_registered
            ? '<button class="btn-register registered">Registered ✓</button>'
            : `<button class="btn-register" onclick="registerEvent(${e.id}, this)">Register</button>`
          }
        </div>
      `).join('')
    }
  `;
}

async function registerEvent(eventId, btn) {
  const token = localStorage.getItem('access_token');
  if (!token) return;

  try {
    const response = await fetch(`${API_BASE}/events/${eventId}/register`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (response.ok) {
      btn.textContent = 'Registered ✓';
      btn.classList.add('registered');
      btn.disabled = true;
    } else {
      const data = await response.json();
      alert(data.detail || 'Error registering');
    }
  } catch (err) {
    alert('Network error');
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ===== Init =====
document.addEventListener('DOMContentLoaded', () => {
  loadProfile();
});
