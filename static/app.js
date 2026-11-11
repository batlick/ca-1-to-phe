/**
 * app.js
 * Customer ordering & Real-time SSE Live Order Tracker for "Cả 1 tổ phê" (Cà phê Tổ 1).
 */

let menuItems = [];
let cart = [];
let currentModalDrink = null;
let selectedSweetness = "Chuẩn vị Tổ 1";
let selectedIce = "Đá chung bình thường";
let modalQty = 1;
let activeOrderId = null;
let lastOrderStatus = null;
let lastMenuSignature = "";

function formatVND(amount) {
  return Number(amount || 0).toLocaleString("vi-VN") + "đ";
}

function getQueryTable() {
  const params = new URLSearchParams(window.location.search);
  return (params.get("table") || "").trim();
}

async function initCustomerApp() {
  const presetTable = getQueryTable();
  if (presetTable) {
    const pill = document.getElementById("table-pill");
    if (pill) pill.textContent = `📍 ${presetTable}`;
    const tableInput = document.getElementById("table-name-input");
    if (tableInput) tableInput.value = presetTable;
  }

  await fetchMenu();
  await restoreActiveOrder();
  connectSSE();
  startCustomerLiveSync();
}

async function fetchMenu() {
  try {
    const res = await fetch(`/api/menu?_t=${Date.now()}`, { cache: "no-store" });
    const data = await res.json();
    const items = data.items || [];
    const sig = JSON.stringify(items);
    if (sig !== lastMenuSignature) {
      lastMenuSignature = sig;
      menuItems = items;
      renderMenu();
    }
  } catch (err) {
    console.error("Failed to load menu:", err);
  }
}

function renderMenu() {
  const grid = document.getElementById("menu-grid");
  if (!grid) return;

  grid.innerHTML = menuItems
    .map((item) => {
      const available = Boolean(item.is_available);
      return `
      <article class="menu-card ${available ? "" : "sold-out"}">
        <div class="menu-img-wrap">
          <img src="${item.image_url}" alt="${item.name}" class="menu-img" />
          ${item.badge ? `<span class="menu-badge-top">🔥 ${item.badge}</span>` : ""}
          <span class="menu-volume-badge">LY ${item.volume}</span>
        </div>
        <div class="menu-body">
          <div>
            <span class="poster-blue-tag">${item.tagline}</span>
          </div>
          <h3 class="menu-name">${item.name}</h3>
          <p class="menu-desc">${item.description}</p>
          <div class="menu-footer">
            <span class="menu-price">${formatVND(item.price)}</span>
            <button
              class="btn-add-drink"
              ${available ? "" : "disabled"}
              onclick="openCustomizeModal(${item.id})"
            >
              ${available ? "＋ Chọn món" : "Tạm hết"}
            </button>
          </div>
        </div>
      </article>
    `;
    })
    .join("");
}

function openCustomizeModal(itemId) {
  const item = menuItems.find((m) => m.id === itemId);
  if (!item || !item.is_available) return;

  currentModalDrink = item;
  selectedSweetness = "Chuẩn vị Tổ 1";
  selectedIce = "Đá chung bình thường";
  modalQty = 1;

  document.getElementById("modal-drink-tagline").textContent = item.tagline;
  document.getElementById("modal-drink-name").textContent = item.name;
  document.getElementById("modal-drink-price").textContent = `${formatVND(item.price)} • Ly ${item.volume}`;
  document.getElementById("modal-item-note").value = "";
  document.getElementById("modal-qty-val").textContent = "1";

  document.querySelectorAll("#sweetness-options .choice-chip").forEach((el, idx) => {
    el.classList.toggle("selected", idx === 0);
  });
  document.querySelectorAll("#ice-options .choice-chip").forEach((el, idx) => {
    el.classList.toggle("selected", idx === 0);
  });

  updateModalConfirmBtn();
  document.getElementById("customize-modal").classList.remove("hidden");
}

function closeCustomizeModal() {
  document.getElementById("customize-modal").classList.add("hidden");
}

function selectSweetness(el) {
  document.querySelectorAll("#sweetness-options .choice-chip").forEach((c) => c.classList.remove("selected"));
  el.classList.add("selected");
  selectedSweetness = el.getAttribute("data-val");
}

function selectIce(el) {
  document.querySelectorAll("#ice-options .choice-chip").forEach((c) => c.classList.remove("selected"));
  el.classList.add("selected");
  selectedIce = el.getAttribute("data-val");
}

function changeModalQty(delta) {
  modalQty = Math.max(1, Math.min(20, modalQty + delta));
  document.getElementById("modal-qty-val").textContent = String(modalQty);
  updateModalConfirmBtn();
}

function updateModalConfirmBtn() {
  if (!currentModalDrink) return;
  const subtotal = currentModalDrink.price * modalQty;
  document.getElementById("modal-confirm-btn").textContent =
    `Thêm ${modalQty} ly vào đơn • ${formatVND(subtotal)}`;
}

