// ===== Configuration =====
const API_BASE = '';

// ===== Sidebar =====
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
  if (sidebar.classList.contains('open')) closeSidebar();
  else openSidebar();
});

sidebarClose.addEventListener('click', closeSidebar);
sidebarOverlay.addEventListener('click', closeSidebar);

// Desktop sidebar toggle
if (desktopSidebarToggle) {
  desktopSidebarToggle.addEventListener('click', () => {
    sidebar.classList.toggle('collapsed');
  });
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeSidebar();
});

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

// ===== Admin Tabs =====
function switchAdminTab(tab) {
  document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
  document.querySelector(`[data-tab="${tab}"]`).classList.add('active');

  document.getElementById('articlesSection').classList.toggle('hidden', tab !== 'articles');
  document.getElementById('eventsSection').classList.toggle('hidden', tab !== 'events');
  document.getElementById('courseSection').classList.toggle('hidden', tab !== 'course');

  if (tab === 'articles') loadArticles();
  if (tab === 'events') loadEvents();
  if (tab === 'course') loadCourses();
}

// ===== Message Helpers =====
function showMessage(elementId, text, type) {
  const el = document.getElementById(elementId);
  el.textContent = text;
  el.className = `message ${type}`;
  setTimeout(() => { el.textContent = ''; el.className = 'message'; }, 5000);
}

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

// Универсальная отрисовка загрузки/пустого состояния ВНУТРИ списка.
// Раньше элементы #articlesLoading/#eventsLoading/#coursesLoading лежали внутри
// контейнера списка, а `listEl.innerHTML = ''` их уничтожал: второй вызов
// loadX() падал на `null.classList` и список переставал обновляться после
// создания/удаления объекта. Теперь загрузчик рисуем заново при каждой загрузке.
function showListLoader(listEl) {
  listEl.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
}

function emptyState(text) {
  return `<div class="empty-state"><p>${escapeHtml(text)}</p></div>`;
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
    const body = JSON.stringify({ title, content, excerpt });

    const response = await fetch(url, {
      method,
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body,
    });

    if (response.ok) {
      showMessage('articleMessage', editingArticleId ? 'Статья обновлена!' : 'Статья опубликована!', 'success');
      hideArticleForm();
      loadArticles();
    } else {
      const data = await response.json();
      showMessage('articleMessage', errorText(data, 'Ошибка'), 'error');
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
  try {
    const response = await fetch(`${API_BASE}/admin/articles/${id}`, {
      method: 'DELETE',
      credentials: 'include',
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
      showMessage('articleMessage', errorText(data, 'Ошибка удаления статьи'), 'error');
    }
  } catch (err) {
    showMessage('articleMessage', 'Ошибка сети', 'error');
    console.error(err);
  }
}

async function loadArticles() {
  const listEl = document.getElementById('articlesList');
  showListLoader(listEl);

  try {
    const response = await fetch(`${API_BASE}/admin/articles`, { credentials: 'include', cache: 'no-store' });

    if (!response.ok) {
      if (response.status === 403) {
        window.location.href = '/dashboard';
        return;
      }
      throw new Error('Не удалось загрузить статьи');
    }

    const articles = await response.json();

    if (articles.length === 0) {
      listEl.innerHTML = emptyState('Статей пока нет. Создайте первую!');
      return;
    }

    listEl.innerHTML = '';
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
          <button class="btn-small btn-edit" onclick="editArticle(${article.id})">Изменить</button>
          <button class="btn-small btn-delete" onclick="deleteArticle(${article.id})">Удалить</button>
        </div>
      `;
      listEl.appendChild(item);
    });
  } catch (err) {
    listEl.innerHTML = emptyState('Ошибка загрузки статей');
    console.error(err);
  }
}

async function editArticle(id) {
  // В списке статьи приходят без полного текста (ArticleList), поэтому за
  // деталями идём отдельным запросом. В onclick передаём id, а не JSON:
  // вклеенный в атрибут JSON — лишний вес и дыра для инъекции.
  try {
    const response = await fetch(`${API_BASE}/admin/articles/${id}`, {
      credentials: 'include',
    });
    if (!response.ok) {
      showMessage('articleMessage', 'Не удалось загрузить статью', 'error');
      return;
    }
    showArticleForm(await response.json());
  } catch (err) {
    showMessage('articleMessage', 'Ошибка сети', 'error');
    console.error(err);
  }
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
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body,
    });

    if (response.ok) {
      showMessage('eventMessage', editingEventId ? 'Событие обновлено!' : 'Событие создано!', 'success');
      hideEventForm();
      loadEvents();
    } else {
      const data = await response.json();
      showMessage('eventMessage', errorText(data, 'Ошибка'), 'error');
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
  try {
    const response = await fetch(`${API_BASE}/admin/events/${id}`, {
      method: 'DELETE',
      credentials: 'include',
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
      showMessage('eventMessage', errorText(data, 'Ошибка удаления события'), 'error');
    }
  } catch (err) {
    showMessage('eventMessage', 'Ошибка сети', 'error');
    console.error(err);
  }
}

async function loadEvents() {
  const listEl = document.getElementById('eventsList');
  showListLoader(listEl);

  try {
    const response = await fetch(`${API_BASE}/admin/events`, { credentials: 'include', cache: 'no-store' });

    if (!response.ok) {
      if (response.status === 403) {
        window.location.href = '/dashboard';
        return;
      }
      throw new Error('Не удалось загрузить события');
    }

    const events = await response.json();

    if (events.length === 0) {
      listEl.innerHTML = emptyState('Событий пока нет. Создайте первое!');
      return;
    }

    listEl.innerHTML = '';
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
          <button class="btn-small btn-edit" onclick="editEvent(${event.id})">Изменить</button>
          <button class="btn-small btn-delete" onclick="deleteEvent(${event.id})">Удалить</button>
        </div>
      `;
      listEl.appendChild(item);
    });
  } catch (err) {
    listEl.innerHTML = emptyState('Ошибка загрузки событий');
    console.error(err);
  }
}

