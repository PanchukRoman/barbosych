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
logoutBtn.addEventListener('click', async (e) => {
  e.preventDefault();
  try {
    // HttpOnly-cookie из JS не удалить — просим сервер её погасить
    await fetch(`${API_BASE}/auth/logout`, { method: 'POST', credentials: 'include' });
  } catch (err) {
    console.error('Logout error:', err);
  }
  window.location.href = '/';
});

// ===== Load User Data =====
const API_BASE = '';

async function loadProfile() {
  const loadingEl = document.getElementById('loading');
  const profileCard = document.getElementById('profileCard');
  const errorEl = document.getElementById('errorMessage');

  try {
    // credentials: 'include' — браузер сам приложит HttpOnly-cookie с токеном
    const response = await fetch(`${API_BASE}/users/me`, {
      method: 'GET',
      credentials: 'include',
    });

    if (!response.ok) {
      if (response.status === 401) {
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
      avatarEl.innerHTML = `<img src="/uploads/avatars/${user.avatar}" alt="Avatar" style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%;">`;
    } else {
      avatarEl.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z"/></svg>`;
    }

    // Показываем карточку, скрываем лоадер
    loadingEl.classList.add('hidden');
    profileCard.classList.remove('hidden');

    // Загружаем статьи и события
    loadContent(user);
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
async function loadContent(user) {
  try {
    // Статьи
    let articles = null;
    const articlesResp = await fetch(`${API_BASE}/articles`, { credentials: 'include', cache: 'no-store' });

    if (articlesResp.ok) {
      articles = await articlesResp.json();
      renderArticles(articles);
    }

    // События
    let events = null;
    const eventsResp = await fetch(`${API_BASE}/events`, { credentials: 'include', cache: 'no-store' });

    if (eventsResp.ok) {
      events = await eventsResp.json();
      renderEvents(events);
    }

    // Курс дрессировки
    let courses = null;
    const coursesResp = await fetch(`${API_BASE}/courses`, { credentials: 'include', cache: 'no-store' });

    if (coursesResp.ok) {
      courses = await coursesResp.json();
      renderCourses(courses);
    }

    // Ссылку на админку показываем только администратору. Токен в URL не нужен:
    // /admin читает сессию из cookie, которую браузер отправляет сам.
    const adminLink = document.getElementById('adminLink');
    if (adminLink) {
      adminLink.style.display = user.role === 'admin' ? 'block' : 'none';
    }

    // Колокольчик показываем всем: он сообщает о новом контенте (статьи,
    // события, доступ к курсу, материалы курса). Лента приходит с сервера, а не
    // собирается здесь: так она одинакова в любом браузере и не зависит от того,
    // когда пользователь заходил в кабинет в прошлый раз.
    await loadNotifications();
    startNotificationsPolling();
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
  try {
    const response = await fetch(`${API_BASE}/events/${eventId}/register`, {
      method: 'POST',
      credentials: 'include',
    });

    if (response.ok) {
      btn.textContent = 'Вы записаны ✓';
      btn.classList.add('registered');
      btn.disabled = true;
    } else {
      const data = await response.json();
      showToast(errorText(data, 'Ошибка записи'), 'error');
    }
  } catch (err) {
    showToast('Ошибка сети', 'error');
  }
}

// ===== Event Detail Modal =====
async function showEventDetail(eventId) {
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
      credentials: 'include',
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
      credentials: 'include',
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
      showToast(errorText(data, 'Ошибка записи'), 'error');
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
  try {
    const response = await fetch(`${API_BASE}/events/${eventId}/register`, {
      method: 'DELETE',
      credentials: 'include',
    });

    if (response.ok) {
      showToast('Вы отписались от события', 'success');
      // Перезагружаем событие для обновления состояния
      showEventDetail(eventId);
    } else {
      const data = await response.json();
      showToast(errorText(data, 'Ошибка отписки'), 'error');
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
          ? `<img src="/uploads/avatars/${p.avatar}" alt="Avatar">`
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
      credentials: 'include',
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
    closeCourseDetail();
    closeNotifications();
  }
});

// ===== Notifications =====
// Колокольчик показывает «новое»: статьи, события, открытый доступ к курсу,
// новые прогулки и упражнения. Лента живёт на сервере (таблица notifications):
// запись создаётся в момент публикации контента и адресована конкретному
// пользователю.
//
// Раньше лента собиралась здесь же, в браузере, сравнением текущих списков
// контента с прошлым визитом в localStorage. Результат зависел от браузера и от
// того, заходил ли человек в кабинет до публикации: у одного уведомление
// появлялось, у другого — нет. Теперь источник один — сервер.

// Раз в минуту спрашиваем сервер о новых записях: админ публикует материал, и
// у открытого кабинета уведомление появляется без перезагрузки страницы.
const NOTIFICATIONS_POLL_MS = 60000;

const NOTIFICATION_ICONS = {
  article: '📄',
  event: '📅',
  course: '🐕',
  section: '🐾',
  exercise: '🎯',
};

// id записей, уже показанных в этой вкладке: по ним отличаем действительно
// новое (для всплывающего сообщения) от того, что просто перерисовалось.
let knownNotificationIds = new Set();
let notificationsLoaded = false;
let notificationsPollTimer = null;

function startNotificationsPolling() {
  if (notificationsPollTimer !== null) return;
  notificationsPollTimer = setInterval(
    () => loadNotifications({ notify: true }),
    NOTIFICATIONS_POLL_MS
  );
}

// notify=true — показать всплывающее сообщение о свежих записях.
async function loadNotifications({ notify = false } = {}) {
  const bell = document.getElementById('notificationBell');
  if (bell) bell.style.display = 'flex';

  let data;
  try {
    const response = await fetch(`${API_BASE}/notifications`, {
      credentials: 'include',
      cache: 'no-store',
    });
    // 401 — сессии нет; на страницу входа уже уводит loadProfile().
    if (!response.ok) return;
    data = await response.json();
  } catch (err) {
    console.error('Ошибка загрузки уведомлений:', err);
    return;
  }

  const items = Array.isArray(data.items) ? data.items : [];
  renderNotifications(items, data.unread_count || 0);

  const fresh = items.filter((item) => !knownNotificationIds.has(item.id));
  items.forEach((item) => knownNotificationIds.add(item.id));

  if (!notificationsLoaded) {
    // Первая загрузка в этой вкладке: показываем сводку по непрочитанным, чтобы
    // уведомление было видно и без открытия колокольчика.
    if (data.unread_count > 0) {
      showToast(
        data.unread_count === 1 ? items[0].text : `Новых уведомлений: ${data.unread_count}`,
        'info'
      );
    }
  } else if (notify && fresh.length) {
    // Первую загрузку «новой» не считаем: иначе тост вылезал бы при каждом
    // открытии кабинета.
    showToast(
      fresh.length === 1 ? fresh[0].text : `Новых материалов: ${fresh.length}`,
      'info'
    );
  }
  notificationsLoaded = true;
}

function notificationTime(value) {
  if (!value) return 'только что';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'только что';

  const minutes = Math.round((Date.now() - date.getTime()) / 60000);
  if (minutes < 1) return 'только что';
  if (minutes < 60) return `${minutes} мин назад`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} ч назад`;
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });
}

function renderNotifications(items, unreadCount) {
  const badge = document.getElementById('notificationBadge');
  const list = document.getElementById('notificationList');
  if (!badge || !list) return;

  // Число непрочитанных приходит с сервера: он считает его по всей ленте, а не
  // только по выданным записям. Прочитанность — по read_at, поэтому она не
  // сбрасывается ни при перезагрузке, ни в другом браузере.
  const unread = typeof unreadCount === 'number' ? unreadCount : items.filter((item) => !item.read_at).length;
  if (unread > 0) {
    badge.textContent = unread > 9 ? '9+' : String(unread);
    badge.style.display = 'flex';
  } else {
    badge.style.display = 'none';
  }

  if (!items.length) {
    list.innerHTML = '<p class="empty-notifications">Нет уведомлений</p>';
    return;
  }

  list.innerHTML = items.map((item) => `
    <div class="notification-item${item.read_at ? ' read' : ''}">
      <div class="notification-icon">${NOTIFICATION_ICONS[item.type] || '🔔'}</div>
      <div class="notification-content">
        <p class="notification-text">${escapeHtml(item.text)}</p>
        <span class="notification-time">${escapeHtml(notificationTime(item.created_at))}</span>
      </div>
    </div>
  `).join('');
}

// Открыли список — значит прочитали: просим сервер проставить отметки.
// Записи не удаляются, поэтому «прочитано» видно и после перезагрузки.
async function markNotificationsRead() {
  try {
    const response = await fetch(`${API_BASE}/notifications/read`, {
      method: 'POST',
      credentials: 'include',
    });
    if (!response.ok) return;
    const data = await response.json();
    renderNotifications(
      Array.isArray(data.items) ? data.items : [],
      data.unread_count || 0
    );
  } catch (err) {
    console.error('Ошибка отметки уведомлений прочитанными:', err);
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
  const isOpen = !dropdown.classList.toggle('hidden');
  if (isOpen) markNotificationsRead();
}

function closeNotifications() {
  const dropdown = document.getElementById('notificationDropdown');
  dropdown.classList.add('hidden');
}

async function clearNotifications() {
  try {
    const response = await fetch(`${API_BASE}/notifications`, {
      method: 'DELETE',
      credentials: 'include',
    });
    if (!response.ok) {
      showToast('Не удалось очистить уведомления', 'error');
      return;
    }
  } catch (err) {
    console.error('Ошибка очистки уведомлений:', err);
    showToast('Не удалось очистить уведомления', 'error');
    return;
  }
  knownNotificationIds = new Set();
  renderNotifications([], 0);
  closeNotifications();
}

// ===== Avatar Upload =====
async function uploadAvatar(input) {
  const file = input.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await fetch(`${API_BASE}/users/me/avatar`, {
      method: 'POST',
      credentials: 'include',
      body: formData,
    });

    if (!response.ok) {
      const data = await response.json();
      showToast(errorText(data, 'Ошибка загрузки аватара'), 'error');
      return;
    }

    const user = await response.json();
    const avatarEl = document.getElementById('profileAvatar');
    avatarEl.innerHTML = `<img src="/uploads/avatars/${user.avatar}?t=${Date.now()}" alt="Avatar" style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%;">`;
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

  const email = document.getElementById('editEmail').value;
  const msgEl = document.getElementById('profileMessage');
  const btn = document.getElementById('saveProfileBtn');

  btn.textContent = 'Сохранение...';
  btn.disabled = true;
  msgEl.textContent = '';

  try {
    const response = await fetch(`${API_BASE}/users/me`, {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });

    if (!response.ok) {
      const data = await response.json();
      msgEl.textContent = errorText(data, 'Ошибка сохранения');
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
// Данные собак храним в Map, а в onclick передаём только id: данные, вклеенные
// в атрибут строкой, ломаются на кавычках в кличке и открывают инъекцию JS.
let dogsById = new Map();

// Состояние фотографии в открытой форме собаки:
//   file    — выбран новый файл (загрузим после сохранения данных собаки);
//   remove  — пользователь убрал уже загруженное фото (удалим на сервере);
//   current — имя файла на сервере (для превью и решения об удалении).
let dogPhotoState = { file: null, remove: false, current: null };

const DOG_PHOTO_MAX_BYTES = 5 * 1024 * 1024;
const DOG_PHOTO_DIR = '/uploads/dogs';

function dogPhotoUrl(filename) {
  // encodeURIComponent: имя приходит от сервера, но чужой ввод в URL не пускаем.
  return `${DOG_PHOTO_DIR}/${encodeURIComponent(filename)}`;
}

async function loadDogs() {
  const section = document.getElementById('dogsSection');
  const list = document.getElementById('dogsList');
  const loading = document.getElementById('dogsLoading');

  try {
    const response = await fetch(`${API_BASE}/users/me/dogs`, { credentials: 'include' });

    if (!response.ok) {
      section.classList.add('hidden');
      return;
    }

    const dogs = await response.json();
    section.classList.remove('hidden');

    // Карта собак нужна селекту «с какой собакой гуляли» в курсе: обновляем
    // её всегда, в том числе когда собак нет (пустая карта — тоже ответ).
    dogsById = new Map(dogs.map(dog => [dog.id, dog]));

    if (dogs.length === 0) {
      list.innerHTML = '<p class="empty-text">У вас пока нет собак. Добавьте первую!</p>';
      return;
    }

    list.innerHTML = dogs.map(dog => `
      <div class="dog-card">
        ${dog.photo
          ? `<div class="dog-card-photo"><img src="${dogPhotoUrl(dog.photo)}" alt="Фото собаки ${escapeHtml(dog.name)}"></div>`
          : '<div class="dog-card-photo dog-card-photo-empty">🐕</div>'}
        <div class="dog-card-info">
          <h3 class="dog-card-name">${escapeHtml(dog.name)}</h3>
          <p class="dog-card-breed">${escapeHtml(dog.breed)}</p>
          <p class="dog-card-age">Возраст: ${dog.age} ${getAgeWord(dog.age)}</p>
        </div>
        <div class="dog-card-actions">
          <button class="btn-edit-dog" onclick="openEditDogModal(${dog.id})">✏️</button>
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
  resetDogPhotoState(null);
  document.getElementById('dogModal').classList.remove('hidden');
}

function closeDogModal() {
  document.getElementById('dogModal').classList.add('hidden');
  document.getElementById('dogMessage').textContent = '';
  resetDogPhotoState(null);
}

function openEditDogModal(id) {
  const dog = dogsById.get(id);
  if (!dog) return;

  document.getElementById('dogModalTitle').textContent = 'Редактировать собаку';
  document.getElementById('dogId').value = dog.id;
  document.getElementById('dogName').value = dog.name;
  document.getElementById('dogBreed').value = dog.breed;
  document.getElementById('dogAge').value = dog.age;
  document.getElementById('dogMessage').textContent = '';
  resetDogPhotoState(dog.photo || null);
  document.getElementById('dogModal').classList.remove('hidden');
}

// ===== Фото собаки =====

// Сбрасывает состояние формы фото под конкретную собаку (photo — имя файла
// на сервере или null) и перерисовывает превью.
function resetDogPhotoState(photo) {
  dogPhotoState = { file: null, remove: false, current: photo || null };
  const input = document.getElementById('dogPhotoInput');
  if (input) input.value = '';
  renderDogPhotoPreview();
}

function renderDogPhotoPreview() {
  const preview = document.getElementById('dogPhotoPreview');
  const removeBtn = document.getElementById('dogPhotoRemoveBtn');
  if (!preview || !removeBtn) return;

  const hasPhoto = !!(dogPhotoState.file || (dogPhotoState.current && !dogPhotoState.remove));
  removeBtn.classList.toggle('hidden', !hasPhoto);

  if (dogPhotoState.file) {
    // FileReader, а не URL.createObjectURL: так не нужно помнить про revoke
    // и файл не удерживается в памяти после закрытия формы.
    const reader = new FileReader();
    reader.onload = () => {
      preview.innerHTML = `<img src="${reader.result}" alt="Новое фото собаки">`;
    };
    reader.readAsDataURL(dogPhotoState.file);
  } else if (dogPhotoState.current && !dogPhotoState.remove) {
    preview.innerHTML = `<img src="${dogPhotoUrl(dogPhotoState.current)}" alt="Фото собаки">`;
  } else {
    preview.innerHTML = '<span class="dog-photo-placeholder">🐕</span>';
  }
}

// Выбор файла в форме: проверяем тип и размер на клиенте, чтобы не гонять
// заведомо негодный файл на сервер (сервер проверяет это же повторно).
function previewDogPhoto(input) {
  const file = input.files && input.files[0];
  if (!file) return;

  if (!file.type || !file.type.startsWith('image/')) {
    showToast('Выберите файл изображения', 'error');
    input.value = '';
    return;
  }
  if (file.size > DOG_PHOTO_MAX_BYTES) {
    showToast('Максимальный размер фото: 5 МБ', 'error');
    input.value = '';
    return;
  }

  dogPhotoState.file = file;
  dogPhotoState.remove = false;
  renderDogPhotoPreview();
}

function removeDogPhotoSelection() {
  dogPhotoState.file = null;
  // Фото уже на сервере — удалим его при сохранении. Для новой собаки просто
  // очищаем выбранный файл.
  dogPhotoState.remove = !!dogPhotoState.current;
  const input = document.getElementById('dogPhotoInput');
  if (input) input.value = '';
  renderDogPhotoPreview();
}

// Отправляет фото после сохранения данных собаки. Возвращает текст ошибки или
// null. Отдельный запрос нужен потому, что для новой собаки id известен
// только из ответа POST /me/dogs.
async function saveDogPhoto(dogId) {
  try {
    if (dogPhotoState.file) {
      const formData = new FormData();
      formData.append('file', dogPhotoState.file);
      const response = await fetch(`${API_BASE}/users/me/dogs/${dogId}/photo`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        return errorText(data, 'Не удалось загрузить фото собаки');
      }
      return null;
    }

    if (dogPhotoState.remove) {
      const response = await fetch(`${API_BASE}/users/me/dogs/${dogId}/photo`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (!response.ok) {
        return 'Не удалось удалить фото собаки';
      }
    }
    return null;
  } catch (err) {
    return 'Ошибка сети при сохранении фото';
  }
}

async function saveDog(e) {
  e.preventDefault();

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
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, breed, age }),
    });

    if (!response.ok) {
      const data = await response.json();
      msgEl.textContent = errorText(data, 'Ошибка сохранения');
      msgEl.className = 'message error';
      btn.textContent = 'Сохранить';
      btn.disabled = false;
      return;
    }

    const savedDog = await response.json();

    // Собака уже сохранена; фото отправляем вторым запросом. Ошибка фото не
    // откатывает данные, но пользователь о ней узнаёт.
    const photoError = await saveDogPhoto(savedDog.id);

    btn.textContent = 'Сохранить';
    btn.disabled = false;
    closeDogModal();
    if (photoError) {
      showToast(photoError, 'error');
    } else {
      showToast(isEdit ? 'Собака обновлена' : 'Собака добавлена', 'success');
    }
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

  try {
    const response = await fetch(`${API_BASE}/users/me/dogs/${dogId}`, {
      method: 'DELETE',
      credentials: 'include',
    });

    if (!response.ok) {
      const data = await response.json();
      showToast(errorText(data, 'Ошибка удаления'), 'error');
      return;
    }

    loadDogs();
  } catch (err) {
    showToast('Ошибка сети', 'error');
  }
}

// ===== Курс дрессировки =====
// Курс → секции (1 секция = 1 прогулка) → упражнения. Пользователь отмечает
// каждое упражнение (в том числе по таймеру), выбирает собаку и заполняет
// дневник прогулки; сервер считает прогресс по упражнениям и отдаёт его
// в /courses, а сводную статистику — в /courses/stats.
let currentCourseId = null;

// Идущие таймеры упражнений: id упражнения → { startedAt, seconds, intervalId }.
// Состояние держим вне DOM: перерисовка модалки не должна сбивать отсчёт.
const exerciseTimers = new Map();

const EXERCISE_MEDIA_DIR = '/uploads/exercises';

function exerciseMediaUrl(filename) {
  // Имя файла приходит от сервера, но в URL лишний ввод не пускаем.
  return `${EXERCISE_MEDIA_DIR}/${encodeURIComponent(filename)}`;
}

// «90» → «01:30» — счётчик во время отсчёта.
function formatClock(totalSeconds) {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

// «3750» → «1 ч 02 мин» — уже отработанное время для бейджа.
function formatDuration(totalSeconds) {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(seconds / 60);
  if (minutes >= 60) {
    return `${Math.floor(minutes / 60)} ч ${String(minutes % 60).padStart(2, '0')} мин`;
  }
  if (minutes >= 1) {
    return `${minutes} мин ${String(seconds % 60).padStart(2, '0')} с`;
  }
  return `${seconds} с`;
}

function renderCourses(courses) {
  let container = document.getElementById('coursesContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'coursesContainer';
    container.className = 'dashboard-section';
    document.querySelector('.dashboard-main').appendChild(container);
  }

  container.innerHTML = `
    <h2 class="section-title">Курс дрессировки</h2>
    <div id="courseStatsBar" class="course-stats-bar"></div>
    ${courses.length === 0
      ? '<p class="empty-text">Вам пока не назначен ни один курс. Доступ открывает администратор</p>'
      : courses.map(c => `
          <div class="content-card course-card" onclick="showCourseDetail(${c.id})">
            <h3 class="content-card-title">${escapeHtml(c.title)}</h3>
            <p class="content-card-excerpt">${escapeHtml(c.description || 'Без описания')}</p>
            <div class="course-card-progress">
              <div class="course-progress-bar"><div class="course-progress-fill" style="width: ${c.percent}%"></div></div>
              <span class="course-progress-text">${courseProgressText(c)}</span>
            </div>
          </div>
        `).join('')
    }
  `;

  // Блок статистики рендерится отдельно и асинхронно (не блокирует карточки).
  renderCourseStats();
}

function courseProgressText(course) {
  const walks = `прогулок пройдено ${course.completed_count} из ${course.sections_count}`;
  if (course.exercises_count) {
    return `Выполнено ${course.completed_exercises_count} из ${course.exercises_count} упражнений · ${walks}`;
  }
  return `Пройдено ${course.completed_count} из ${course.sections_count} прогулок`;
}

async function renderCourseStats() {
  const bar = document.getElementById('courseStatsBar');
  if (!bar) return;
  try {
    const response = await fetch(`${API_BASE}/courses/stats`, { credentials: 'include', cache: 'no-store' });
    if (!response.ok) { bar.innerHTML = ''; return; }
    const stats = await response.json();
    if (!stats.total_walks && !stats.completed_exercises) { bar.innerHTML = ''; return; }
    const cards = [
      { value: stats.total_walks, label: 'прогулок всего' },
      { value: stats.walks_this_week, label: 'за неделю' },
      { value: `${stats.current_streak} 🔥`, label: 'дней подряд' },
      { value: stats.completed_exercises, label: 'упражнений' },
    ];
    if (stats.total_minutes) cards.push({ value: stats.total_minutes, label: 'минут на прогулках' });
    if (stats.average_rating) cards.push({ value: stats.average_rating, label: 'средняя оценка' });
    bar.innerHTML = cards.map(card => `
      <div class="course-stat">
        <span class="course-stat-value">${card.value}</span>
        <span class="course-stat-label">${card.label}</span>
      </div>
    `).join('');
  } catch (err) {
    console.error('Ошибка загрузки статистики:', err);
  }
}

async function loadCourses() {
  try {
    const response = await fetch(`${API_BASE}/courses`, { credentials: 'include', cache: 'no-store' });
    if (response.ok) {
      renderCourses(await response.json());
    }
  } catch (err) {
    console.error('Ошибка загрузки курсов:', err);
  }
}

async function showCourseDetail(courseId) {
  currentCourseId = courseId;
  const modal = document.getElementById('courseModal');
  modal.classList.remove('hidden');
  document.getElementById('courseModalTitle').textContent = 'Загрузка...';
  document.getElementById('courseModalProgress').textContent = '';
  document.getElementById('courseModalBody').innerHTML =
    '<p style="color: #5a5f68; text-align: center; padding: 40px 0;">Загрузка курса...</p>';
  await refreshCourseModal();
}

async function refreshCourseModal() {
  if (currentCourseId === null) return;
  try {
    const response = await fetch(`${API_BASE}/courses/${currentCourseId}`, {
      credentials: 'include',
      cache: 'no-store',
    });
    if (response.status === 403) {
      document.getElementById('courseModalTitle').textContent = 'Доступ закрыт';
      document.getElementById('courseModalBody').innerHTML =
        '<p style="color: #e5a92e; text-align: center; padding: 40px 0;">Доступ к этому курсу не открыт. Попросите администратора пригласить вас на курс.</p>';
      return;
    }
    if (!response.ok) throw new Error('HTTP ' + response.status);
    renderCourseModal(await response.json());
  } catch (err) {
    console.error('Ошибка загрузки курса:', err);
    document.getElementById('courseModalTitle').textContent = 'Ошибка загрузки';
    document.getElementById('courseModalBody').innerHTML =
      '<p style="color: #e74c3c; text-align: center; padding: 40px 0;">Не удалось загрузить курс.</p>';
  }
}

// Процент курса считаем по упражнениям (как и сервер): «3 из 5 упражнений» —
// это 60%, даже если прогулка ещё не зачтена целиком.
function coursePercent(course) {
  const total = course.sections.reduce((sum, s) => sum + s.total_exercises, 0);
  const done = course.sections.reduce((sum, s) => sum + s.completed_exercises, 0);
  if (total) return Math.round((done / total) * 100);
  const doneSections = course.sections.filter(s => s.completed).length;
  return course.sections.length ? Math.round((doneSections / course.sections.length) * 100) : 0;
}

function renderCourseModal(course) {
  const total = course.sections.length;
  const done = course.sections.filter(s => s.completed).length;
  const percent = coursePercent(course);

  document.getElementById('courseModalTitle').textContent = course.title;
  document.getElementById('courseModalProgress').textContent = `Пройдено ${done} из ${total} прогулок`;

  const body = document.getElementById('courseModalBody');
  body.innerHTML = `
    ${course.description ? `<p class="course-modal-desc">${escapeHtml(course.description).replace(/\n/g, '<br>')}</p>` : ''}
    <div class="course-progress-bar course-progress-bar-lg"><div class="course-progress-fill" style="width: ${percent}%"></div></div>
    ${total === 0
      ? '<p class="empty-text">В курсе пока нет секций</p>'
      : course.sections.map((s, i) => sectionItemHtml(s, i)).join('')}
  `;
}

function sectionItemHtml(section, index) {
  return `
    <div class="course-section-item ${section.completed ? 'completed' : ''}">
      <div class="course-section-head">
        <h3>${index + 1}. ${escapeHtml(section.title)}</h3>
        ${section.completed ? '<span class="course-status-badge">✓ Пройдено</span>' : ''}
      </div>
      ${section.description ? `<p class="course-section-desc">${escapeHtml(section.description).replace(/\n/g, '<br>')}</p>` : ''}
      <div class="course-section-progress">
        <div class="course-progress-bar"><div class="course-progress-fill" style="width: ${section.percent}%"></div></div>
        <span class="course-progress-text">${section.total_exercises
          ? `Отработано ${section.completed_exercises} из ${section.total_exercises} упражнений`
          : 'Прогулка без упражнений'}</span>
      </div>
      ${section.exercises.length
        ? `<ul class="course-exercises">${section.exercises.map(e => exerciseItemHtml(e)).join('')}</ul>`
        : '<p class="empty-text">Упражнений нет</p>'}
      ${sectionDiaryHtml(section)}
      <button class="btn-small ${section.completed ? 'btn-secondary' : 'btn-primary'}"
              onclick="toggleSectionComplete(${section.id}, ${section.completed})">
        ${section.completed ? 'Пройти заново' : 'Отметить пройденной'}
      </button>
    </div>
  `;
}

function exerciseItemHtml(exercise) {
  const meta = [exercise.repetitions, exercise.duration_minutes ? exercise.duration_minutes + ' мин' : '']
    .filter(Boolean).join(' · ');
  const timer = exerciseTimers.get(exercise.id);
  const elapsed = timer ? timer.seconds : 0;
  const saved = exercise.actual_seconds || 0;

  return `
    <li class="course-exercise ${exercise.completed ? 'done' : ''}">
      <label class="course-exercise-check">
        <input type="checkbox" ${exercise.completed ? 'checked' : ''}
               onchange="toggleExercise(${exercise.id}, this.checked)">
        <span class="course-exercise-title">${escapeHtml(exercise.title)}</span>
        ${meta ? `<span class="course-exercise-meta">${escapeHtml(meta)}</span>` : ''}
      </label>
      ${exercise.description ? `<span class="course-exercise-desc">${escapeHtml(exercise.description).replace(/\n/g, '<br>')}</span>` : ''}
      ${exercise.media ? `<div class="exercise-media-wrap">${exercise.media_type === 'video'
        ? `<video class="exercise-media" src="${exerciseMediaUrl(exercise.media)}" controls preload="metadata"></video>`
        : `<img class="exercise-media" src="${exerciseMediaUrl(exercise.media)}" alt="${escapeHtml(exercise.title)}" loading="lazy">`}</div>` : ''}
      <div class="exercise-timer">
        <button type="button" class="btn-small ${timer ? 'btn-delete' : 'btn-secondary'}"
                id="exerciseTimerBtn-${exercise.id}" onclick="toggleExerciseTimer(${exercise.id})">
          ${timer ? '■ Стоп' : '▶ Таймер'}
        </button>
        <span class="exercise-timer-value ${timer ? 'running' : ''}" id="exerciseTimer-${exercise.id}">${formatClock(elapsed)}</span>
        ${saved ? `<span class="exercise-timer-saved">отработано: ${formatDuration(saved)}</span>` : ''}
      </div>
    </li>
  `;
}

function sectionDiaryHtml(section) {
  const dogOptions = ['<option value="">— не выбрана —</option>']
    .concat(Array.from(dogsById.values()).map(dog =>
      `<option value="${dog.id}" ${section.dog_id === dog.id ? 'selected' : ''}>${escapeHtml(dog.name)}</option>`))
    .join('');
  const ratingOptions = ['<option value="">—</option>']
    .concat([1, 2, 3, 4, 5].map(n =>
      `<option value="${n}" ${section.rating === n ? 'selected' : ''}>${n}</option>`))
    .join('');

  return `
    <div class="section-diary">
      <h4 class="section-diary-title">Дневник прогулки</h4>
      <div class="section-diary-grid">
        <label class="diary-field">
          <span>Собака</span>
          <select onchange="saveSectionDiary(${section.id}, { dog_id: this.value === '' ? null : parseInt(this.value, 10) })">${dogOptions}</select>
        </label>
        <label class="diary-field">
          <span>Оценка прогулки</span>
          <select onchange="saveSectionDiary(${section.id}, { rating: this.value === '' ? null : parseInt(this.value, 10) })">${ratingOptions}</select>
        </label>
        <label class="diary-field">
          <span>Погода</span>
          <input type="text" maxlength="50" placeholder="Например: солнечно"
                 value="${escapeHtml(section.weather || '')}"
                 onchange="saveSectionDiary(${section.id}, { weather: this.value })">
        </label>
        <label class="diary-field">
          <span>Фактически, минут</span>
          <input type="number" min="0" max="1440" value="${section.actual_minutes || ''}" placeholder="0"
                 onchange="saveSectionDiary(${section.id}, { actual_minutes: this.value === '' ? 0 : parseInt(this.value, 10) })">
        </label>
      </div>
      <label class="diary-field diary-field-wide">
        <span>Заметка</span>
        <textarea rows="2" maxlength="2000" placeholder="Как прошла прогулка"
                  onchange="saveSectionDiary(${section.id}, { note: this.value })">${escapeHtml(section.note || '')}</textarea>
      </label>
      <div class="section-diary-hint" id="sectionDiaryHint-${section.id}"></div>
    </div>
  `;
}

// Дневник сохраняем без перерисовки модалки: иначе при вводе заметки слетал бы
// фокус. После успеха показываем «Сохранено» и обновляем статистику.
async function saveSectionDiary(sectionId, changes) {
  const hint = document.getElementById(`sectionDiaryHint-${sectionId}`);
  try {
    const response = await fetch(`${API_BASE}/sections/${sectionId}/progress`, {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(changes),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      if (hint) { hint.textContent = errorText(data, 'Не удалось сохранить'); hint.className = 'section-diary-hint error'; }
      return;
    }
    if (hint) { hint.textContent = 'Сохранено ✓'; hint.className = 'section-diary-hint ok'; }
    renderCourseStats();
  } catch (err) {
    if (hint) { hint.textContent = 'Ошибка сети'; hint.className = 'section-diary-hint error'; }
  }
}

async function toggleExercise(exerciseId, completed) {
  try {
    const options = { method: completed ? 'POST' : 'DELETE', credentials: 'include' };
    if (completed) {
      options.headers = { 'Content-Type': 'application/json' };
      options.body = JSON.stringify({ actual_seconds: 0 });
    }
    const response = await fetch(`${API_BASE}/exercises/${exerciseId}/complete`, options);
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      showToast(errorText(data, 'Не удалось обновить упражнение'), 'error');
      await refreshCourseModal();
      return;
    }
    await refreshCourseModal();
    loadCourses();
    if (completed) showToast('Упражнение отработано ✓', 'success');
  } catch (err) {
    showToast('Ошибка сети', 'error');
  }
}

// --- Таймер упражнения ---
// Отсчёт идёт в браузере, серверу уходит итог в actual_seconds. Остановка
// таймера сразу зачитывает упражнение отработанным.

function setTimerButtonState(exerciseId, running, seconds) {
  const btn = document.getElementById(`exerciseTimerBtn-${exerciseId}`);
  const value = document.getElementById(`exerciseTimer-${exerciseId}`);
  if (btn) {
    btn.textContent = running ? '■ Стоп' : '▶ Таймер';
    btn.classList.toggle('btn-delete', running);
    btn.classList.toggle('btn-secondary', !running);
  }
  if (value) {
    value.classList.toggle('running', running);
    if (!running) value.textContent = formatClock(seconds || 0);
  }
}

function toggleExerciseTimer(exerciseId) {
  if (exerciseTimers.has(exerciseId)) {
    stopExerciseTimer(exerciseId);
    return;
  }
  const timer = { startedAt: Date.now(), seconds: 0, intervalId: null };
  timer.intervalId = setInterval(() => {
    timer.seconds = Math.floor((Date.now() - timer.startedAt) / 1000);
    const el = document.getElementById(`exerciseTimer-${exerciseId}`);
    if (el) el.textContent = formatClock(timer.seconds);
  }, 1000);
  exerciseTimers.set(exerciseId, timer);
  setTimerButtonState(exerciseId, true, 0);
}

async function stopExerciseTimer(exerciseId) {
  const timer = exerciseTimers.get(exerciseId);
  if (!timer) return;
  clearInterval(timer.intervalId);
  exerciseTimers.delete(exerciseId);

  const seconds = Math.max(timer.seconds, Math.floor((Date.now() - timer.startedAt) / 1000));
  setTimerButtonState(exerciseId, false, seconds);

  try {
    const response = await fetch(`${API_BASE}/exercises/${exerciseId}/complete`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actual_seconds: seconds }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      showToast(errorText(data, 'Не удалось сохранить время'), 'error');
      return;
    }
    showToast(`Упражнение отработано за ${formatDuration(seconds)} ✓`, 'success');
    await refreshCourseModal();
    loadCourses();
  } catch (err) {
    showToast('Ошибка сети', 'error');
  }
}

function stopAllExerciseTimers() {
  exerciseTimers.forEach(timer => clearInterval(timer.intervalId));
  exerciseTimers.clear();
}

async function toggleSectionComplete(sectionId, completed) {
  try {
    const response = await fetch(`${API_BASE}/sections/${sectionId}/complete`, {
      method: completed ? 'DELETE' : 'POST',
      credentials: 'include',
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      showToast(errorText(data, 'Не удалось обновить отметку'), 'error');
      return;
    }
    await refreshCourseModal();
    loadCourses();   // обновить прогресс в карточке курса
    if (!completed) showToast('Прогулка отмечена ✓', 'success');
  } catch (err) {
    showToast('Ошибка сети', 'error');
  }
}

function closeCourseDetail() {
  // Незавершённые таймеры не сохраняем: закрыл модалку — отсчёт сброшен.
  stopAllExerciseTimers();
  document.getElementById('courseModal').classList.add('hidden');
  currentCourseId = null;
}

// Закрытие модалки курса по клику на overlay
document.addEventListener('click', (e) => {
  const modal = document.getElementById('courseModal');
  if (e.target === modal) closeCourseDetail();
});

// ===== Toast Notifications =====
// FastAPI отдаёт detail строкой («Курс не найден») либо массивом ошибок
// валидации ([{loc, msg}]). Без нормализации в интерфейс попадало
// «[object Object]» вместо причины. Приводим оба варианта к одной строке.
function errorText(data, fallback) {
  const detail = data && data.detail;
  if (typeof detail === 'string' && detail) return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map(item => (item && item.msg ? String(item.msg) : null)).filter(Boolean);
    if (parts.length) return parts.join('; ');
  }
  return fallback;
}

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
  // Дописывать токен к ссылкам больше не нужно: он в HttpOnly-cookie и уходит
  // с каждым запросом сам. Нет сессии — loadProfile() вернёт на страницу входа.
  loadProfile();
});
