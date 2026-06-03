"use strict";

// ── 0. Burger menu ────────────────────────────────────────
const burger = document.getElementById("burger");
const navMobile = document.getElementById("nav-mobile");
if (burger && navMobile) {
  burger.addEventListener("click", () => {
    const isOpen = navMobile.classList.toggle("open");
    burger.classList.toggle("open", isOpen);
    burger.setAttribute("aria-expanded", isOpen);
  });
  // закрыть при клике на ссылку
  navMobile.querySelectorAll("a").forEach((a) => {
    a.addEventListener("click", () => {
      navMobile.classList.remove("open");
      burger.classList.remove("open");
      burger.setAttribute("aria-expanded", "false");
    });
  });
  // закрыть при клике вне меню
  document.addEventListener("click", (e) => {
    if (!burger.contains(e.target) && !navMobile.contains(e.target)) {
      navMobile.classList.remove("open");
      burger.classList.remove("open");
      burger.setAttribute("aria-expanded", "false");
    }
  });
}

// ── 1. Info-tabs (кнопки-секции) ──────────────────────────
document.querySelectorAll("[data-info-toggle]").forEach((btn) => {
  btn.addEventListener("click", () => {
    btn.closest(".info-tab").classList.toggle("open");
  });
});

// ── helpers ────────────────────────────────────────────────
async function api(path, { method = "GET", body = null } = {}) {
  const opts = { method, headers: {} };
  if (body !== null) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  let data = null;
  try { data = await res.json(); } catch (e) { /* no body */ }
  return { ok: res.ok, status: res.status, data };
}

function escapeHtml(s) {
  return String(s == null ? "" : s)
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

function detailToText(detail) {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map(d => d.msg || "").join("; ");
  return "Ошибка";
}

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("ru-RU") + " " +
         d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}
function formatDay(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("ru-RU");
}

function statusBadge(s) {
  const map = { done: "готово", error: "ошибка", processing: "обработка", pending: "в очереди" };
  return `<span class="badge badge-${s}">${map[s] || s}</span>`;
}

// ── 1. Auth forms ──────────────────────────────────────────
document.querySelectorAll("[data-auth-form]").forEach((form) => {
  const kind = form.getAttribute("data-auth-form"); // login | register
  const errBox = form.querySelector("[data-auth-error]");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errBox.classList.add("hidden");
    const email = form.email.value.trim();
    const password = form.password.value;
    const { ok, data } = await api(`/api/auth/${kind}`, { method: "POST", body: { email, password } });
    if (ok) {
      window.location = data.is_admin ? "/admin" : "/dashboard";
    } else {
      errBox.textContent = detailToText(data && data.detail) || "Не удалось выполнить";
      errBox.classList.remove("hidden");
    }
  });
});

// ── 2. Process widget (index + dashboard) ──────────────────
document.querySelectorAll("[data-process]").forEach((root) => {
  const input = root.querySelector("[data-process-url]");
  const btn = root.querySelector("[data-process-btn]");
  const result = root.querySelector("[data-process-result]");
  let timer = null;

  const show = (cls, html) => { result.className = "result"; result.innerHTML = `<div class="alert ${cls}">${html}</div>`; };
  const showInfo = (t) => show("alert-info", escapeHtml(t));
  const showError = (t) => show("alert-error", escapeHtml(t));

  async function start() {
    const url = input.value.trim();
    if (!url) return;
    btn.disabled = true;
    showInfo("Создаём задачу…");
    const { ok, status, data } = await api("/api/jobs", { method: "POST", body: { url } });
    if (status === 401) { window.location = "/login"; return; }
    if (!ok) { showError(detailToText(data && data.detail) || "Ошибка"); btn.disabled = false; return; }
    poll(data.id);
  }

  function poll(id) {
    showInfo("Обрабатываем… фотографии скачиваются и очищаются.");
    clearInterval(timer);
    timer = setInterval(async () => {
      const { ok, data } = await api(`/api/jobs/${id}`);
      if (!ok) return;
      if (data.status === "done") {
        clearInterval(timer); btn.disabled = false;
        result.className = "result";
        result.innerHTML =
          `<div class="alert alert-ok">Готово! Обработано фотографий: ${data.photo_count}.` +
          (data.title ? ` Объявление: ${escapeHtml(data.title)}` : "") + `</div>` +
          `<a class="btn" href="/api/jobs/${data.id}/download">Скачать архив (.zip)</a>`;
        if (window.__reloadJobs) window.__reloadJobs();
        if (window.__reloadMe) window.__reloadMe();
      } else if (data.status === "error") {
        clearInterval(timer); btn.disabled = false;
        showError(data.error || "Не удалось обработать объявление");
      }
    }, 1500);
  }

  btn.addEventListener("click", start);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") start(); });
});