async function editEvent(id) {
  // Как и со статьями: в onclick — только id, детали берём отдельным запросом
  try {
    const response = await fetch(`${API_BASE}/admin/events/${id}`, {
      credentials: 'include',
    });
    if (!response.ok) {
      showMessage('eventMessage', 'Не удалось загрузить событие', 'error');
      return;
    }
    showEventForm(await response.json());
  } catch (err) {
    showMessage('eventMessage', 'Ошибка сети', 'error');
    console.error(err);
  }
}

// ===== Helpers =====
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ===== Init =====
document.addEventListener('DOMContentLoaded', () => {
  // Страница /admin уже защищена на сервере (cookie), дописывать токен в
  // ссылки не нужно. 403 от API тоже вернёт на личный кабинет.
  loadArticles();
});

// ===== Course (курс дрессировки) =====
// Курс → секции (1 секция = 1 прогулка) → упражнения.
// Как и в статьях/событиях: в onclick передаём только id, а сами данные
// храним в Map — это безопаснее, чем вклеивать JSON в HTML-атрибут.
let editingCourseId = null;
let expandedCourseId = null;        // какой курс раскрыт (для перезагрузки секций)
let sectionsByIdCache = new Map();
let exercisesByIdCache = new Map();
let coursesByIdCache = new Map();
let enrollCourseId = null;

// Медиа упражнения приходит «отложенно»: секция/упражнение сначала сохраняются
// (нужен id), и только потом грузится выбранный файл. Так медиа работает и у
// только что созданного упражнения, а не теряется до перезагрузки страницы.
const EXERCISE_MEDIA_DIR = '/uploads/exercises';
const EXERCISE_MEDIA_MAX_BYTES = 25 * 1024 * 1024;
let exerciseMediaState = { file: null, remove: false, current: null, type: 'image', objectUrl: null };

