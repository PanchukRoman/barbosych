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
  btn.textContent = 'Signing in...';

  try {
    const formData = new URLSearchParams();
    formData.set('username', email);
    formData.set('password', password);

    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData,
    });

    const data = await response.json();

    if (response.ok) {
      // Сохраняем токен и перенаправляем
      localStorage.setItem('access_token', data.access_token);
      showMessage('signinMessage', 'Вход выполнен! Перенаправление...', 'success');
      setTimeout(() => {
        window.location.href = '/dashboard';
      }, 800);
    } else {
      showMessage('signinMessage', data.detail || 'Ошибка входа', 'error');
    }
  } catch (err) {
    showMessage('signinMessage', 'Не удалось подключиться к серверу', 'error');
    console.error('Signin error:', err);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Sign in';
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
  btn.textContent = 'Registering...';

  try {
    const response = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();

    if (response.ok) {
      // Авто-логин после регистрации
      showMessage('registerMessage', 'Регистрация успешна! Автоматический вход...', 'success');

      const loginResponse = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username: email, password }),
      });

      const loginData = await loginResponse.json();

      if (loginResponse.ok) {
        localStorage.setItem('access_token', loginData.access_token);
        setTimeout(() => {
          window.location.href = '/dashboard';
        }, 800);
      } else {
        showMessage('registerMessage', 'Регистрация успешна, но вход не удался. Попробуйте войти вручную.', 'error');
      }
    } else {
      showMessage('registerMessage', data.detail || 'Ошибка регистрации', 'error');
    }
  } catch (err) {
    showMessage('registerMessage', 'Не удалось подключиться к серверу', 'error');
    console.error('Register error:', err);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Register';
  }
}

// ===== Check for existing token on load =====
document.addEventListener('DOMContentLoaded', () => {
  const token = localStorage.getItem('access_token');
  if (token) {
    // Уже авторизован — перенаправляем на dashboard
    window.location.href = '/dashboard';
  }
});
