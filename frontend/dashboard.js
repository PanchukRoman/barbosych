// ===== Sidebar Menu =====
const hamburgerBtn = document.getElementById('hamburgerBtn');
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebarOverlay');
const sidebarClose = document.getElementById('sidebarClose');
const logoutBtn = document.getElementById('logoutBtn');
const desktopSidebarToggle = document.getElementById('desktopSidebarToggle');

function openSidebar() {
  hamburgerBtn.classList.add('active');
  sidebar.classList.add('open');
  sidebar.classList.remove('collapsed');
  sidebarOverlay.classList.add('visible');
}

function closeSidebar() {
  hamburgerBtn.classList.remove('active');
  sidebar.classList.remove('open');
  sidebarOverlay.classList.remove('visible');
  
  // На десктопе вместо закрытия — сворачиваем
  if (window.innerWidth >= 768) {
    sidebar.classList.add('collapsed');
  }
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

// Desktop sidebar toggle
if (desktopSidebarToggle) {
  desktopSidebarToggle.addEventListener('click', () => {
    sidebar.classList.toggle('collapsed');
  });
}

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

    // Аватар
    const avatarEl = document.getElementById('profileAvatar');
    if (user.avatar) {
      avatarEl.innerHTML = `<img src="/static/avatars/${user.avatar}" alt="Avatar" style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%;">`;
    } else {
      avatarEl.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z"/></svg>`;
    }

    // Показываем карточку, скрываем лоадер
    loadingEl.classList.add('hidden');
    profileCard.classList.remove('hidden');

    // Загружаем статьи и события
    loadContent(user.role);
    loadDogs();
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

    // Показываем/скрываем ссылку на админ-панель
    const adminLink = document.getElementById('adminLink');
    if (adminLink) {
      if (role === 'admin') {
        adminLink.style.display = 'block';
        // При клике передаём токен через query parameter
        adminLink.addEventListener('click', (e) => {
          e.preventDefault();
          const token = localStorage.getItem('access_token');
          if (token) {
            window.location.href = '/admin?token=' + token;
          }
        });
      } else {
        adminLink.style.display = 'none';
      }
    }

    if (role !== 'admin') {
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
      showToast(data.detail || 'Ошибка записи', 'error');
    }
  } catch (err) {
    showToast('Ошибка сети', 'error');
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

    // Отображаем участников
    if (event.participants && event.participants.length > 0) {
      renderParticipants(event.participants);
    } else {
      document.getElementById('participantsSection').style.display = 'none';
    }

    // Кнопка записи/отмены
    if (event.is_registered) {
      actionsEl.innerHTML = `
        <button class="btn-unregister" onclick="unregisterEvent(${event.id})">
          Отписаться
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
      showToast(data.detail || 'Ошибка записи', 'error');
      btn.textContent = 'Записаться';
      btn.disabled = false;
    }
  } catch (err) {
    showToast('Ошибка сети', 'error');
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

// ===== Unregister from Event =====
async function unregisterEvent(eventId) {
  const token = localStorage.getItem('access_token');
  if (!token) return;

  try {
    const response = await fetch(`${API_BASE}/events/${eventId}/register`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` },
    });

    if (response.ok) {
      showToast('Вы отписались от события', 'success');
      // Перезагружаем событие для обновления состояния
      showEventDetail(eventId);
    } else {
      const data = await response.json();
      showToast(data.detail || 'Ошибка отписки', 'error');
    }
  } catch (err) {
    showToast('Ошибка сети', 'error');
  }
}