function exerciseMediaUrl(filename) {
  // Имя приходит от сервера, но чужой ввод в URL не пускаем.
  return `${EXERCISE_MEDIA_DIR}/${encodeURIComponent(filename)}`;
}

async function loadCourses() {
  const listEl = document.getElementById('coursesList');
  showListLoader(listEl);

  try {
    const response = await fetch(`${API_BASE}/admin/courses`, { credentials: 'include', cache: 'no-store' });
    if (!response.ok) {
      if (response.status === 403) { window.location.href = '/dashboard'; return; }
      throw new Error('Не удалось загрузить курсы');
    }
    const courses = await response.json();

    if (courses.length === 0) {
      listEl.innerHTML = emptyState('Курсов пока нет. Создайте первый!');
      expandedCourseId = null;
      return;
    }
    renderCourses(courses);

    // Список строится заново, поэтому раскрытый ранее курс надо раскрыть снова.
    if (expandedCourseId !== null) {
      const container = document.getElementById(`courseSections-${expandedCourseId}`);
      if (container) {
        container.dataset.loaded = '1';
        await loadCourseSections(expandedCourseId);
      } else {
        expandedCourseId = null;   // курс удалён — раскрывать нечего
      }
    }
  } catch (err) {
    listEl.innerHTML = emptyState('Ошибка загрузки курсов');
    console.error(err);
  }
}

function renderCourses(courses) {
  const listEl = document.getElementById('coursesList');
  listEl.innerHTML = '';
  coursesByIdCache = new Map(courses.map(course => [course.id, course]));

  courses.forEach(course => {
    const item = document.createElement('div');
    item.className = 'admin-list-item';
    item.innerHTML = `
      <div class="list-item-header">
        <h3 class="list-item-title">${escapeHtml(course.title)}</h3>
        <span class="list-item-date">${course.sections_count} секц. · ${course.enrolled_count || 0} учеников</span>
      </div>
      <p class="list-item-excerpt">${escapeHtml(course.description || 'Без описания')}</p>
      <div class="list-item-actions">
        <button class="btn-small btn-secondary" onclick="toggleCourseSections(${course.id})">Секции</button>
        <button class="btn-small btn-primary" onclick="openEnrollModal(${course.id})">Пригласить на курс</button>
        <button class="btn-small btn-edit" onclick="editCourse(${course.id})">Изменить</button>
        <button class="btn-small btn-delete" onclick="deleteCourse(${course.id})">Удалить</button>
      </div>
      <div class="course-sections" id="courseSections-${course.id}"></div>
    `;
    listEl.appendChild(item);
  });
}

function showCourseForm(course = null) {
  const form = document.getElementById('courseForm');
  form.classList.remove('hidden');
  document.getElementById('courseFormTitle').textContent = course ? 'Редактировать курс' : 'Новый курс';

  if (course) {
    editingCourseId = course.id;
    document.getElementById('courseTitle').value = course.title;
    document.getElementById('courseDescription').value = course.description || '';
  } else {
    editingCourseId = null;
    document.getElementById('courseTitle').value = '';
    document.getElementById('courseDescription').value = '';
  }
  form.scrollIntoView({ behavior: 'smooth' });
}

function hideCourseForm() {
  document.getElementById('courseForm').classList.add('hidden');
  editingCourseId = null;
}

async function saveCourse() {
  const title = document.getElementById('courseTitle').value.trim();
  const description = document.getElementById('courseDescription').value.trim();

  if (title.length < 3) {
    showMessage('courseMessage', 'Название курса — минимум 3 символа', 'error');
    return;
  }

  const btn = document.querySelector('#courseForm .btn-primary');
  btn.disabled = true;
  btn.textContent = 'Сохраняю...';

  try {
    const url = editingCourseId
      ? `${API_BASE}/admin/courses/${editingCourseId}`
      : `${API_BASE}/admin/courses`;
    const method = editingCourseId ? 'PUT' : 'POST';

    const response = await fetch(url, {
      method,
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, description }),
    });

    if (response.ok) {
      showMessage('courseMessage', editingCourseId ? 'Курс обновлён!' : 'Курс создан!', 'success');
      hideCourseForm();
      loadCourses();
    } else {
      const data = await response.json();
      showMessage('courseMessage', errorText(data, 'Ошибка'), 'error');
    }
  } catch (err) {
    showMessage('courseMessage', 'Ошибка сети', 'error');
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Сохранить курс';
  }
}