function confirmAddToCart() {
  if (!currentModalDrink) return;
  const note = document.getElementById("modal-item-note").value.trim();

  // Merge if identical drink + customization
  const existing = cart.find(
    (c) =>
      c.menu_item_id === currentModalDrink.id &&
      c.sweetness === selectedSweetness &&
      c.ice_level === selectedIce &&
      c.item_note === note
  );

  if (existing) {
    existing.quantity += modalQty;
  } else {
    cart.push({
      menu_item_id: currentModalDrink.id,
      name: currentModalDrink.name,
      price: currentModalDrink.price,
      image_url: currentModalDrink.image_url,
      quantity: modalQty,
      sweetness: selectedSweetness,
      ice_level: selectedIce,
      item_note: note,
    });
  }

  closeCustomizeModal();
  updateCartUI();
}

function updateCartUI() {
  const bar = document.getElementById("floating-cart");
  const totalCups = cart.reduce((acc, i) => acc + i.quantity, 0);
  const totalAmount = cart.reduce((acc, i) => acc + i.price * i.quantity, 0);

  if (totalCups === 0) {
    bar.classList.add("hidden");
  } else {
    bar.classList.remove("hidden");
    document.getElementById("cart-count").textContent = String(totalCups);
    document.getElementById("cart-total-text").textContent = formatVND(totalAmount);
  }
}

function openCheckoutModal() {
  if (cart.length === 0) return;
  renderCheckoutItems();
  document.getElementById("checkout-error-msg").style.display = "none";
  document.getElementById("checkout-modal").classList.remove("hidden");
}

function closeCheckoutModal() {
  document.getElementById("checkout-modal").classList.add("hidden");
}

function renderCheckoutItems() {
  const listEl = document.getElementById("checkout-items-list");
  if (cart.length === 0) {
    closeCheckoutModal();
    updateCartUI();
    return;
  }

  const totalAmount = cart.reduce((acc, i) => acc + i.price * i.quantity, 0);
  document.getElementById("checkout-total-amount").textContent = formatVND(totalAmount);

  listEl.innerHTML = cart
    .map(
      (item, idx) => `
      <div style="display:flex; align-items:center; justify-content:space-between; gap:10px; background:#FFFFFF; border:2px solid var(--border-dark); border-radius:12px; padding:10px 12px;">
        <div style="flex:1;">
          <div style="font-weight:800; font-size:0.95rem;">${item.name} <span style="color:var(--brand-red);">(${formatVND(item.price)})</span></div>
          <div style="font-size:0.78rem; color:var(--espresso-muted); font-weight:600;">
            ${item.sweetness} • ${item.ice_level}
            ${item.item_note ? ` • Ghi chú: "${item.item_note}"` : ""}
          </div>
        </div>
        <div style="display:flex; align-items:center; gap:6px;">
          <button class="qty-btn" style="width:26px;height:26px;font-size:0.9rem;" onclick="adjustCartItem(${idx}, -1)">−</button>
          <span style="font-weight:800; min-width:20px; text-align:center;">${item.quantity}</span>
          <button class="qty-btn" style="width:26px;height:26px;font-size:0.9rem;" onclick="adjustCartItem(${idx}, 1)">+</button>
        </div>
      </div>
    `
    )
    .join("");
}

function adjustCartItem(index, delta) {
  if (!cart[index]) return;
  cart[index].quantity += delta;
  if (cart[index].quantity <= 0) {
    cart.splice(index, 1);
  }
  updateCartUI();
  renderCheckoutItems();
}

async function submitOrder() {
  const customerName = document.getElementById("customer-name-input").value.trim();
  const tableName = document.getElementById("table-name-input").value.trim();
  const note = document.getElementById("order-note-input").value.trim();
  const errEl = document.getElementById("checkout-error-msg");

  if (!customerName && !tableName) {
    errEl.textContent = "⚠️ Bạn vui lòng nhập Tên gọi hoặc Số bàn để quầy gọi tên nhé!";
    errEl.style.display = "block";
    document.getElementById("customer-name-input").focus();
    return;
  }

  const btn = document.getElementById("submit-order-btn");
  btn.disabled = true;
  btn.textContent = "⏳ Đang gửi đơn về quầy...";

  try {
    const res = await fetch("/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        customer_name: customerName || "Khách Tổ 1",
        table_name: tableName,
        note: note,
        items: cart,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || "Không thể tạo đơn hàng");
    }

    cart = [];
    updateCartUI();
    closeCheckoutModal();

    activeOrderId = data.order.id;
    localStorage.setItem("cafego_active_order_id", String(activeOrderId));
    renderLiveTracker(data.order);
    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (err) {
    errEl.textContent = `⚠️ ${err.message}`;
    errEl.style.display = "block";
  } finally {
    btn.disabled = false;
    btn.textContent = "🚀 GỬI ORDER VỀ QUẦY PHA CHẾ";
  }
}

