const API = "";

function getToken() {
  return localStorage.getItem("myportmap_token");
}

function setToken(t) {
  localStorage.setItem("myportmap_token", t);
}

function requireAuth() {
  if (!getToken()) {
    window.location.href = "login.html";
  }
}

async function apiFetch(path, options = {}) {
  options.headers = options.headers || {};
  const token = getToken();
  if (token) options.headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(API + path, options);
  if (res.status === 401) {
    localStorage.removeItem("myportmap_token");
    window.location.href = "login.html";
    return;
  }
  return res;
}

function logout() {
  localStorage.removeItem("myportmap_token");
  window.location.href = "login.html";
}