async function editCourse(id) {
  // В списке нет полного описания при больших объёмах — берём курс отдельным
  // запросом (как со статьями и событиями).
  try {
    const response = await fetch(`${API_BASE}/admin/courses/${id}`, { credentials: 'include' });
    if (!response.ok) {
      showMessage('courseMessage', 'Не удалось загрузить курс', 'error');
      return;
    }
    showCourseForm(await response.json());
  } catch (err) {
    showMessage('courseMessage', 'Ошибка сети', 'error');
    console.error(err);
  }
}

function deleteCourse(id) {
  showDeleteModal(
    'Удаление курса',
    'Удалить курс вместе со всеми секциями, упражнениями и отметками пользователей? Действие необратимо.',
    async () => { await performDeleteCourse(id); }
  );
}

async function performDeleteCourse(id) {
  try {
    const response = await fetch(`${API_BASE}/admin/courses/${id}`, {
      method: 'DELETE',
      credentials: 'include',
    });
    if (response.ok) {
      if (expandedCourseId === id) expandedCourseId = null;
      loadCourses();
    } else {
      const data = await response.json();
      showMessage('courseMessage', errorText(data, 'Ошибка удаления курса'), 'error');
    }
  } catch (err) {
    showMessage('courseMessage', 'Ошибка сети', 'error');
    console.error(err);
  }
}

// --- Секции (прогулки) ---

async function toggleCourseSections(courseId) {
  const container = document.getElementById(`courseSections-${courseId}`);
  if (!container) return;

  if (container.dataset.loaded === '1') {
    // Повторный клик — сворачиваем.
    container.innerHTML = '';
    container.dataset.loaded = '';
    if (expandedCourseId === courseId) expandedCourseId = null;
    return;
  }

  container.dataset.loaded = '1';
  expandedCourseId = courseId;
  await loadCourseSections(courseId);
}

async function loadCourseSections(courseId) {
  const container = document.getElementById(`courseSections-${courseId}`);
  if (!container) return;
  container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const response = await fetch(`${API_BASE}/admin/courses/${courseId}`, { credentials: 'include' });
    if (!response.ok) {
      container.innerHTML = '<p class="empty-text">Не удалось загрузить секции</p>';
      return;
    }
    const course = await response.json();

    sectionsByIdCache = new Map(course.sections.map(s => [s.id, s]));
    exercisesByIdCache = new Map();
    course.sections.forEach(s => s.exercises.forEach(e => exercisesByIdCache.set(e.id, e)));

    renderCourseSections(container, course);
  } catch (err) {
    container.innerHTML = '<p class="empty-text">Ошибка сети</p>';
    console.error(err);
  }
}