async function restoreActiveOrder() {
  const savedId = localStorage.getItem("cafego_active_order_id");
  if (!savedId) return;
  activeOrderId = Number(savedId);
  await pollActiveOrderOnce();
}

async function pollActiveOrderOnce() {
  if (!activeOrderId) return;
  try {
    const res = await fetch(`/api/orders/${activeOrderId}?_t=${Date.now()}`, {
      cache: "no-store",
    });
    if (!res.ok) {
      if (res.status === 404) {
        localStorage.removeItem("cafego_active_order_id");
        activeOrderId = null;
        const section = document.getElementById("live-tracker-section");
        if (section) section.style.display = "none";
      }
      return;
    }
    const data = await res.json();
    if (data.order) {
      renderLiveTracker(data.order);
    }
  } catch (e) {
    console.error(e);
  }
}

function startCustomerLiveSync() {
  // Poll active order status every 2 seconds so even over Cloudflare HTTP/3 tunnels
  // the customer screen updates immediately without any page reload.
  setInterval(() => {
    if (activeOrderId) {
      pollActiveOrderOnce();
    }
  }, 2000);

  // Sync menu availability and price changes every 4 seconds
  setInterval(() => {
    fetchMenu();
  }, 4000);
}

function renderLiveTracker(order) {
  const section = document.getElementById("live-tracker-section");
  const card = document.getElementById("live-tracker-card");
  if (!section || !card) return;

  section.style.display = "block";
  document.getElementById("tracker-order-code").textContent = order.order_code;
  document.getElementById("tracker-customer-title").textContent =
    `${order.customer_name}${order.table_name ? ` • ${order.table_name}` : ""}`;

  const stepsRow = document.getElementById("tracker-steps-row");
  const sPending = document.getElementById("step-pending");
  const sPrep = document.getElementById("step-preparing");
  const sReady = document.getElementById("step-ready");
  const msgEl = document.getElementById("tracker-status-msg");

  sPending.className = "t-step";
  sPrep.className = "t-step";
  sReady.className = "t-step";
  card.classList.remove("status-ready", "status-cancelled");
  if (stepsRow) stepsRow.style.display = "grid";

  if (order.status === "cancelled") {
    card.classList.add("status-cancelled");
    if (stepsRow) stepsRow.style.display = "none";
    msgEl.innerHTML =
      `<div style="background:#FEE2E2; border:2px solid var(--brand-red); color:#991B1B; padding:12px 14px; border-radius:12px; font-size:1rem; font-weight:800;">` +
      `⚠️ Xin lỗi, món đó đã hết - vui lòng chọn lại món khác` +
      `</div>`;
  } else if (order.status === "pending") {
    sPending.className = "t-step active";
    msgEl.innerHTML = "⏳ Đơn hàng đã gửi tới quầy! Barista sẽ xác nhận ngay trong giây lát.";
  } else if (order.status === "preparing") {
    sPending.className = "t-step done";
    sPrep.className = "t-step active";
    msgEl.innerHTML = "☕ <strong>Barista Tổ 1 đang pha chế</strong> những ly 700ml mát lạnh cho bạn!";
  } else if (order.status === "ready" || order.status === "completed") {
    sPending.className = "t-step done";
    sPrep.className = "t-step done";
    sReady.className = "t-step active";
    card.classList.add("status-ready");
    msgEl.innerHTML =
      "🎉 <strong>ĐỒ UỐNG ĐÃ XONG!</strong> Mời bạn ghé quầy đọc mã <strong>" +
      order.order_code +
      "</strong> để nhận nước và thanh toán (" +
      formatVND(order.total_amount) +
      ") nhé!";
  }

  const summaryHtml = (order.items || [])
    .map(
      (i) =>
        `<div>• <strong>${i.quantity}x ${i.item_name}</strong> (${i.sweetness}, ${i.ice_level}) — ${formatVND(i.subtotal)}</div>`
    )
    .join("");
  document.getElementById("tracker-items-summary").innerHTML =
    summaryHtml +
    `<div style="margin-top:6px; padding-top:6px; border-top:1px solid #E2D9C5; font-weight:800; color:var(--brand-red);">Tổng thanh toán tại quầy: ${formatVND(order.total_amount)}</div>`;
}

function connectSSE() {
  try {
    const evtSource = new EventSource("/api/stream");

    evtSource.addEventListener("menu_updated", () => {
      fetchMenu();
    });

    evtSource.addEventListener("order_updated", (e) => {
      try {
        const payload = JSON.parse(e.data);
        if (payload.order && Number(payload.order.id) === Number(activeOrderId)) {
          renderLiveTracker(payload.order);
        }
      } catch (err) {
        console.error(err);
      }
    });

    evtSource.addEventListener("orders_reset", () => {
      pollActiveOrderOnce();
    });
  } catch (e) {
    console.warn("SSE fallback to polling:", e);
  }
}

document.addEventListener("DOMContentLoaded", initCustomerApp);