// ── 3. Dashboard: профиль + история ────────────────────────
(() => {
  const meTariff = document.querySelector("[data-me-tariff]");
  if (meTariff) {
    window.__reloadMe = async () => {
      const { ok, data } = await api("/api/me");
      if (!ok) return;
      meTariff.textContent = data.tariff ? `Тариф: ${data.tariff}` : "Тариф не назначен";
      document.querySelector("[data-me-remaining]").textContent =
        data.remaining === null ? "∞" : `Осталось: ${data.remaining}`;
      const acc = document.querySelector("[data-me-access]");
      acc.textContent = data.access_active
        ? `доступ активен до ${formatDay(data.access_until)}`
        : "доступ не активен";
    };
    window.__reloadMe();
  }

  const jobsBody = document.querySelector("[data-jobs-body]");
  if (jobsBody) {
    window.__reloadJobs = async () => {
      const { ok, data } = await api("/api/jobs");
      if (!ok) { jobsBody.innerHTML = `<tr><td colspan="5" class="muted">Ошибка загрузки</td></tr>`; return; }
      if (!data.length) { jobsBody.innerHTML = `<tr><td colspan="5" class="muted">Пока нет обработок</td></tr>`; return; }
      jobsBody.innerHTML = data.map((j) => `
        <tr>
          <td>${j.id}</td>
          <td>${escapeHtml((j.title || j.url).slice(0, 50))}</td>
          <td>${j.photo_count || ""}</td>
          <td>${statusBadge(j.status)}</td>
          <td>${j.status === "done"
                ? `<a class="btn btn-sm" href="/api/jobs/${j.id}/download">Скачать</a>`
                : (j.status === "error"
                    ? `<span class="muted" title="${escapeHtml(j.error)}">ошибка</span>`
                    : "…")}</td>
        </tr>`).join("");
    };
    window.__reloadJobs();
  }
})();

// ── 4. Tariffs page + калькулятор ──────────────────────────
(() => {
  const wrap = document.querySelector("[data-tariffs]");
  if (!wrap) return;
  api("/api/tariffs").then(({ ok, data }) => {
    if (!ok || !data.length) { wrap.innerHTML = '<p class="muted">Тарифы пока не настроены.</p>'; return; }
    wrap.innerHTML = data.map((t, i) => `
      <div class="tariff ${i === 1 ? "featured" : ""}">
        <h3>${escapeHtml(t.name)}</h3>
        <div class="price">${t.price} ₽ <span>/ ${t.duration_days} дн.</span></div>
        <p>${escapeHtml(t.description || "")}</p>
        <div class="muted">${t.limit_count === 0 ? "без лимита" : t.limit_count + " обработок"}</div>
      </div>`).join("");

    const sel = document.querySelector("[data-calc-tariff]");
    const res = document.querySelector("[data-calc-result]");
    if (sel && res) {
      sel.innerHTML = data.map((t) => `<option value="${t.id}">${escapeHtml(t.name)}</option>`).join("");
      const update = () => {
        const t = data.find((x) => x.id == sel.value);
        if (!t) return;
        res.textContent = t.limit_count
          ? `${t.price} ₽ за ${t.limit_count} обработок (~${(t.price / t.limit_count).toFixed(1)} ₽ за объявление)`
          : `${t.price} ₽ — без лимита на ${t.duration_days} дн.`;
      };
      sel.addEventListener("change", update);
      update();
    }
  });
})();