function renderCourseSections(container, course) {
  const sections = course.sections;
  container.innerHTML = `
    <div class="course-sections-header">
      <span class="course-sections-count">Секции (прогулки): ${sections.length}</span>
      <button class="btn-small btn-primary" onclick="openSectionModal(${course.id})">+ Секция</button>
    </div>
    ${sections.length === 0
      ? '<p class="empty-text">Секций пока нет. Добавьте первую прогулку.</p>'
      : sections.map((s, i) => `
        <div class="course-section-card">
          <div class="course-section-head">
            <h4>${i + 1}. ${escapeHtml(s.title)}</h4>
            <div class="course-section-actions">
              <button class="btn-small btn-edit" onclick="openSectionModal(${course.id}, ${s.id})">Изменить</button>
              <button class="btn-small btn-delete" onclick="deleteSection(${s.id})">Удалить</button>
            </div>
          </div>
          ${s.description ? `<p class="course-section-desc">${escapeHtml(s.description).replace(/\n/g, '<br>')}</p>` : ''}
          <div class="exercise-list">
            ${s.exercises.length === 0
              ? '<p class="empty-text">Упражнений нет</p>'
              : s.exercises.map((e, j) => `
                <div class="exercise-row">
                  <span class="exercise-index">${j + 1}.</span>
                  ${e.media ? `<span class="exercise-thumb">${e.media_type === 'video'
                    ? `<video class="exercise-thumb-media" src="${exerciseMediaUrl(e.media)}" muted preload="metadata"></video>`
                    : `<img class="exercise-thumb-media" src="${exerciseMediaUrl(e.media)}" alt="" loading="lazy">`}</span>` : ''}
                  <span class="exercise-title">${escapeHtml(e.title)}</span>
                  ${e.repetitions ? `<span class="exercise-meta">${escapeHtml(e.repetitions)}</span>` : ''}
                  ${e.duration_minutes ? `<span class="exercise-meta">${e.duration_minutes} мин</span>` : ''}
                  ${e.media ? `<span class="exercise-media-badge">${e.media_type === 'video' ? 'видео' : 'фото'}</span>` : ''}
                  <span class="exercise-actions">
                    <button class="btn-small btn-edit" title="Изменить" onclick="openExerciseModal(${s.id}, ${e.id})">✎</button>
                    ${e.media ? `<button class="btn-small btn-secondary" title="Убрать медиа" onclick="deleteExerciseMedia(${e.id})">🖼✕</button>` : ''}
                    <button class="btn-small btn-delete" title="Удалить" onclick="deleteExercise(${e.id})">✕</button>
                  </span>
                </div>
              `).join('')}
          </div>
          <button class="btn-small btn-secondary" onclick="openExerciseModal(${s.id})">+ Упражнение</button>
        </div>
      `).join('')}
  `;
}

function openSectionModal(courseId, sectionId) {
  const section = sectionId ? sectionsByIdCache.get(sectionId) : null;
  document.getElementById('sectionModalTitle').textContent = section ? 'Редактировать секцию' : 'Новая секция';
  document.getElementById('sectionId').value = section ? section.id : '';
  document.getElementById('sectionCourseId').value = courseId;
  document.getElementById('sectionTitle').value = section ? section.title : '';
  document.getElementById('sectionDescription').value = section ? section.description : '';
  document.getElementById('sectionOrder').value = section ? section.order_index : '';
  document.getElementById('sectionMessage').textContent = '';
  document.getElementById('sectionMessage').className = 'message';
  document.getElementById('sectionModal').classList.remove('hidden');
}

function closeSectionModal() {
  document.getElementById('sectionModal').classList.add('hidden');
}