// ===== Participants =====
function renderParticipants(participants) {
  const section = document.getElementById('participantsSection');
  const list = document.getElementById('participantsList');
  
  if (!participants || participants.length === 0) {
    section.style.display = 'none';
    return;
  }

  section.style.display = 'block';
  list.innerHTML = participants.map(p => `
    <div class="participant-card">
      <div class="participant-avatar">
        ${p.avatar 
          ? `<img src="/static/avatars/${p.avatar}" alt="Avatar">`
          : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z"/></svg>`
        }
      </div>
      <div class="participant-info">
        <div class="participant-email">${escapeHtml(p.email)}</div>
        ${p.dogs && p.dogs.length > 0 
          ? `<div class="participant-dogs">${p.dogs.map(d => `🐕 ${escapeHtml(d.name)} (${escapeHtml(d.breed)})`).join(', ')}</div>`
          : '<div class="participant-no-dogs">Нет добавленных собак</div>'
        }
      </div>
    </div>
  `).join('');
}

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

// ===== Avatar Upload =====
async function uploadAvatar(input) {
  const file = input.files[0];
  if (!file) return;

  const token = localStorage.getItem('access_token');
  if (!token) return;

  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await fetch(`${API_BASE}/users/me/avatar`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData,
    });

    if (!response.ok) {
      const data = await response.json();
      showToast(data.detail || 'Ошибка загрузки аватара', 'error');
      return;
    }

    const user = await response.json();
    const avatarEl = document.getElementById('profileAvatar');
    avatarEl.innerHTML = `<img src="/static/avatars/${user.avatar}?t=${Date.now()}" alt="Avatar" style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%;">`;
    showToast('Аватар обновлён', 'success');
  } catch (err) {
    showToast('Ошибка сети', 'error');
  }

  input.value = '';
}

// ===== Profile Edit =====
function openEditProfileModal() {
  const modal = document.getElementById('editProfileModal');
  const emailInput = document.getElementById('editEmail');
  emailInput.value = document.getElementById('profileEmail').textContent;
  modal.classList.remove('hidden');
}

function closeEditProfileModal() {
  const modal = document.getElementById('editProfileModal');
  modal.classList.add('hidden');
  document.getElementById('profileMessage').textContent = '';
}

async function saveProfile(e) {
  e.preventDefault();
  const token = localStorage.getItem('access_token');
  if (!token) return;

  const email = document.getElementById('editEmail').value;
  const msgEl = document.getElementById('profileMessage');
  const btn = document.getElementById('saveProfileBtn');

  btn.textContent = 'Сохранение...';
  btn.disabled = true;
  msgEl.textContent = '';

  try {
    const response = await fetch(`${API_BASE}/users/me`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email }),
    });

    if (!response.ok) {
      const data = await response.json();
      msgEl.textContent = data.detail || 'Ошибка сохранения';
      msgEl.className = 'message error';
      btn.textContent = 'Сохранить';
      btn.disabled = false;
      return;
    }

    const user = await response.json();
    document.getElementById('profileEmail').textContent = user.email;
    closeEditProfileModal();
    showToast('Профиль обновлён', 'success');
  } catch (err) {
    msgEl.textContent = 'Ошибка сети';
    msgEl.className = 'message error';
    btn.textContent = 'Сохранить';
    btn.disabled = false;
  }
}

