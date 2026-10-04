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
    console.error('Ошибка загрузки профиля:', err);
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
      const adminLink = document.getElementById('adminLink');
      if (adminLink) {
        adminLink.style.display = 'block';
        // При клике передаём токен через query parameter
        adminLink.addEventListener('click', (e) => {
          e.preventDefault();
          const token = localStorage.getItem('access_token');
          if (token) {
            window.location.href = '/admin?token=' + token;
          }
        });
      }
    } else {
      // Для обычных пользователей показываем колокольчик уведомлений
      const bell = document.getElementById('notificationBell');
      if (bell) {
        bell.style.display = 'flex';
        loadNotifications();
      }
    }
  } catch (err) {
    console.error('Ошибка загрузки контента:', err);
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
    <h2 class="section-title">Статьи</h2>
    ${articles.length === 0
      ? '<p class="empty-text">Статей пока нет</p>'
      : articles.map(a => `
        <div class="content-card" onclick="showArticleDetail(${a.id})">
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
    <h2 class="section-title">Предстоящие события</h2>
    ${events.length === 0
      ? '<p class="empty-text">Предстоящих событий нет</p>'
      : events.map(e => `
        <div class="content-card" onclick="showEventDetail(${e.id})">
          <h3 class="content-card-title">${escapeHtml(e.title)}</h3>
          <p class="content-card-excerpt">${escapeHtml(e.description)}</p>
          <div class="content-card-meta">
            <span>📅 ${formatDate(e.date)}</span>
            <span>📍 ${escapeHtml(e.location || 'TBD')}</span>
            <span>👥 ${e.registered_count}/${e.max_participants}</span>
          </div>
          <button class="btn-register" onclick="event.stopPropagation(); registerEvent(${e.id}, this)">Записаться</button>
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
      btn.textContent = 'Вы записаны ✓';
      btn.classList.add('registered');
      btn.disabled = true;
    } else {
      const data = await response.json();
      alert(data.detail || 'Ошибка записи');
    }
  } catch (err) {
    alert('Ошибка сети');
  }
}

// ===== Event Detail Modal =====
async function showEventDetail(eventId) {
  const token = localStorage.getItem('access_token');
  if (!token) return;

  const modal = document.getElementById('eventModal');
  const titleEl = document.getElementById('eventModalTitle');
  const dateEl = document.getElementById('eventModalDate');
  const locationEl = document.getElementById('eventModalLocation');
  const participantsEl = document.getElementById('eventModalParticipants');
  const bodyEl = document.getElementById('eventModalBody');
  const actionsEl = document.getElementById('eventModalActions');

  // Показываем модалку сразу с плейсхолдером
  modal.classList.remove('hidden');
  titleEl.textContent = 'Загрузка...';
  dateEl.textContent = '';
  locationEl.textContent = '';
  participantsEl.textContent = '';
  bodyEl.innerHTML = '';
  actionsEl.innerHTML = '<p style="color: #5a5f68; text-align: center; padding: 40px 0;">Загрузка события...</p>';

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    const response = await fetch(`${API_BASE}/events/${eventId}`, {
      headers: { 'Authorization': `Bearer ${token}` },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const event = await response.json();
    titleEl.textContent = event.title;
    dateEl.textContent = `📅 ${formatDate(event.date)}`;
    locationEl.textContent = `📍 ${event.location || 'Место проведения уточняется'}`;
    participantsEl.textContent = `👥 Записано: ${event.registered_count}/${event.max_participants}`;
    bodyEl.innerHTML = `<div class="event-content">${escapeHtml(event.description).replace(/\n/g, '<br>')}</div>`;

    // Кнопка записи/отмены
    if (event.is_registered) {
      actionsEl.innerHTML = `
        <button class="btn-register registered" disabled>
          Вы записаны ✓
        </button>`;
    } else {
      actionsEl.innerHTML = `
        <button class="btn-register" onclick="registerEventFromModal(${event.id})">
          Записаться
        </button>`;
    }
  } catch (err) {
    console.error('Ошибка загрузки события:', err);
    titleEl.textContent = 'Ошибка загрузки';
    bodyEl.innerHTML = `
      <p style="color: #e74c3c; text-align: center; padding: 40px 0;">
        Не удалось загрузить событие. Проверьте соединение.
      </p>`;
    actionsEl.innerHTML = `
      <button onclick="closeEventDetail()" 
        style="margin-top: 20px; padding: 10px 24px; background: #e5a92e; border: none; border-radius: 8px; color: #fff; cursor: pointer; font-size: 14px;">
        Закрыть
      </button>`;
  }
}

function closeEventDetail() {
  const modal = document.getElementById('eventModal');
  modal.classList.add('hidden');
}

// Регистрация из модального окна события
async function registerEventFromModal(eventId) {
  const btn = document.querySelector('#eventModalActions .btn-register');
  if (!btn) return;

  btn.textContent = 'Записываюсь...';
  btn.disabled = true;

  try {
    const response = await fetch(`${API_BASE}/events/${eventId}/register`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        'Content-Type': 'application/json',
      },
    });

    if (response.ok) {
      btn.textContent = 'Вы записаны ✓';
      btn.classList.add('registered');
      btn.disabled = true;
      // Обновляем счётчик участников
      const participantsEl = document.getElementById('eventModalParticipants');
      if (participantsEl) {
        const parts = participantsEl.textContent.match(/(\d+)\/(\d+)/);
        if (parts) {
          participantsEl.textContent = `👥 Записано: ${parseInt(parts[1]) + 1}/${parts[2]}`;
        }
      }
    } else {
      const data = await response.json();
      alert(data.detail || 'Ошибка записи');
      btn.textContent = 'Записаться';
      btn.disabled = false;
    }
  } catch (err) {
    alert('Ошибка сети');
    btn.textContent = 'Записаться';
    btn.disabled = false;
  }
}

