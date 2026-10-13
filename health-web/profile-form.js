// ============================================================
// profile-form.js —— 注册页和档案页共用的"健康字段"表单
//
// 两个页面都要填年龄、性别、身高……，把这一大段 HTML 和读写逻辑放在这里，
// 两个页面各调用一次，就不用复制粘贴两份（改一处，两页同时生效）。
// 使用前要先引入 api.js。
// ============================================================

const HEALTH_FIELDS_HTML = `
  <h2>基本信息（必填）</h2>
  <div class="row">
    <div class="field">
      <label for="age">年龄</label>
      <input id="age" name="age" type="number" min="18" max="100" step="1" required>
      <div class="hint">18–100</div>
    </div>
    <div class="field">
      <label for="gender">性别</label>
      <select id="gender" name="gender" required>
        <option value="">请选择</option>
        <option value="male">男</option>
        <option value="female">女</option>
      </select>
    </div>
    <div class="field">
      <label for="height_cm">身高 (cm)</label>
      <input id="height_cm" name="height_cm" type="number" min="100" max="250" step="any" required>
      <div class="hint">100–250</div>
    </div>
    <div class="field">
      <label for="weight_kg">体重 (kg)</label>
      <input id="weight_kg" name="weight_kg" type="number" min="30" max="300" step="any" required>
      <div class="hint">30–300，也是周期的起始体重</div>
    </div>
    <div class="field">
      <label for="sleep_hours">平时每晚睡眠 (小时) <span class="opt">选填</span></label>
      <input id="sleep_hours" name="sleep_hours" type="number" min="2" max="14" step="0.5">
      <div class="hint">2–14，参考 7–9 小时</div>
    </div>
  </div>

  <h2>体检指标 <span class="opt">（选填，留空即可）</span></h2>
  <div class="row">
    <div class="field">
      <label for="baseline_glucose_mgdl">空腹血糖 (mg/dL)</label>
      <input id="baseline_glucose_mgdl" name="baseline_glucose_mgdl" type="number" min="40" max="600" step="any">
    </div>
    <div class="field">
      <label for="baseline_cholesterol_mgdl">总胆固醇 (mg/dL)</label>
      <input id="baseline_cholesterol_mgdl" name="baseline_cholesterol_mgdl" type="number" min="80" max="500" step="any">
    </div>
    <div class="field">
      <label for="baseline_systolic">收缩压 (mmHg)</label>
      <input id="baseline_systolic" name="baseline_systolic" type="number" min="70" max="250" step="1">
    </div>
    <div class="field">
      <label for="baseline_diastolic">舒张压 (mmHg)</label>
      <input id="baseline_diastolic" name="baseline_diastolic" type="number" min="40" max="150" step="1">
    </div>
  </div>
  <div class="hint" style="margin:-8px 0 16px">收缩压和舒张压要一起填，或者都不填。</div>

  <h2>目标与周期 <span class="opt">（选填）</span></h2>
  <div class="row">
    <div class="field">
      <label for="goal_type">目标类型</label>
      <select id="goal_type" name="goal_type">
        <option value="maintain">保持体重</option>
        <option value="lose_weight">减重</option>
        <option value="gain_weight">增重</option>
      </select>
    </div>
    <div class="field">
      <label for="cycle_days">监测周期（天）</label>
      <input id="cycle_days" name="cycle_days" type="number" min="7" max="365" step="1" placeholder="默认 30">
    </div>
  </div>
  <div class="field">
    <label for="goal_note">目标描述</label>
    <textarea id="goal_note" name="goal_note" rows="2" maxlength="200" placeholder="比如：三个月减 3 公斤（最多 200 字）"></textarea>
  </div>
`;

// 把健康字段画进页面里某个容器（比如 <div id="health-fields"></div>）
function renderHealthFields(container) {
  container.innerHTML = HEALTH_FIELDS_HTML;   // 这段 HTML 是我们自己写死的，不含用户输入，可以放心用 innerHTML
}

// 空字符串 -> null，其它 -> 数字。
// 为什么要转：没填的数字框，它的 value 是 ""（空字符串），不是 null；
// 直接发给后端，后端会因为 "" 不是数字而报 422。
const num = v => (v === "" || v == null ? null : Number(v));

// 从表单里读出健康字段，整理成后端要的 JSON 对象
function readHealthFields(root) {
  const v = name => root.querySelector(`[name="${name}"]`).value;
  return {
    age: num(v("age")),
    gender: v("gender"),
    height_cm: num(v("height_cm")),
    weight_kg: num(v("weight_kg")),
    sleep_hours: num(v("sleep_hours")),              // 选填：留空 -> null
    baseline_glucose_mgdl: num(v("baseline_glucose_mgdl")),
    baseline_cholesterol_mgdl: num(v("baseline_cholesterol_mgdl")),
    baseline_systolic: num(v("baseline_systolic")),
    baseline_diastolic: num(v("baseline_diastolic")),
    goal_type: v("goal_type"),
    goal_note: v("goal_note").trim() || null,        // 空描述 -> null（清空）
    cycle_days: num(v("cycle_days")) ?? 30,          // 留空就发 30，和后端默认值一致
  };
}

// 把后端返回的档案填回表单（编辑页用）。null 要显示成空字符串，不能显示成 "null"
function fillHealthFields(root, profile) {
  for (const [key, value] of Object.entries(profile)) {
    const el = root.querySelector(`[name="${key}"]`);
    if (el) el.value = value ?? "";
  }
}

// 前端校验：血压必须成对。返回错误文字，没问题返回 ""。
// （后端也会检查；前端提前提示是为了体验，后端检查才是真正的防线）
function checkBloodPressure(values) {
  const hasS = values.baseline_systolic !== null;
  const hasD = values.baseline_diastolic !== null;
  if (hasS !== hasD) return "血压必须同时填写收缩压和舒张压";
  if (hasS && values.baseline_systolic <= values.baseline_diastolic) return "收缩压必须大于舒张压";
  return "";
}
