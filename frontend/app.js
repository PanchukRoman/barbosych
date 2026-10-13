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

// ===== Configuration =====
const API_BASE = ''; // relative to current host

// ===== Tab Switching =====
function switchTab(tab) {
  const signinForm = document.getElementById('signinForm');
  const registerForm = document.getElementById('registerForm');
  const tabs = document.querySelectorAll('.tab');

  tabs.forEach(t => t.classList.remove('active'));
  document.querySelector(`[data-tab="${tab}"]`).classList.add('active');

  if (tab === 'signin') {
    signinForm.classList.remove('hidden');
    registerForm.classList.add('hidden');
  } else {
    signinForm.classList.add('hidden');
    registerForm.classList.remove('hidden');
  }

  // Clear messages
  clearMessage('signinMessage');
  clearMessage('registerMessage');
}

// ===== Message Helpers =====
function showMessage(elementId, text, type) {
  const el = document.getElementById(elementId);
  el.textContent = text;
  el.className = `message ${type}`;
}

function clearMessage(elementId) {
  const el = document.getElementById(elementId);
  el.textContent = '';
  el.className = 'message';
}

// ===== Sign In =====
async function handleSignin(event) {
  event.preventDefault();
  clearMessage('signinMessage');

  const email = document.getElementById('signinEmail').value.trim();
  const password = document.getElementById('signinPassword').value;
  const btn = document.getElementById('signinBtn');

  btn.disabled = true;
  btn.textContent = 'Вхожу...';

  try {
    const formData = new URLSearchParams();
    formData.set('username', email);
    formData.set('password', password);

    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      credentials: 'include',
      body: formData,
    });

    const data = await response.json();

    if (response.ok) {
      // Токен отдан в HttpOnly-cookie — браузер отправит её сам, а JS
      // токен не читает и нигде не хранит (защита от XSS-кражи).
      showMessage('signinMessage', 'Вход выполнен! Перенаправление...', 'success');
      setTimeout(() => {
        window.location.href = '/dashboard';
      }, 800);
    } else {
      showMessage('signinMessage', errorText(data, 'Ошибка входа'), 'error');
    }
  } catch (err) {
    showMessage('signinMessage', 'Не удалось подключиться к серверу', 'error');
    console.error('Signin error:', err);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Войти';
  }
}

// ===== Register =====
async function handleRegister(event) {
  event.preventDefault();
  clearMessage('registerMessage');

  const email = document.getElementById('registerEmail').value.trim();
  const password = document.getElementById('registerPassword').value;
  const btn = document.getElementById('registerBtn');

  btn.disabled = true;
  btn.textContent = 'Регистрирую...';

  try {
    const response = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();

    if (response.ok) {
      // Авто-логин после регистрации
      showMessage('registerMessage', 'Регистрация успешна! Автоматический вход...', 'success');

      const loginResponse = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        credentials: 'include',
        body: new URLSearchParams({ username: email, password }),
      });

      if (loginResponse.ok) {
        // Cookie уже выставлена сервером — просто переходим в кабинет
        setTimeout(() => {
          window.location.href = '/dashboard';
        }, 800);
      } else {
        showMessage('registerMessage', 'Регистрация успешна, но вход не удался. Попробуйте войти вручную.', 'error');
      }
    } else {
      showMessage('registerMessage', errorText(data, 'Ошибка регистрации'), 'error');
    }
  } catch (err) {
    showMessage('registerMessage', 'Не удалось подключиться к серверу', 'error');
    console.error('Register error:', err);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Зарегистрироваться';
  }
}

// ===== Уже авторизован? =====
// Токен в HttpOnly-cookie, из JS его не прочитать. Поэтому просто спрашиваем
// сервер: если сессия жива — уводим в личный кабинет, иначе остаёмся на входе.
document.addEventListener('DOMContentLoaded', async () => {
  try {
    const response = await fetch(`${API_BASE}/users/me`, { credentials: 'include' });
    if (response.ok) {
      window.location.href = '/dashboard';
    }
  } catch (err) {
    // Сервер недоступен — не мешаем пользователю войти вручную
    console.error('Session check failed:', err);
  }
});
