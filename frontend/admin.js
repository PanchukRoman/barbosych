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

// ===== Custom Delete Confirmation Modal =====
let deleteCallback = null; // Функция, которая выполнится после подтверждения удаления

function showDeleteModal(title, message, onConfirm) {
  deleteCallback = onConfirm;

  // Создаём модальное окно если ещё нет
  let modal = document.getElementById('deleteModal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'deleteModal';
    modal.className = 'delete-modal-overlay';
    modal.innerHTML = `
      <div class="delete-modal">
        <div class="delete-modal-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"/>
          </svg>
        </div>
        <h3 class="delete-modal-title">${escapeHtml(title)}</h3>
        <p class="delete-modal-message">${escapeHtml(message)}</p>
        <div class="delete-modal-actions">
          <button class="btn-delete-confirm" onclick="confirmDelete()">Удалить</button>
          <button class="btn-cancel-delete" onclick="cancelDelete()">Отмена</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    // Закрытие по клику на overlay
    modal.addEventListener('click', (e) => {
      if (e.target === modal) cancelDelete();
    });

    // Закрытие по Escape
    document.addEventListener('keydown', handleModalEscape);
  }
}

function handleModalEscape(e) {
  if (e.key === 'Escape') cancelDelete();
}

function confirmDelete() {
  if (deleteCallback) deleteCallback();
  cancelDelete();
}

function cancelDelete() {
  deleteCallback = null;
  const modal = document.getElementById('deleteModal');
  if (modal) modal.remove();
  document.removeEventListener('keydown', handleModalEscape);
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
  document.getElementById('articleFormTitle').textContent = article ? 'Редактировать статью' : 'Новая статья';

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
    showMessage('articleMessage', 'Заголовок и содержание обязательны', 'error');
    return;
  }

  const btn = document.querySelector('#articleForm .btn-primary');
  btn.disabled = true;
  btn.textContent = editingArticleId ? 'Сохраняю...' : 'Публикую...';

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
      showMessage('articleMessage', editingArticleId ? 'Статья обновлена!' : 'Статья опубликована!', 'success');
      hideArticleForm();
      loadArticles();
    } else {
      const data = await response.json();
      showMessage('articleMessage', data.detail || 'Ошибка', 'error');
    }
  } catch (err) {
    showMessage('articleMessage', 'Ошибка сети', 'error');
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.textContent = editingArticleId ? 'Сохранить статью' : 'Сохранить статью';
  }
}

async function deleteArticle(id) {
  // Показываем кастомное модальное окно подтверждения
  showDeleteModal(
    'Удаление статьи',
    'Вы уверены, что хотите удалить эту статью? Это действие нельзя отменить.',
    async () => {
      await performDeleteArticle(id);
    }
  );
}

async function performDeleteArticle(id) {
  const token = localStorage.getItem('access_token');
  if (!token) return;

  const btn = event?.target;
  if (btn) btn.disabled = true;

  try {
    const response = await fetch(`${API_BASE}/admin/articles/${id}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` },
    });

    if (response.ok) {
      // Визуально удаляем элемент из списка с анимацией
      const articleItem = document.querySelector(`button[onclick="deleteArticle(${id})"]`).closest('.admin-list-item');
      if (articleItem) {
        articleItem.style.transition = 'all 0.3s ease';
        articleItem.style.opacity = '0';
        articleItem.style.transform = 'translateX(-20px)';
        articleItem.style.maxHeight = articleItem.offsetHeight + 'px';
        setTimeout(() => {
          articleItem.style.maxHeight = '0';
          articleItem.style.padding = '0';
          articleItem.style.margin = '0';
        }, 300);
        setTimeout(() => loadArticles(), 400);
      } else {
        loadArticles();
      }
    } else {
      const data = await response.json();
      showMessage('articleMessage', data.detail || 'Ошибка удаления статьи', 'error');
    }
  } catch (err) {
    showMessage('articleMessage', 'Ошибка сети', 'error');
    console.error(err);
  } finally {
    if (btn) btn.disabled = false;
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
      throw new Error('Не удалось загрузить статьи');
    }

    const articles = await response.json();
    loadingEl.classList.add('hidden');

    if (articles.length === 0) {
      listEl.innerHTML = '<div class="empty-state"><p>Статей пока нет. Создайте первую!</p></div>';
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
          <button class="btn-small btn-edit" onclick='editArticle(${JSON.stringify(article).replace(/'/g, "&#39;")})'>Изменить</button>
          <button class="btn-small btn-delete" onclick="deleteArticle(${article.id})">Удалить</button>
        </div>
      `;
      listEl.appendChild(item);
    });
  } catch (err) {
    loadingEl.classList.add('hidden');
    listEl.innerHTML = '<div class="empty-state"><p>Ошибка загрузки статей</p></div>';
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
  document.getElementById('eventFormTitle').textContent = event ? 'Редактировать событие' : 'Новое событие';

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
    showMessage('eventMessage', 'Заголовок, описание и дата обязательны', 'error');
    return;
  }

  const btn = document.querySelector('#eventForm .btn-primary');
  btn.disabled = true;
  btn.textContent = editingEventId ? 'Сохраняю...' : 'Создаю...';

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
      showMessage('eventMessage', editingEventId ? 'Событие обновлено!' : 'Событие создано!', 'success');
      hideEventForm();
      loadEvents();
    } else {
      const data = await response.json();
      showMessage('eventMessage', data.detail || 'Ошибка', 'error');
    }
  } catch (err) {
    showMessage('eventMessage', 'Ошибка сети', 'error');
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.textContent = editingEventId ? 'Сохранить событие' : 'Сохранить событие';
  }
}