// ===== Dogs =====
async function loadDogs() {
  const token = localStorage.getItem('access_token');
  if (!token) return;

  const section = document.getElementById('dogsSection');
  const list = document.getElementById('dogsList');
  const loading = document.getElementById('dogsLoading');

  try {
    const response = await fetch(`${API_BASE}/users/me/dogs`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });

    if (!response.ok) {
      section.classList.add('hidden');
      return;
    }

    const dogs = await response.json();
    section.classList.remove('hidden');

    if (dogs.length === 0) {
      list.innerHTML = '<p class="empty-text">У вас пока нет собак. Добавьте первую!</p>';
      return;
    }

    list.innerHTML = dogs.map(dog => `
      <div class="dog-card">
        <div class="dog-card-info">
          <h3 class="dog-card-name">${escapeHtml(dog.name)}</h3>
          <p class="dog-card-breed">${escapeHtml(dog.breed)}</p>
          <p class="dog-card-age">Возраст: ${dog.age} ${getAgeWord(dog.age)}</p>
        </div>
        <div class="dog-card-actions">
          <button class="btn-edit-dog" onclick="openEditDogModal(${dog.id}, '${escapeHtml(dog.name)}', '${escapeHtml(dog.breed)}', ${dog.age})">✏️</button>
          <button class="btn-delete-dog" onclick="deleteDog(${dog.id})">🗑️</button>
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Ошибка загрузки собак:', err);
    section.classList.add('hidden');
  }
}

function getAgeWord(age) {
  if (age === 1) return 'год';
  if (age >= 2 && age <= 4) return 'года';
  return 'лет';
}

function openAddDogModal() {
  document.getElementById('dogModalTitle').textContent = 'Добавить собаку';
  document.getElementById('dogId').value = '';
  document.getElementById('dogName').value = '';
  document.getElementById('dogBreed').value = '';
  document.getElementById('dogAge').value = '';
  document.getElementById('dogMessage').textContent = '';
  document.getElementById('dogModal').classList.remove('hidden');
}

function closeDogModal() {
  document.getElementById('dogModal').classList.add('hidden');
  document.getElementById('dogMessage').textContent = '';
}

function openEditDogModal(id, name, breed, age) {
  document.getElementById('dogModalTitle').textContent = 'Редактировать собаку';
  document.getElementById('dogId').value = id;
  document.getElementById('dogName').value = name;
  document.getElementById('dogBreed').value = breed;
  document.getElementById('dogAge').value = age;
  document.getElementById('dogMessage').textContent = '';
  document.getElementById('dogModal').classList.remove('hidden');
}

async function saveDog(e) {
  e.preventDefault();
  const token = localStorage.getItem('access_token');
  if (!token) return;

  const dogId = document.getElementById('dogId').value;
  const name = document.getElementById('dogName').value;
  const breed = document.getElementById('dogBreed').value;
  const age = parseInt(document.getElementById('dogAge').value);
  const msgEl = document.getElementById('dogMessage');
  const btn = document.getElementById('saveDogBtn');

  btn.textContent = 'Сохранение...';
  btn.disabled = true;
  msgEl.textContent = '';

  try {
    const isEdit = !!dogId;
    const url = isEdit ? `${API_BASE}/users/me/dogs/${dogId}` : `${API_BASE}/users/me/dogs`;
    const method = isEdit ? 'PUT' : 'POST';

    const response = await fetch(url, {
      method,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name, breed, age }),
    });

    if (!response.ok) {
      const data = await response.json();
      msgEl.textContent = data.detail || 'Ошибка сохранения';
      msgEl.className = 'message error';
      btn.textContent = 'Сохранить';
      btn.disabled = false;
      return;
    }

    btn.textContent = 'Сохранить';
    btn.disabled = false;
    closeDogModal();
    loadDogs();
  } catch (err) {
    msgEl.textContent = 'Ошибка сети';
    msgEl.className = 'message error';
    btn.textContent = 'Сохранить';
    btn.disabled = false;
  }
}

async function deleteDog(dogId) {
  if (!confirm('Удалить собаку из профиля?')) return;

  const token = localStorage.getItem('access_token');
  if (!token) return;

  try {
    const response = await fetch(`${API_BASE}/users/me/dogs/${dogId}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` },
    });

    if (!response.ok) {
      const data = await response.json();
      showToast(data.detail || 'Ошибка удаления', 'error');
      return;
    }

    loadDogs();
  } catch (err) {
    showToast('Ошибка сети', 'error');
  }
}

// ===== Toast Notifications =====
function showToast(message, type = 'info') {
  // Удаляем старые тосты
  const oldToasts = document.querySelectorAll('.toast-notification');
  oldToasts.forEach(t => t.remove());

  const toast = document.createElement('div');
  toast.className = `toast-notification toast-${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);

  // Анимация появления
  requestAnimationFrame(() => {
    toast.classList.add('show');
  });

  // Автоудаление через 3 секунды
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 3000);
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
