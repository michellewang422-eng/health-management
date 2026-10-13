// ============================================================
// api.js —— 所有页面共用的小工具
// 每个页面都会先引入这个文件：<script src="api.js"></script>
// ============================================================

// 前端和后端是三个独立的程序，前端靠下面两个地址找到它们。
// 换端口 / 换机器，只改这两行。
const USER_API = "http://127.0.0.1:8000";     // User-management-service：姓名、邮箱、登录
const HEALTH_API = "http://127.0.0.1:8001";   // health-service：档案、打卡、标准

// FastAPI 的错误有两种形状：
//   detail 是字符串（404 / 409 / 401 …）：{"detail": "邮箱未注册"}
//   detail 是数组（422 数据不合法）：{"detail": [{"loc": ["body","age"], "msg": "..."}]}
function errorText(data, status) {
  if (!data || !data.detail) return `请求失败 (${status})`;
  if (typeof data.detail === "string") return data.detail;
  return data.detail.map(e => `${e.loc.slice(1).join(".")}: ${e.msg}`).join("；");
}

// 所有请求都走这个函数：成功返回解析好的数据，失败抛出 Error（message 是给用户看的中文）
async function request(base, path, options = {}) {
  let resp;
  try {
    resp = await fetch(base + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (e) {
    // fetch 本身抛错 = 网络层出问题（后端没启动、被 CORS 拦住等），根本没拿到响应
    throw new Error("无法连接服务器，请确认后端已启动");
  }
  if (resp.status === 204) return null;                  // 204 = 成功但没有内容
  const data = await resp.json().catch(() => null);      // 响应体不是 JSON 也不要崩
  if (!resp.ok) throw new Error(errorText(data, resp.status));
  return data;
}

const userApi = (path, opt) => request(USER_API, path, opt);
const healthApi = (path, opt) => request(HEALTH_API, path, opt);

// ---------------- 登录状态 ----------------
// 登录成功后，我们把后端返回的用户对象用 JSON.stringify 存进 localStorage 的 "currentUser"。
// localStorage 是浏览器按网站保存的小字典，刷新页面也不会丢。
// 注意：这不是真正的安全登录（没有密码、没有令牌），任何人改一下 localStorage 就能"变成"别人。
function getCurrentUser() {
  const raw = localStorage.getItem("currentUser");
  return raw ? JSON.parse(raw) : null;
}

// 每个需要登录的页面开头调用：没登录就跳回登录页
function requireLogin() {
  const u = getCurrentUser();
  if (!u) location.href = "login.html";
  return u;
}

function logout() {
  localStorage.removeItem("currentUser");
  location.href = "login.html";
}

// ---------------- 小工具 ----------------
// 把用户输入里的 < > & 等转义，防止有人在姓名里写 <script> 来攻击页面（XSS）。
// 规则：凡是要拼进 innerHTML 的"用户数据"，都先过一遍 esc()；
// 或者干脆不用 innerHTML，改用 textContent（它天生不会把内容当 HTML 解析）。
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function fullName(user) {
  return `${user.first_name} ${user.last_name}`;
}

// 导航栏：写在这一个地方，所有页面共用，加新页面只改这里。
const NAV_ITEMS = [
  { href: "dashboard.html", label: "仪表盘" },
  { href: "report.html", label: "周期报告" },
  { href: "profile.html", label: "我的档案" },
];

// 在页面里放一个 <nav id="nav"></nav>，然后调用 renderNav("dashboard.html")，
// 参数是当前页面的文件名，用来高亮当前页。
function renderNav(current) {
  const user = getCurrentUser();
  const nav = document.getElementById("nav");
  const links = NAV_ITEMS.map(item =>
    `<a href="${item.href}"${item.href === current ? ' class="active"' : ""}>${esc(item.label)}</a>`
  ).join("");
  nav.innerHTML = `
    <div class="nav-inner">
      <span class="brand">健康管理</span>
      <div class="nav-links">${links}</div>
      <span class="who"></span>
      <button type="button" class="link-btn" id="logout-btn">退出</button>
    </div>`;
  // 姓名是用户输入的内容，用 textContent 填入，不会被当成 HTML
  nav.querySelector(".who").textContent = user ? fullName(user) : "";
  document.getElementById("logout-btn").addEventListener("click", logout);
}

// 在红色提示区显示错误；message 为空则隐藏。统一用 textContent（见上面 esc 的说明）。
function showError(el, message) {
  el.textContent = message || "";
  el.hidden = !message;
}