// ── 5. Admin ───────────────────────────────────────────────
(() => {
  const usersList = document.querySelector("[data-users-list]");
  const tariffsList = document.querySelector("[data-tariffs-list]");
  if (!usersList && !tariffsList) return;

  // tabs
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const name = tab.getAttribute("data-tab");
      document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
      document.querySelectorAll("[data-tabpanel]").forEach((p) =>
        p.classList.toggle("hidden", p.getAttribute("data-tabpanel") !== name));
    });
  });

  let tariffsCache = [];
  const refreshTariffsCache = async () => {
    const { ok, data } = await api("/api/admin/tariffs");
    if (ok) tariffsCache = data;
  };

  // ── Users (карточки) ──
  if (usersList) {
    const searchInput = document.querySelector("[data-user-search]");
    const searchBtn = document.querySelector("[data-user-search-btn]");
    const detail = document.querySelector("[data-user-detail]");

    const loadUsers = async (q = "") => {
      const { ok, data } = await api("/api/admin/users?q=" + encodeURIComponent(q));
      if (!ok) return;
      if (!data.length) { usersList.innerHTML = '<p class="muted">Никого не найдено</p>'; return; }
      usersList.innerHTML = data.map((u) => `
        <div class="user-card" data-uid="${u.id}">
          <div class="user-card-info">
            <div class="email">${escapeHtml(u.email)}${u.is_admin ? ' <span class="badge badge-processing">admin</span>' : ""}</div>
            <div class="meta">${u.tariff ? escapeHtml(u.tariff) : "нет тарифа"} · ${u.is_active
              ? (u.access_active ? '<span style="color:var(--ok)">активен</span>' : '<span>нет доступа</span>')
              : '<span style="color:var(--danger)">заблок.</span>'}</div>
          </div>
          <div class="user-card-right">
            <div class="remaining">${u.remaining === null ? "∞" : u.remaining}</div>
            <div class="muted" style="font-size:11px">осталось</div>
          </div>
        </div>`).join("");
      usersList.querySelectorAll("[data-uid]").forEach((card) =>
        card.addEventListener("click", () => {
          usersList.querySelectorAll(".user-card").forEach((c) => c.classList.remove("selected"));
          card.classList.add("selected");
          openUser(card.getAttribute("data-uid"));
        }));
    };

    const openUser = async (id) => {
      const { ok, data } = await api("/api/admin/users/" + id);
      if (!ok) return;
      renderUser(detail, data, loadUsers, tariffsCache);
      // на мобиле скролл к деталям
      if (window.innerWidth <= 768) detail.scrollIntoView({ behavior: "smooth", block: "start" });
    };

    searchBtn.addEventListener("click", () => loadUsers(searchInput.value));
    searchInput.addEventListener("keydown", (e) => { if (e.key === "Enter") loadUsers(searchInput.value); });
    refreshTariffsCache().then(loadUsers);
  }

  // ── Tariffs CRUD (карточки) ──
  if (tariffsList) {
    const f = {
      id: document.querySelector("[data-tariff-id]"),
      name: document.querySelector("[data-tariff-name]"),
      price: document.querySelector("[data-tariff-price]"),
      limit: document.querySelector("[data-tariff-limit]"),
      days: document.querySelector("[data-tariff-days]"),
      desc: document.querySelector("[data-tariff-desc]"),
      active: document.querySelector("[data-tariff-active]"),
      sort: document.querySelector("[data-tariff-sort]"),
      msg: document.querySelector("[data-tariff-msg]"),
      delBtn: document.querySelector("[data-tariff-delete]"),
    };

    const loadTariffs = async () => {
      const { ok, data } = await api("/api/admin/tariffs");
      if (!ok) return;
      tariffsCache = data;
      tariffsList.innerHTML = data.length
        ? data.map((t) => `
          <div class="tariff-card" data-edit="${t.id}">
            <div>
              <div class="name">${escapeHtml(t.name)}${t.is_active ? "" : ' <span class="badge badge-off">выкл</span>'}</div>
              <div class="details">${t.limit_count === 0 ? "безлимит" : t.limit_count + " обработок"} · ${t.duration_days} дн.</div>
            </div>
            <div style="font-weight:700;font-size:16px;color:var(--accent)">${t.price} ₽</div>
          </div>`).join("")
        : '<p class="muted">Тарифов пока нет</p>';
      tariffsList.querySelectorAll("[data-edit]").forEach((card) =>
        card.addEventListener("click", () => fillForm(data.find((x) => x.id == card.getAttribute("data-edit")))));
    };

    const clearForm = () => {
      f.id.value = ""; f.name.value = ""; f.price.value = 0; f.limit.value = 0;
      f.days.value = 30; f.desc.value = ""; f.active.checked = true; f.sort.value = 0;
      f.delBtn.classList.add("hidden");
    };
    const fillForm = (t) => {
      if (!t) return;
      f.id.value = t.id; f.name.value = t.name; f.price.value = t.price;
      f.limit.value = t.limit_count; f.days.value = t.duration_days;
      f.desc.value = t.description || ""; f.active.checked = t.is_active; f.sort.value = t.sort_order;
      f.delBtn.classList.remove("hidden");
    };
    const flash = (text, isErr) => {
      f.msg.textContent = text;
      f.msg.className = "alert " + (isErr ? "alert-error" : "alert-ok");
      setTimeout(() => f.msg.classList.add("hidden"), 2500);
    };

    document.querySelector("[data-tariff-save]").addEventListener("click", async () => {
      const body = {
        name: f.name.value.trim(),
        price: parseInt(f.price.value || "0", 10),
        limit_count: parseInt(f.limit.value || "0", 10),
        duration_days: parseInt(f.days.value || "30", 10),
        description: f.desc.value.trim(),
        is_active: f.active.checked,
        sort_order: parseInt(f.sort.value || "0", 10),
      };
      if (!body.name) { flash("Укажите название", true); return; }
      const id = f.id.value;
      const { ok, data } = id
        ? await api("/api/admin/tariffs/" + id, { method: "PUT", body })
        : await api("/api/admin/tariffs", { method: "POST", body });
      if (ok) { flash("Сохранено"); clearForm(); loadTariffs(); }
      else flash(detailToText(data && data.detail) || "Ошибка", true);
    });

    document.querySelector("[data-tariff-new]").addEventListener("click", clearForm);
    f.delBtn.addEventListener("click", async () => {
      const id = f.id.value;
      if (!id || !confirm("Удалить тариф?")) return;
      const { ok } = await api("/api/admin/tariffs/" + id, { method: "DELETE" });
      if (ok) { clearForm(); loadTariffs(); }
    });

    loadTariffs();
  }
})();

