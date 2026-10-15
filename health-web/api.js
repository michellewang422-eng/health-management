// ============================================================
// api.js —— 所有页面共用的小工具
// 每个页面都会先引入这个文件：<script src="api.js"></script>
// ============================================================

// 前端和后端是三个独立的程序，前端靠下面两个地址找到它们。
// 本机打开（localhost / 127.0.0.1）用本机地址；放在 GitHub Pages 等公网地址上时，
// 用 PUBLIC_* 里填的隧道地址（Cloudflare Tunnel / ngrok 给你的 https 地址，末尾不要加 /）。
// PUBLIC_* 留空 = 还没有可用的后端，页面会直接显示「服务器暂未开启」。
const PUBLIC_USER_API = "";     // 例：https://user-xxxx.trycloudflare.com
const PUBLIC_HEALTH_API = "";   // 例：https://health-xxxx.trycloudflare.com
const PROJECT_URL = "https://github.com/michellewang422-eng/health-management";

const IS_LOCAL = ["localhost", "127.0.0.1", "[::1]", ""].includes(location.hostname);
const USER_API = IS_LOCAL ? "http://127.0.0.1:8000" : PUBLIC_USER_API;      // User-management-service：姓名、邮箱、登录
const HEALTH_API = IS_LOCAL ? "http://127.0.0.1:8001" : PUBLIC_HEALTH_API;  // health-service：档案、打卡、标准

// ---------------- 「服务器暂未开启」提示层 ----------------
// 演示服务器跑在作者自己的电脑上，不一定一直开着。后端连不上时，
// 不让访客看到一个会报错的空表单，而是盖一层说明页（带项目链接和重试按钮）。
let unavailableShown = false;

function showUnavailable() {
  if (unavailableShown || !document.body) return;
  unavailableShown = true;
  const box = document.createElement("div");
  box.className = "unavailable";
  box.setAttribute("role", "alert");
  const card = document.createElement("div");
  card.className = "unavailable-card";
  const h = document.createElement("h2");
  h.textContent = "演示服务器暂未开启";
  const p1 = document.createElement("p");
  p1.textContent = "这个健康管理网站的后端运行在作者自己的电脑上，目前没有开机或服务未启动，所以暂时无法使用。";
  const p2 = document.createElement("p");
  p2.textContent = "The back end of this demo runs on the author's own computer, which is offline right now. The site will work again once the server is started.";
  const links = document.createElement("p");
  const a = document.createElement("a");
  a.href = PROJECT_URL;
  a.textContent = "查看项目源码与截图 / View source and screenshots on GitHub";
  a.target = "_blank";
  a.rel = "noopener";
  links.appendChild(a);
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "btn";
  btn.textContent = "重试 / Retry";
  btn.addEventListener("click", () => location.reload());
  card.append(h, p1, p2, links, btn);
  box.appendChild(card);
  document.body.appendChild(box);
}

// 探测一个后端是否在线：3 秒内拿到响应就算在线。
// 隧道断开时 Cloudflare 返回的错误页没有 CORS 头，浏览器会让 fetch 抛错，同样判为离线。
async function isUp(base, path) {
  if (!base) return false;
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 3000);
  try {
    const r = await fetch(base + path, { signal: ctl.signal });
    return r.status < 500;
  } catch (e) {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

async function checkBackends() {
  const [userUp, healthUp] = await Promise.all([isUp(USER_API, "/"), isUp(HEALTH_API, "/health")]);
  if (!userUp || !healthUp) showUnavailable();
}

document.addEventListener("DOMContentLoaded", checkBackends);

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
    showUnavailable();
    throw new Error("无法连接服务器，请确认后端已启动");
  }
  if (resp.status === 204) return null;                  // 204 = 成功但没有内容
  const data = await resp.json().catch(() => null);      // 响应体不是 JSON 也不要崩
  if (!resp.ok) {
    const err = new Error(errorText(data, resp.status));
    err.status = resp.status;       // 页面可以据此区分"没有档案(404)"和别的错误
    throw err;
  }
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

// 用户在用户服务里存在、但还没有健康档案时（比如用户服务里原有的老用户）：
// 在提示区显示说明和「去建立档案」的链接，而不是只丢一句"健康档案不存在"。
function showNoProfile(el) {
  el.textContent = "你还没有健康档案，请先去「我的档案」填写必填项并保存。 ";
  const a = document.createElement("a");
  a.href = "profile.html";
  a.textContent = "去建立档案";
  el.appendChild(a);
  el.hidden = false;
}

// 页面中央的提示对话框（用 <dialog>，不用 alert：样式统一、不会卡住浏览器自动化）。
// 点「好的」或按 Esc 关闭；返回一个 Promise，关闭后才会 resolve（要"关掉再跳转"时 await 它）。
// message 一律用 textContent 填，里面有 <script> 也只是文字。
function showDialog(message, { title = "提示", kind = "ok" } = {}) {
  return new Promise(resolve => {
    const dlg = document.createElement("dialog");
    dlg.className = `dialog ${kind}`;
    const h = document.createElement("h3");
    h.textContent = title;
    const p = document.createElement("p");
    p.textContent = message;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn";
    btn.textContent = "好的";
    btn.addEventListener("click", () => dlg.close());
    dlg.append(h, p, btn);
    dlg.addEventListener("close", () => { dlg.remove(); resolve(); });
    document.body.appendChild(dlg);
    dlg.showModal();
    btn.focus();
  });
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
  { href: "calories.html", label: "卡路里计算器" },
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