// Закрытие модального окна события по клику на overlay
document.addEventListener('click', (e) => {
  const modal = document.getElementById('eventModal');
  if (e.target === modal) {
    closeEventDetail();
  }
});

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ===== Article Detail Modal =====
async function showArticleDetail(articleId) {
  const token = localStorage.getItem('access_token');
  if (!token) return;

  const modal = document.getElementById('articleModal');
  const titleEl = document.getElementById('articleModalTitle');
  const dateEl = document.getElementById('articleModalDate');
  const bodyEl = document.getElementById('articleModalBody');

  // Показываем модалку сразу с плейсхолдером
  modal.classList.remove('hidden');
  titleEl.textContent = 'Загрузка...';
  dateEl.textContent = '';
  bodyEl.innerHTML = '<p style="color: #5a5f68; text-align: center; padding: 40px 0;">Загрузка статьи...</p>';

  try {
    // Создаём контроллер для отмены запроса через 10 секунд
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    const response = await fetch(`${API_BASE}/articles/${articleId}`, {
      headers: { 'Authorization': `Bearer ${token}` },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const article = await response.json();
    titleEl.textContent = article.title;
    dateEl.textContent = formatDate(article.created_at);
    bodyEl.innerHTML = `<div class="article-content">${escapeHtml(article.content).replace(/\n/g, '<br>')}</div>`;
  } catch (err) {
    console.error('Ошибка загрузки статьи:', err);
    titleEl.textContent = 'Ошибка загрузки';
    bodyEl.innerHTML = `
      <p style="color: #e74c3c; text-align: center; padding: 40px 0;">
        Не удалось загрузить статью. Проверьте соединение.
      </p>
      <button onclick="closeArticleDetail()" 
        style="margin-top: 20px; padding: 10px 24px; background: #e5a92e; border: none; border-radius: 8px; color: #fff; cursor: pointer; font-size: 14px;">
        Закрыть
      </button>`;
  }
}

function closeArticleDetail() {
  const modal = document.getElementById('articleModal');
  modal.classList.add('hidden');
}

// Закрытие по клику на overlay
document.addEventListener('click', (e) => {
  const modal = document.getElementById('articleModal');
  if (e.target === modal) {
    closeArticleDetail();
  }
});

// Закрытие по Escape
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeArticleDetail();
    closeNotifications();
  }
});

// ===== Notifications =====
function loadNotifications() {
  const token = localStorage.getItem('access_token');
  if (!token) return;

  // Получаем уведомления из localStorage
  const notifications = JSON.parse(localStorage.getItem('notifications') || '[]');

  const badge = document.getElementById('notificationBadge');
  const list = document.getElementById('notificationList');

  if (notifications.length > 0) {
    badge.textContent = notifications.length;
    badge.style.display = 'flex';

    list.innerHTML = notifications.map(n => `
      <div class="notification-item">
        <div class="notification-icon">${n.type === 'article' ? '📄' : '📅'}</div>
        <div class="notification-content">
          <p class="notification-text">${escapeHtml(n.text)}</p>
          <span class="notification-time">${n.time}</span>
        </div>
      </div>
    `).join('');
  } else {
    badge.style.display = 'none';
    list.innerHTML = '<p class="empty-notifications">Нет новых уведомлений</p>';
  }
}

// Обработчик для колокольчика
document.addEventListener('DOMContentLoaded', () => {
  const bell = document.getElementById('notificationBell');
  if (bell) {
    bell.addEventListener('click', toggleNotifications);
  }
});

function toggleNotifications() {
  const dropdown = document.getElementById('notificationDropdown');
  dropdown.classList.toggle('hidden');
}

function closeNotifications() {
  const dropdown = document.getElementById('notificationDropdown');
  dropdown.classList.add('hidden');
}

function clearNotifications() {
  localStorage.removeItem('notifications');
  loadNotifications();
  closeNotifications();
}

// ===== Init =====
document.addEventListener('DOMContentLoaded', () => {
  // Обновляем ссылки в sidebar — добавляем токен к навигации
  const token = localStorage.getItem('access_token');
  if (token) {
    const sidebarLinks = document.querySelectorAll('.sidebar-link');
    sidebarLinks.forEach(link => {
      const href = link.getAttribute('href');
      if (href && !href.startsWith('http') && !href.startsWith('#')) {
        link.href = href + '?token=' + token;
      }
    });
  }
  loadProfile();
});