async function deleteEvent(id) {
  // Показываем кастомное модальное окно подтверждения
  showDeleteModal(
    'Удаление события',
    'Вы уверены, что хотите удалить это событие? Все записи также будут удалены.',
    async () => {
      await performDeleteEvent(id);
    }
  );
}

async function performDeleteEvent(id) {
  const token = localStorage.getItem('access_token');
  if (!token) return;

  const btn = event?.target;
  if (btn) btn.disabled = true;

  try {
    const response = await fetch(`${API_BASE}/admin/events/${id}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` },
    });

    if (response.ok) {
      // Визуально удаляем элемент из списка с анимацией
      const eventItem = document.querySelector(`button[onclick="deleteEvent(${id})"]`).closest('.admin-list-item');
      if (eventItem) {
        eventItem.style.transition = 'all 0.3s ease';
        eventItem.style.opacity = '0';
        eventItem.style.transform = 'translateX(-20px)';
        eventItem.style.maxHeight = eventItem.offsetHeight + 'px';
        setTimeout(() => {
          eventItem.style.maxHeight = '0';
          eventItem.style.padding = '0';
          eventItem.style.margin = '0';
        }, 300);
        setTimeout(() => loadEvents(), 400);
      } else {
        loadEvents();
      }
    } else {
      const data = await response.json();
      showMessage('eventMessage', data.detail || 'Ошибка удаления события', 'error');
    }
  } catch (err) {
    showMessage('eventMessage', 'Ошибка сети', 'error');
    console.error(err);
  } finally {
    if (btn) btn.disabled = false;
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
      throw new Error('Не удалось загрузить события');
    }

    const events = await response.json();
    loadingEl.classList.add('hidden');

    if (events.length === 0) {
      listEl.innerHTML = '<div class="empty-state"><p>Событий пока нет. Создайте первое!</p></div>';
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
          <span>👥 Макс: ${event.max_participants}</span>
        </div>
        <div class="list-item-actions">
          <button class="btn-small btn-edit" onclick='editEvent(${JSON.stringify(event).replace(/'/g, "&#39;")})'>Изменить</button>
          <button class="btn-small btn-delete" onclick="deleteEvent(${event.id})">Удалить</button>
        </div>
      `;
      listEl.appendChild(item);
    });
  } catch (err) {
    loadingEl.classList.add('hidden');
    listEl.innerHTML = '<div class="empty-state"><p>Ошибка загрузки событий</p></div>';
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
  loadArticles();
});
