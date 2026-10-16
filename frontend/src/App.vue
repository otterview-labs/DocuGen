<template>
  <div id="app">
    <div class="bg-pattern"></div>

    <!-- Header Navigation -->
    <header class="app-header">
      <div class="header-container">
        <div class="brand">
          <div class="brand-icon" aria-hidden="true">Q</div>
          <div class="brand-text">
            <div class="brand-name">Quill</div>
            <div class="brand-tagline">知识与文档工作台</div>
          </div>
        </div>

        <nav class="main-nav" aria-label="工作台导航">
          <RouterLink to="/knowledge" class="nav-link">知识库</RouterLink>
          <RouterLink to="/writing" class="nav-link">文档写作</RouterLink>
          <RouterLink to="/" class="nav-link">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <rect x="3" y="3" width="7" height="7" rx="1"/>
              <rect x="14" y="3" width="7" height="7" rx="1"/>
              <rect x="3" y="14" width="7" height="7" rx="1"/>
              <rect x="14" y="14" width="7" height="7" rx="1"/>
            </svg>
            文档模板
          </RouterLink>
          <RouterLink to="/create" class="nav-link">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            上传模板
          </RouterLink>
        </nav>

        <div class="header-actions">
          <label class="key-label">访问密钥
            <input type="password" v-model="accessKey" @change="saveKey" autocomplete="off" placeholder="本地访问可留空" />
          </label>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="app-main">
      <RouterView />
    </main>

    <!-- Footer -->
    <footer class="app-footer">
      <div class="footer-container">
        <p>Otterview Quill · 让资料成为有据可查的文档。</p>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { RouterLink, RouterView } from 'vue-router';
import { ref } from 'vue';
const accessKey = ref(sessionStorage.getItem('quill-key') || '');
function saveKey() { sessionStorage.setItem('quill-key', accessKey.value); window.location.reload(); }
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --bg-primary: #0f172a;
  --bg-secondary: #1e293b;
  --bg-tertiary: #334155;
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-tertiary: #64748b;
  --accent: #3b82f6;
  --accent-secondary: #8b5cf6;
  --border: rgba(255, 255, 255, 0.1);
  --shadow: rgba(0, 0, 0, 0.5);
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.6;
}

#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  position: relative;
}

.bg-pattern {
  position: fixed;
  inset: 0;
  background-image:
    radial-gradient(circle at 20% 30%, rgba(59, 130, 246, 0.15), transparent 40%),
    radial-gradient(circle at 80% 70%, rgba(139, 92, 246, 0.15), transparent 40%);
  pointer-events: none;
  z-index: 0;
}

/* Header */
.app-header {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(15, 23, 42, 0.8);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
}

.header-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 16px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--accent), var(--accent-secondary));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

.brand-text {
  display: flex;
  flex-direction: column;
}

.brand-name {
  font-size: 18px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.5px;
}

.brand-tagline {
  font-size: 11px;
  color: var(--text-tertiary);
  font-weight: 500;
}

.main-nav {
  display: flex;
  gap: 8px;
  flex: 1;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 8px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.3s ease;
  position: relative;
}

.nav-link svg {
  width: 18px;
  height: 18px;
  stroke-width: 2;
}

.nav-link:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.05);
}

.nav-link.router-link-active {
  color: #60a5fa;
  background: rgba(59, 130, 246, 0.15);
}

.header-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.3s ease;
}

.action-btn svg {
  width: 20px;
  height: 20px;
  stroke-width: 2;
}

.action-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: var(--accent);
  color: var(--text-primary);
}

/* Main */
.app-main {
  flex: 1;
  position: relative;
  z-index: 1;
}

/* Footer */
.app-footer {
  position: relative;
  z-index: 1;
  padding: 24px 0;
  border-top: 1px solid var(--border);
  margin-top: 60px;
}

.footer-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 24px;
  text-align: center;
}

.footer-container p {
  font-size: 14px;
  color: var(--text-tertiary);
}

/* Responsive */
@media (max-width: 768px) {
  .header-container {
    flex-wrap: wrap;
  }

  .main-nav {
    width: 100%;
    order: 3;
  }

  .brand-tagline {
    display: none;
  }

  .nav-link {
    flex: 1;
    justify-content: center;
  }
}
</style>

<style>
:root { --bg-primary: #f8fafc; --bg-secondary: #ffffff; --text-primary: #142536; --text-secondary: #475569; --text-tertiary: #52627a; --accent: #245d75; --border: #dce3e8; }
.bg-pattern { display:none; }
.app-header { background: #fff; backdrop-filter: none; }
.brand-icon { background:#245d75; box-shadow:none; font-family:Georgia,serif; }
.key-label { display:flex; flex-direction:column; gap:3px; font-size:11px; color:#475569; }
.key-label input { width:160px; padding:6px 8px; border:1px solid #cbd5e1; border-radius:4px; }
:focus-visible { outline:3px solid #245d75; outline-offset:3px; }
::selection { background:#cce5ee; color:#142536; }
.workspace { max-width:1120px; margin:40px auto; padding:0 24px; }
.workspace h1 { margin-bottom:10px; font-size:30px; }
.workspace p { color:#475569; margin-bottom:20px; }
.work-form { display:grid; gap:16px; max-width:760px; margin:24px 0; }
.work-form label { display:grid; gap:6px; font-weight:600; }
.work-form input,.work-form textarea,.work-form select { padding:11px; border:1px solid #b6c2ce; border-radius:6px; background:white; color:#142536; font:inherit; width:100%; }
.work-actions { display:flex; flex-wrap:wrap; gap:12px; }
.work-actions button,.work-button { padding:10px 18px; border:0; background:#245d75; color:white; border-radius:6px; cursor:pointer; font:inherit; }
.work-actions button:disabled { opacity:.5; cursor:wait; }
.work-result { white-space:pre-wrap; overflow-wrap:anywhere; border-top:1px solid #ccd6df; padding:20px 0; }
.work-status { color:#874315 !important; white-space:pre-wrap; }
.work-list { list-style:none; margin:20px 0; }
.work-list li { padding:16px 0; border-bottom:1px solid #dce3e8; }
.nav-link.router-link-active {color:#17495f;background:#e0edf3;}
input::placeholder,textarea::placeholder {color:#52627a;opacity:1;}
@media(max-width:850px) { .header-container {flex-wrap:wrap; gap:12px;} .main-nav {order:3; flex:0 0 100%; display:grid;grid-template-columns:repeat(4,minmax(0,1fr));overflow:visible;} .nav-link {white-space:nowrap; padding:8px 4px;font-size:13px;} .nav-link svg {display:none;} .workspace {margin-top:24px;} }
@media(prefers-reduced-motion:reduce) { *,*::before,*::after {animation:none!important;transition:none!important;scroll-behavior:auto!important;} }
</style>