async function saveSection(e) {
  e.preventDefault();

  const sectionId = document.getElementById('sectionId').value;
  const courseId = document.getElementById('sectionCourseId').value;
  const title = document.getElementById('sectionTitle').value.trim();
  const description = document.getElementById('sectionDescription').value.trim();
  const orderRaw = document.getElementById('sectionOrder').value;

  if (!title) {
    showMessage('sectionMessage', 'Название обязательно', 'error');
    return;
  }

  const payload = { title, description };
  if (orderRaw !== '') payload.order_index = parseInt(orderRaw);

  const btn = document.getElementById('saveSectionBtn');
  btn.disabled = true;
  btn.textContent = 'Сохраняю...';

  try {
    const url = sectionId
      ? `${API_BASE}/admin/sections/${sectionId}`
      : `${API_BASE}/admin/courses/${courseId}/sections`;
    const method = sectionId ? 'PUT' : 'POST';

    const response = await fetch(url, {
      method,
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (response.ok) {
      closeSectionModal();
      await loadCourses();   // обновляет список и раскрытый курс (секции)
    } else {
      const data = await response.json();
      showMessage('sectionMessage', errorText(data, 'Ошибка сохранения'), 'error');
    }
  } catch (err) {
    showMessage('sectionMessage', 'Ошибка сети', 'error');
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Сохранить';
  }
}

function deleteSection(sectionId) {
  showDeleteModal(
    'Удаление секции',
    'Удалить прогулку вместе с её упражнениями и отметками пользователей?',
    async () => {
      try {
        const response = await fetch(`${API_BASE}/admin/sections/${sectionId}`, {
          method: 'DELETE',
          credentials: 'include',
        });
        if (response.ok) {
          await loadCourses();
        } else {
          const data = await response.json();
          showMessage('courseMessage', errorText(data, 'Ошибка удаления секции'), 'error');
        }
      } catch (err) {
        showMessage('courseMessage', 'Ошибка сети', 'error');
      }
    }
  );
}

// --- Упражнения ---

function openExerciseModal(sectionId, exerciseId) {
  const exercise = exerciseId ? exercisesByIdCache.get(exerciseId) : null;
  document.getElementById('exerciseModalTitle').textContent = exercise ? 'Редактировать упражнение' : 'Новое упражнение';
  document.getElementById('exerciseId').value = exercise ? exercise.id : '';
  document.getElementById('exerciseSectionId').value = sectionId;
  document.getElementById('exerciseTitle').value = exercise ? exercise.title : '';
  document.getElementById('exerciseDescription').value = exercise ? exercise.description : '';
  document.getElementById('exerciseRepetitions').value = exercise ? exercise.repetitions : '';
  document.getElementById('exerciseDuration').value = exercise ? exercise.duration_minutes : '';
  document.getElementById('exerciseOrder').value = exercise ? exercise.order_index : '';
  document.getElementById('exerciseMessage').textContent = '';
  document.getElementById('exerciseMessage').className = 'message';
  resetExerciseMediaState(exercise);
  document.getElementById('exerciseModal').classList.remove('hidden');
}

function closeExerciseModal() {
  document.getElementById('exerciseModal').classList.add('hidden');
  releaseExerciseMediaUrl();
}

// --- Медиа упражнения (превью и отложенная загрузка) ---

function releaseExerciseMediaUrl() {
  if (exerciseMediaState.objectUrl) {
    URL.revokeObjectURL(exerciseMediaState.objectUrl);
    exerciseMediaState.objectUrl = null;
  }
}

function resetExerciseMediaState(exercise) {
  releaseExerciseMediaUrl();
  exerciseMediaState = {
    file: null,
    remove: false,
    current: exercise && exercise.media ? exercise.media : null,
    type: exercise && exercise.media_type ? exercise.media_type : 'image',
    objectUrl: null,
  };
  const input = document.getElementById('exerciseMediaInput');
  if (input) input.value = '';
  renderExerciseMediaPreview();
}

function renderExerciseMediaPreview() {
  const preview = document.getElementById('exerciseMediaPreview');
  const removeBtn = document.getElementById('exerciseMediaRemoveBtn');
  if (!preview) return;

  const { file, remove, current, type, objectUrl } = exerciseMediaState;
  if (remove || (!file && !current)) {
    preview.innerHTML = '<span class="exercise-media-placeholder">🎬</span>';
    if (removeBtn) removeBtn.classList.add('hidden');
    return;
  }

  const kind = file ? (file.type.startsWith('video') ? 'video' : 'image') : type;
  const src = file ? objectUrl : exerciseMediaUrl(current);
  preview.innerHTML = kind === 'video'
    ? `<video class="exercise-media-preview-media" src="${src}" controls preload="metadata"></video>`
    : `<img class="exercise-media-preview-media" src="${src}" alt="Медиа упражнения">`;
  if (removeBtn) removeBtn.classList.remove('hidden');
}

function previewExerciseMedia(input) {
  const file = input.files && input.files[0];
  if (!file) return;
  if (file.size > EXERCISE_MEDIA_MAX_BYTES) {
    showMessage('exerciseMessage', 'Файл больше 25 МБ', 'error');
    input.value = '';
    return;
  }
  releaseExerciseMediaUrl();
  exerciseMediaState.file = file;
  exerciseMediaState.remove = false;
  exerciseMediaState.objectUrl = URL.createObjectURL(file);
  renderExerciseMediaPreview();
}

function removeExerciseMediaSelection() {
  releaseExerciseMediaUrl();
  exerciseMediaState.file = null;
  // «Убрать» у уже загруженного медиа — это запрос на удаление на сервере.
  exerciseMediaState.remove = !!exerciseMediaState.current;
  const input = document.getElementById('exerciseMediaInput');
  if (input) input.value = '';
  renderExerciseMediaPreview();
}

async function uploadExerciseMedia(exerciseId) {
  const form = new FormData();
  form.append('file', exerciseMediaState.file);
  const response = await fetch(`${API_BASE}/admin/exercises/${exerciseId}/media`, {
    method: 'POST',
    credentials: 'include',
    body: form,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(errorText(data, 'Не удалось загрузить медиа'));
  }
  return response.json();
}

async function deleteExerciseMedia(exerciseId) {
  try {
    const response = await fetch(`${API_BASE}/admin/exercises/${exerciseId}/media`, {
      method: 'DELETE',
      credentials: 'include',
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      showMessage('courseMessage', errorText(data, 'Не удалось убрать медиа'), 'error');
      return;
    }
    showMessage('courseMessage', 'Медиа упражнения удалено', 'success');
    await loadCourses();
  } catch (err) {
    showMessage('courseMessage', 'Ошибка сети', 'error');
    console.error(err);
  }
}

async function saveExercise(e) {
  e.preventDefault();

  const exerciseId = document.getElementById('exerciseId').value;
  const sectionId = document.getElementById('exerciseSectionId').value;
  const title = document.getElementById('exerciseTitle').value.trim();
  const description = document.getElementById('exerciseDescription').value.trim();
  const repetitions = document.getElementById('exerciseRepetitions').value.trim();
  const durationRaw = document.getElementById('exerciseDuration').value;
  const orderRaw = document.getElementById('exerciseOrder').value;

  if (!title) {
    showMessage('exerciseMessage', 'Название обязательно', 'error');
    return;
  }

  const payload = {
    title,
    description,
    repetitions,
    duration_minutes: durationRaw === '' ? 0 : parseInt(durationRaw),
  };
  if (orderRaw !== '') payload.order_index = parseInt(orderRaw);

  const btn = document.getElementById('saveExerciseBtn');
  btn.disabled = true;
  btn.textContent = 'Сохраняю...';

  try {
    const url = exerciseId
      ? `${API_BASE}/admin/exercises/${exerciseId}`
      : `${API_BASE}/admin/sections/${sectionId}/exercises`;
    const method = exerciseId ? 'PUT' : 'POST';

    const response = await fetch(url, {
      method,
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (response.ok) {
      const saved = await response.json().catch(() => null);
      const savedId = saved ? saved.id : (exerciseId ? parseInt(exerciseId, 10) : null);
      // Запоминаем id: если загрузка медиа упадёт, повторное «Сохранить»
      // обновит это упражнение, а не создаст дубликат.
      if (savedId) document.getElementById('exerciseId').value = savedId;

      if (savedId && exerciseMediaState.file) {
        try {
          await uploadExerciseMedia(savedId);
        } catch (err) {
          showMessage('exerciseMessage', err.message, 'error');
          return;   // модалку не закрываем — можно повторить загрузку
        }
      } else if (savedId && exerciseMediaState.remove && exerciseMediaState.current) {
        await fetch(`${API_BASE}/admin/exercises/${savedId}/media`, {
          method: 'DELETE',
          credentials: 'include',
        });
      }

      closeExerciseModal();
      await loadCourses();
    } else {
      const data = await response.json();
      showMessage('exerciseMessage', errorText(data, 'Ошибка сохранения'), 'error');
    }
  } catch (err) {
    showMessage('exerciseMessage', 'Ошибка сети', 'error');
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Сохранить';
  }
}

function deleteExercise(exerciseId) {
  showDeleteModal(
    'Удаление упражнения',
    'Удалить это упражнение из секции?',
    async () => {
      try {
        const response = await fetch(`${API_BASE}/admin/exercises/${exerciseId}`, {
          method: 'DELETE',
          credentials: 'include',
        });
        if (response.ok) {
          await loadCourses();
        } else {
          const data = await response.json();
          showMessage('courseMessage', errorText(data, 'Ошибка удаления упражнения'), 'error');
        }
      } catch (err) {
        showMessage('courseMessage', 'Ошибка сети', 'error');
      }
    }
  );
}

// ===== Зачисление на курс (доступ пользователей) =====
// По умолчанию курс пользователю недоступен. Кнопка «Пригласить на курс»
// открывает список всех зарегистрированных пользователей с чекбоксами:
// отметил — зачислил, снял — отозвал доступ.

async function openEnrollModal(courseId) {
  enrollCourseId = courseId;
  const course = coursesByIdCache.get(courseId);
  document.getElementById('enrollModalTitle').textContent =
    course ? `Пригласить на курс: ${course.title}` : 'Пригласить на курс';
  document.getElementById('enrollMessage').textContent = '';
  document.getElementById('enrollMessage').className = 'message';
  document.getElementById('enrollList').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
  document.getElementById('enrollModal').classList.remove('hidden');
  await loadEnrollments(courseId);
}

function closeEnrollModal() {
  document.getElementById('enrollModal').classList.add('hidden');
  enrollCourseId = null;
}

async function loadEnrollments(courseId) {
  const listEl = document.getElementById('enrollList');
  try {
    const response = await fetch(`${API_BASE}/admin/courses/${courseId}/enrollments`, {
      credentials: 'include',
      cache: 'no-store',
    });
    if (!response.ok) {
      listEl.innerHTML = '<p class="empty-text">Не удалось загрузить пользователей</p>';
      return;
    }
    renderEnrollments(await response.json());
  } catch (err) {
    listEl.innerHTML = '<p class="empty-text">Ошибка сети</p>';
    console.error(err);
  }
}

function renderEnrollments(students) {
  const listEl = document.getElementById('enrollList');
  if (students.length === 0) {
    listEl.innerHTML = '<p class="empty-text">Зарегистрированных пользователей нет</p>';
    return;
  }
  listEl.innerHTML = students.map(student => `
    <label class="enroll-row">
      <input type="checkbox" ${student.enrolled ? 'checked' : ''}
             onchange="toggleEnrollment(${student.user_id}, this.checked)">
      <span class="enroll-name">${escapeHtml(student.email)}</span>
      ${student.role === 'admin' ? '<span class="enroll-badge">админ</span>' : ''}
    </label>
  `).join('');
}

async function toggleEnrollment(userId, enroll) {
  const url = enroll
    ? `${API_BASE}/admin/courses/${enrollCourseId}/enrollments`
    : `${API_BASE}/admin/courses/${enrollCourseId}/enrollments/${userId}`;
  const options = enroll
    ? {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId }),
      }
    : { method: 'DELETE', credentials: 'include' };

  try {
    const response = await fetch(url, options);
    if (response.ok) {
      showMessage('enrollMessage', enroll ? 'Пользователь зачислен на курс' : 'Доступ отозван', 'success');
      loadCourses();   // обновить счётчик учеников в карточке
    } else {
      const data = await response.json().catch(() => ({}));
      showMessage('enrollMessage', errorText(data, 'Не удалось сохранить'), 'error');
      loadEnrollments(enrollCourseId);   // вернуть чекбокс в актуальное состояние
    }
  } catch (err) {
    showMessage('enrollMessage', 'Ошибка сети', 'error');
    console.error(err);
  }
}