// renders the user detail panel (admin)
function renderUser(detail, u, reloadUsers, tariffs) {
  const tariffOptions =
    '<option value="">— выбрать тариф —</option><option value="0">снять тариф</option>' +
    tariffs.map((t) => `<option value="${t.id}">${escapeHtml(t.name)} (${t.price}₽)</option>`).join("");

  detail.innerHTML = `
    <div class="row" style="justify-content:space-between">
      <div>
        <div style="font-weight:600">${escapeHtml(u.email)}</div>
        <div class="muted">рег. ${formatDay(u.created_at)}</div>
      </div>
      <div>${u.is_active ? '<span class="badge badge-done">активен</span>' : '<span class="badge badge-error">заблокирован</span>'}</div>
    </div>
    <hr style="border:none;border-top:1px solid var(--line);margin:14px 0">
    <div class="stack">
      <div>Тариф: <b>${u.tariff ? escapeHtml(u.tariff) : "не назначен"}</b></div>
      <div>Лимит: <b>${u.limit_count === 0 ? "безлимит" : u.limit_count}</b> · использовано: <b>${u.used_count}</b> · осталось: <b>${u.remaining === null ? "∞" : u.remaining}</b></div>
      <div>Доступ: ${u.access_active ? "до " + formatDay(u.access_until) : '<span class="muted">не активен</span>'}</div>
    </div>

    <hr style="border:none;border-top:1px solid var(--line);margin:14px 0">
    <div class="stack">
      <div class="field" style="margin:0"><label>Назначить тариф</label>
        <select data-assign-tariff>${tariffOptions}</select>
      </div>
      <button class="btn btn-sm" data-do-assign>Назначить</button>

      <div class="row" style="margin-top:6px">
        <div class="field" style="flex:1;margin:0"><label>Лимит (0=∞)</label><input type="number" data-set-limit value="${u.limit_count}"></div>
        <div class="field" style="flex:1;margin:0"><label>+ дней доступа</label><input type="number" data-add-days value="0"></div>
        <label style="align-self:end;padding-bottom:10px"><input type="checkbox" data-reset-used> обнулить</label>
      </div>
      <button class="btn btn-ghost btn-sm" data-do-manual>Применить вручную</button>
      <button class="btn ${u.is_active ? "btn-danger" : ""} btn-sm" data-do-toggle>${u.is_active ? "Заблокировать" : "Разблокировать"}</button>
    </div>

    <hr style="border:none;border-top:1px solid var(--line);margin:14px 0">
    <div><b>Комментарии</b></div>
    <div class="stack" style="margin-top:8px" data-comments>
      ${u.comments.length ? u.comments.map((c) => `
        <div class="comment">
          <div class="meta">${formatDate(c.created_at)} · ${escapeHtml(c.author)}
            <a href="#" data-del-comment="${c.id}" style="float:right;color:var(--danger)">удалить</a></div>
          ${escapeHtml(c.text)}
        </div>`).join("") : '<div class="muted">Нет комментариев</div>'}
    </div>
    <div class="row" style="margin-top:8px">
      <input type="text" data-comment-text placeholder="Новый комментарий" style="flex:1;padding:9px 12px;border:1px solid var(--line);border-radius:8px">
      <button class="btn btn-sm" data-add-comment>Добавить</button>
    </div>

    <hr style="border:none;border-top:1px solid var(--line);margin:14px 0">
    <div><b>Последние обработки</b></div>
    <div class="stack" style="margin-top:8px">
      ${u.jobs.length ? u.jobs.slice(0, 8).map((j) => `
        <div class="row" style="justify-content:space-between">
          <span>${escapeHtml((j.title || j.url).slice(0, 40))}</span>
          ${statusBadge(j.status)}
        </div>`).join("") : '<div class="muted">Нет обработок</div>'}
    </div>
  `;

  const reopen = async () => {
    const { ok, data } = await api("/api/admin/users/" + u.id);
    if (ok) renderUser(detail, data, reloadUsers, tariffs);
    reloadUsers();
  };

  detail.querySelector("[data-do-assign]").addEventListener("click", async () => {
    const v = detail.querySelector("[data-assign-tariff]").value;
    if (v === "") return;
    await api(`/api/admin/users/${u.id}/tariff`, { method: "POST", body: { tariff_id: parseInt(v, 10) } });
    reopen();
  });

  detail.querySelector("[data-do-manual]").addEventListener("click", async () => {
    const body = {
      limit_count: parseInt(detail.querySelector("[data-set-limit]").value || "0", 10),
      extra_days: parseInt(detail.querySelector("[data-add-days]").value || "0", 10) || null,
      reset_used: detail.querySelector("[data-reset-used]").checked,
    };
    await api(`/api/admin/users/${u.id}/tariff`, { method: "POST", body });
    reopen();
  });

  detail.querySelector("[data-do-toggle]").addEventListener("click", async () => {
    await api(`/api/admin/users/${u.id}/toggle`, { method: "POST" });
    reopen();
  });

  detail.querySelector("[data-add-comment]").addEventListener("click", async () => {
    const text = detail.querySelector("[data-comment-text]").value.trim();
    if (!text) return;
    await api(`/api/admin/users/${u.id}/comment`, { method: "POST", body: { text } });
    reopen();
  });

  detail.querySelectorAll("[data-del-comment]").forEach((a) =>
    a.addEventListener("click", async (e) => {
      e.preventDefault();
      await api(`/api/admin/users/${u.id}/comment/${a.getAttribute("data-del-comment")}`, { method: "DELETE" });
      reopen();
    }));
}
