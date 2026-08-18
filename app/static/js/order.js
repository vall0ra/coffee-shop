/* Staff "New Order" wizard — vanilla JS, drives step rendering + basket state. */

const STEP_LABELS = ["Location", "Table", "Allergies", "Member", "Items", "Payment", "Pay", "Review"];

const state = {
  step: 0,
  location: null,
  table: null,
  allergyStatus: false,
  allergens: [],
  member: null,
  basket: [],
  paymentMethod: null,
  amountReceived: "",
  paymentConfirmed: false,
  builder: null, // { mode: 'drink'|'sandwich', ... temp selections }
};

let MENU = null;
let itemKeyCounter = 1;

const stepContainer = document.getElementById("step-container");
const basketContainer = document.getElementById("basket-container");
const progressContainer = document.getElementById("wizard-progress");

function money(n) {
  return "£" + (Math.round(n * 100) / 100).toFixed(2);
}

function el(html) {
  const div = document.createElement("div");
  div.innerHTML = html.trim();
  return div.firstElementChild;
}

function goToStep(n) {
  state.step = n;
  render();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

fetch(window.MENU_API_URL)
  .then((r) => r.json())
  .then((data) => {
    MENU = data;
    render();
  });

function render() {
  renderProgress();
  renderBasket();
  switch (state.step) {
    case 0: return renderLocationStep();
    case 1: return renderTableStep();
    case 2: return renderAllergyStep();
    case 3: return renderMemberStep();
    case 4: return renderItemsStep();
    case 5: return renderPaymentMethodStep();
    case 6: return renderPaymentDetailStep();
    case 7: return renderSummaryStep();
    case 8: return renderConfirmationStep();
  }
}

function renderProgress() {
  progressContainer.innerHTML = "";
  const total = Math.min(state.step, 7);
  for (let i = 0; i < STEP_LABELS.length; i++) {
    const dot = document.createElement("div");
    dot.className = "step-dot" + (i < state.step ? " done" : i === state.step ? " current" : "");
    progressContainer.appendChild(dot);
  }
}

// ---------------------------------------------------------------------------
// Basket (persists across steps)
// ---------------------------------------------------------------------------

function basketTotal() {
  return state.basket.reduce((sum, item) => sum + item.total, 0);
}

function renderBasket() {
  const total = basketTotal();
  let itemsHtml = "";
  if (state.basket.length === 0) {
    itemsHtml = `<div class="basket-empty">No items added yet</div>`;
  } else {
    itemsHtml = state.basket
      .map(
        (item) => `
      <div class="basket-item">
        <div class="row">
          <div>
            <div class="name">${item.name}${item.quantity > 1 ? " × " + item.quantity : ""}</div>
            ${item.options.length ? `<div class="opts">${item.options.map((o) => o.name).join(", ")}</div>` : ""}
          </div>
          <div class="price">${money(item.total)}</div>
        </div>
        <button class="remove" onclick="removeItem('${item.key}')">Remove</button>
      </div>`
      )
      .join("");
  }

  basketContainer.innerHTML = `
    <h3>Your Order So Far</h3>
    ${state.location ? `<div class="meta-line">📍 ${state.location.name}${state.table ? " · Table " + state.table : ""}</div>` : ""}
    ${state.member ? `<div class="meta-line">👤 ${state.member.member_number} — ${state.member.name}</div>` : ""}
    ${state.allergyStatus ? `<div class="meta-line">⚠ ${state.allergens.join(", ") || "Allergies declared"}</div>` : ""}
    <div class="basket-items">${itemsHtml}</div>
    <div class="basket-total">
      <span>Total</span>
      <span class="amount">${money(total)}</span>
    </div>
  `;
}

function removeItem(key) {
  state.basket = state.basket.filter((i) => i.key !== key);
  render();
}

// ---------------------------------------------------------------------------
// Step 1 — Location
// ---------------------------------------------------------------------------

function renderLocationStep() {
  stepContainer.innerHTML = `
    <div class="step-label">Step 1 of 8</div>
    <h2>1. Location</h2>
    <p class="text-muted">Choose where the customer is seated.</p>
    <div class="pick-grid">
      ${MENU.locations
        .map(
          (loc) => `
        <div class="pick-card ${state.location && state.location.id === loc.id ? "selected" : ""}" onclick="selectLocation(${loc.id}, '${loc.name}')">
          ${loc.name}
        </div>`
        )
        .join("")}
    </div>
  `;
}

function selectLocation(id, name) {
  state.location = { id, name };
  goToStep(1);
}

// ---------------------------------------------------------------------------
// Step 2 — Table
// ---------------------------------------------------------------------------

function renderTableStep() {
  let cells = "";
  for (let t = 1; t <= 30; t++) {
    cells += `<div class="table-cell ${state.table === t ? "selected" : ""}" onclick="selectTable(${t})">${t}</div>`;
  }
  stepContainer.innerHTML = `
    <div class="step-label">Step 2 of 8</div>
    <h2>2. Table Number</h2>
    <p class="text-muted">${state.location.name}</p>
    <div class="table-grid">${cells}</div>
    <div class="btn-group">
      <button class="btn btn-outline" onclick="goToStep(0)">← Back</button>
    </div>
  `;
}

function selectTable(t) {
  state.table = t;
  goToStep(2);
}

// ---------------------------------------------------------------------------
// Step 3 — Allergies
// ---------------------------------------------------------------------------

function renderAllergyStep() {
  stepContainer.innerHTML = `
    <div class="step-label">Step 3 of 8</div>
    <h2>3. Any allergies?</h2>
    <div class="pick-grid" style="grid-template-columns: repeat(2, 1fr); max-width:340px;">
      <div class="pick-card ${state.allergyStatus === false ? "selected" : ""}" onclick="setAllergyStatus(false)">No</div>
      <div class="pick-card ${state.allergyStatus === true ? "selected" : ""}" onclick="setAllergyStatus(true)">Yes</div>
    </div>
    <div id="allergen-list"></div>
    <div class="btn-group" style="margin-top:20px;">
      <button class="btn btn-outline" onclick="goToStep(1)">← Back</button>
      <button class="btn btn-primary" onclick="goToStep(3)" ${state.allergyStatus === true && state.allergens.length === 0 ? "disabled" : ""}>Continue →</button>
    </div>
  `;
  renderAllergenList();
}

function setAllergyStatus(val) {
  state.allergyStatus = val;
  if (!val) state.allergens = [];
  renderAllergyStep();
}

function renderAllergenList() {
  const listDiv = document.getElementById("allergen-list");
  if (!listDiv) return;
  if (state.allergyStatus === null || state.allergyStatus === undefined) {
    listDiv.innerHTML = "";
    return;
  }
  if (state.allergyStatus === false) {
    listDiv.innerHTML = `<p style="margin-top:16px; font-weight:600;">No allergies declared</p>`;
    return;
  }
  listDiv.innerHTML = `
    <p class="text-muted" style="margin-top:16px;">Select all that apply:</p>
    <div class="allergen-grid">
      ${MENU.allergens
        .map(
          (a) => `
        <div class="allergen-chip ${state.allergens.includes(a) ? "selected" : ""}" onclick="toggleAllergen('${a}')">
          ${state.allergens.includes(a) ? "✓" : ""} ${a}
        </div>`
        )
        .join("")}
    </div>
  `;
}

function toggleAllergen(name) {
  if (state.allergens.includes(name)) {
    state.allergens = state.allergens.filter((a) => a !== name);
  } else {
    state.allergens.push(name);
  }
  renderAllergyStep();
}

// ---------------------------------------------------------------------------
// Step 4 — Member (optional)
// ---------------------------------------------------------------------------

function renderMemberStep() {
  stepContainer.innerHTML = `
    <div class="step-label">Step 4 of 8</div>
    <h2>4. Member (optional)</h2>
    <p class="text-muted">Search by member number or name, or skip if this is not a member.</p>
    <div class="field" style="max-width:340px;">
      <input type="text" id="member-search" placeholder="e.g. #1001 or name" oninput="searchMembers(this.value)">
    </div>
    <div id="member-results"></div>
    ${state.member ? `<div class="chip-inline">Selected: ${state.member.member_number} — ${state.member.name} <button onclick="clearMember()" style="border:none;background:none;color:var(--red);font-weight:700;">✕</button></div>` : ""}
    <div class="btn-group" style="margin-top:20px;">
      <button class="btn btn-outline" onclick="goToStep(2)">← Back</button>
      <button class="btn btn-outline" onclick="clearMember(); goToStep(4);">Skip</button>
      <button class="btn btn-primary" onclick="goToStep(4)">Continue →</button>
    </div>
  `;
}

let memberSearchTimer = null;
function searchMembers(q) {
  clearTimeout(memberSearchTimer);
  if (!q || q.length < 1) {
    document.getElementById("member-results").innerHTML = "";
    return;
  }
  memberSearchTimer = setTimeout(() => {
    fetch(window.MEMBERS_SEARCH_URL + "?q=" + encodeURIComponent(q))
      .then((r) => r.json())
      .then((data) => {
        const box = document.getElementById("member-results");
        if (!box) return;
        if (data.results.length === 0) {
          box.innerHTML = `<p class="text-muted" style="margin-top:8px;">No members found.</p>`;
          return;
        }
        box.innerHTML = data.results
          .map(
            (m) => `<div class="pick-card" style="text-align:left; padding:12px 16px; margin-bottom:8px;" onclick='selectMember(${JSON.stringify(m)})'>
              <strong>${m.member_number}</strong> — ${m.name}
            </div>`
          )
          .join("");
      });
  }, 250);
}

function selectMember(m) {
  state.member = m;
  renderMemberStep();
}

function clearMember() {
  state.member = null;
  renderMemberStep();
}

// ---------------------------------------------------------------------------
// Step 5 — Items (Add Drink / Add Sandwich)
// ---------------------------------------------------------------------------

function renderItemsStep() {
  if (state.builder && state.builder.mode === "drink-options") return renderDrinkOptionsBuilder();
  if (state.builder && state.builder.mode === "sandwich") return renderSandwichBuilder();

  const drinkCards = (cat, list) =>
    list
      .map(
        (d) => `
      <div class="pick-card" onclick="startDrinkOptions(${d.id}, '${d.name.replace(/'/g, "\\'")}', ${d.price})">
        ${d.name}<span class="price">${money(d.price)}</span>
      </div>`
      )
      .join("");

  stepContainer.innerHTML = `
    <div class="step-label">Step 5 of 8</div>
    <h2>5. Add a Drink</h2>
    <div class="pick-grid">
      ${drinkCards("hot", MENU.hot_drinks)}
      ${drinkCards("cold", MENU.drinks)}
    </div>
    <div class="btn-group" style="margin: 6px 0 20px 0;">
      <button class="btn btn-outline" onclick="startSandwich()">🥪 Order a Sandwich Instead</button>
    </div>
    <div class="btn-group">
      <button class="btn btn-outline" onclick="goToStep(3)">← Back</button>
      <button class="btn btn-primary" onclick="goToStep(5)" ${state.basket.length === 0 ? "disabled" : ""}>Continue to Payment →</button>
    </div>
  `;
}

function startDrinkOptions(id, name, price) {
  state.builder = { mode: "drink-options", id, name, price, selectedOptions: [] };
  renderItemsStep();
}

function renderDrinkOptionsBuilder() {
  const b = state.builder;
  const unitPrice = b.price + b.selectedOptions.reduce((s, o) => s + o.price, 0);
  stepContainer.innerHTML = `
    <div class="step-label">Step 5 of 8</div>
    <h2>${b.name}</h2>
    <p class="text-muted">Choose any options (optional).</p>
    <div class="option-grid">
      ${MENU.drink_options
        .map(
          (o) => `
        <div class="option-chip ${b.selectedOptions.find((s) => s.id === o.id) ? "selected" : ""}" onclick="toggleDrinkOption(${o.id}, '${o.name.replace(/'/g, "\\'")}', ${o.price})">
          <span>${o.name}</span>
          <span class="adj">${o.price >= 0 ? "+" : "-"}${money(Math.abs(o.price))}</span>
        </div>`
        )
        .join("")}
    </div>
    <div class="card" style="background:var(--beige); box-shadow:none;">
      <div class="flex-between"><strong>Price</strong><span class="mono" style="font-size:1.2rem;">${money(unitPrice)}</span></div>
    </div>
    <div class="btn-group" style="margin-top:20px;">
      <button class="btn btn-outline" onclick="cancelBuilder()">← Back</button>
      <button class="btn btn-accent" onclick="addDrinkToBasket()">Add to Order</button>
    </div>
  `;
}

function toggleDrinkOption(id, name, price) {
  const b = state.builder;
  const idx = b.selectedOptions.findIndex((o) => o.id === id);
  if (idx >= 0) b.selectedOptions.splice(idx, 1);
  else b.selectedOptions.push({ id, name, price });
  renderDrinkOptionsBuilder();
}

function addDrinkToBasket() {
  const b = state.builder;
  const unitPrice = b.price + b.selectedOptions.reduce((s, o) => s + o.price, 0);
  state.basket.push({
    key: "item-" + itemKeyCounter++,
    type: "drink",
    menu_item_id: b.id,
    name: b.name,
    options: b.selectedOptions.map((o) => ({ name: o.name, price: o.price })),
    option_ids: b.selectedOptions.map((o) => o.id),
    quantity: 1,
    total: unitPrice,
  });
  state.builder = null;
  renderItemsStep();
}

function startSandwich() {
  state.builder = { mode: "sandwich", filling: null, bread: null, extras: [] };
  renderItemsStep();
}

function renderSandwichBuilder() {
  const b = state.builder;
  const unitPrice =
    (b.filling ? b.filling.price : 0) + (b.bread ? b.bread.price : 0) + b.extras.reduce((s, e) => s + e.price, 0);

  stepContainer.innerHTML = `
    <div class="step-label">Step 5 of 8</div>
    <h2>Build a Sandwich</h2>

    <h3 style="font-size:1rem; margin-top:20px;">Filling</h3>
    <div class="pick-grid">
      ${MENU.fillings
        .map(
          (f) => `<div class="pick-card ${b.filling && b.filling.id === f.id ? "selected" : ""}" onclick='selectFilling(${JSON.stringify(f)})'>${f.name}<span class="price">${money(f.price)}</span></div>`
        )
        .join("")}
    </div>

    <h3 style="font-size:1rem; margin-top:20px;">Bread</h3>
    <div class="pick-grid">
      ${MENU.bread
        .map(
          (br) => `<div class="pick-card ${b.bread && b.bread.id === br.id ? "selected" : ""}" onclick='selectBread(${JSON.stringify(br)})'>${br.name}<span class="price">${money(br.price)}</span></div>`
        )
        .join("")}
    </div>

    <h3 style="font-size:1rem; margin-top:20px;">Extras</h3>
    <div class="option-grid">
      ${MENU.extras
        .map(
          (ex) => `
        <div class="option-chip ${b.extras.find((s) => s.id === ex.id) ? "selected" : ""}" onclick='toggleExtra(${JSON.stringify(ex)})'>
          <span>${ex.name}</span><span class="adj">+${money(ex.price)}</span>
        </div>`
        )
        .join("")}
    </div>

    <div class="card" style="background:var(--beige); box-shadow:none;">
      <div class="flex-between"><strong>Price</strong><span class="mono" style="font-size:1.2rem;">${money(unitPrice)}</span></div>
    </div>

    <div class="btn-group" style="margin-top:20px;">
      <button class="btn btn-outline" onclick="cancelBuilder()">← Back</button>
      <button class="btn btn-accent" onclick="addSandwichToBasket()" ${!b.filling || !b.bread ? "disabled" : ""}>Add to Order</button>
    </div>
  `;
}

function selectFilling(f) {
  state.builder.filling = f;
  renderSandwichBuilder();
}
function selectBread(br) {
  state.builder.bread = br;
  renderSandwichBuilder();
}
function toggleExtra(ex) {
  const b = state.builder;
  const idx = b.extras.findIndex((e) => e.id === ex.id);
  if (idx >= 0) b.extras.splice(idx, 1);
  else b.extras.push(ex);
  renderSandwichBuilder();
}

function addSandwichToBasket() {
  const b = state.builder;
  const unitPrice = b.filling.price + b.bread.price + b.extras.reduce((s, e) => s + e.price, 0);
  const options = [{ name: b.bread.name, price: b.bread.price }, ...b.extras.map((e) => ({ name: e.name, price: e.price }))];
  state.basket.push({
    key: "item-" + itemKeyCounter++,
    type: "sandwich",
    filling_id: b.filling.id,
    bread_id: b.bread.id,
    extra_ids: b.extras.map((e) => e.id),
    name: b.filling.name + " Sandwich",
    options,
    quantity: 1,
    total: unitPrice,
  });
  state.builder = null;
  renderItemsStep();
}

function cancelBuilder() {
  state.builder = null;
  renderItemsStep();
}

// ---------------------------------------------------------------------------
// Step 6 — Payment Method
// ---------------------------------------------------------------------------

function renderPaymentMethodStep() {
  stepContainer.innerHTML = `
    <div class="step-label">Step 6 of 8</div>
    <h2>Payment Method</h2>
    <div class="pay-tiles">
      <div class="pay-tile" onclick="selectPaymentMethod('Card')">💳 Card</div>
      <div class="pay-tile" onclick="selectPaymentMethod('Cash')">💵 Cash</div>
    </div>
    <div class="btn-group">
      <button class="btn btn-outline" onclick="goToStep(4)">← Back</button>
    </div>
  `;
}

function selectPaymentMethod(method) {
  state.paymentMethod = method;
  state.paymentConfirmed = false;
  state.amountReceived = "";
  goToStep(6);
}

// ---------------------------------------------------------------------------
// Step 7 — Payment Detail (Card or Cash)
// ---------------------------------------------------------------------------

function renderPaymentDetailStep() {
  const total = basketTotal();
  if (state.paymentMethod === "Card") {
    stepContainer.innerHTML = `
      <div class="step-label">Step 7 of 8</div>
      <h2>Card Payment</h2>
      <p class="text-muted">Order total: <strong>${money(total)}</strong></p>
      <div class="card" style="background:var(--beige); box-shadow:none;">
        <p style="margin-top:0;">Present the contactless terminal or QR code to the customer to take payment.</p>
        <p class="text-muted" style="font-size:0.82rem;">This build does not connect to a live payment provider. Use the button below to simulate a successful, clearly-labelled demo payment.</p>
        <button class="btn btn-accent btn-block" onclick="confirmCardPayment()">
          ${state.paymentConfirmed ? "✓ Payment Confirmed (Simulated)" : "Simulate Payment — Demo Mode"}
        </button>
      </div>
      <div class="btn-group" style="margin-top:16px;">
        <button class="btn btn-outline" onclick="goToStep(5)">← Back</button>
        <button class="btn btn-primary" onclick="goToStep(7)" ${!state.paymentConfirmed ? "disabled" : ""}>Continue to Review →</button>
      </div>
    `;
  } else {
    const received = parseFloat(state.amountReceived || "0") || 0;
    const change = received - total;
    stepContainer.innerHTML = `
      <div class="step-label">Step 7 of 8</div>
      <h2>Cash Payment</h2>
      <div class="receipt-line"><span class="k">Order total</span><span class="mono">${money(total)}</span></div>
      <div class="field" style="max-width:260px; margin-top:16px;">
        <label for="cash-amount">Amount Received</label>
        <input type="number" step="0.01" min="0" id="cash-amount" value="${state.amountReceived}" oninput="updateCashAmount(this.value)" placeholder="0.00">
      </div>
      <div class="change-display">
        <div class="text-muted" style="font-size:0.8rem; text-transform:uppercase; letter-spacing:0.05em;">Change Due</div>
        <div class="amount ${change < 0 ? "negative" : ""}">${money(Math.abs(change))}</div>
        ${change < 0 ? `<p class="text-muted" style="margin:6px 0 0 0;">Amount received is less than the total.</p>` : ""}
      </div>
      <div class="btn-group" style="margin-top:20px;">
        <button class="btn btn-outline" onclick="goToStep(5)">← Back</button>
        <button class="btn btn-primary" onclick="goToStep(7)" ${received < total ? "disabled" : ""}>Continue to Review →</button>
      </div>
    `;
  }
}

function confirmCardPayment() {
  state.paymentConfirmed = true;
  renderPaymentDetailStep();
}

function updateCashAmount(v) {
  state.amountReceived = v;
  renderPaymentDetailStep();
}

// ---------------------------------------------------------------------------
// Step 8 — Summary
// ---------------------------------------------------------------------------

function renderSummaryStep() {
  const total = basketTotal();
  stepContainer.innerHTML = `
    <div class="step-label">Step 8 of 8</div>
    <h2>Order Summary</h2>

    <div class="receipt-line"><span class="k">Location</span><span>${state.location.name} <a href="#" onclick="goToStep(0); return false;" style="font-size:0.8rem; margin-left:8px;">Edit</a></span></div>
    <div class="receipt-line"><span class="k">Table</span><span>${state.table} <a href="#" onclick="goToStep(1); return false;" style="font-size:0.8rem; margin-left:8px;">Edit</a></span></div>
    <div class="receipt-line"><span class="k">Allergies</span><span>${
      state.allergyStatus ? state.allergens.join(", ") || "Declared" : "None declared"
    } <a href="#" onclick="goToStep(2); return false;" style="font-size:0.8rem; margin-left:8px;">Edit</a></span></div>
    <div class="receipt-line"><span class="k">Member</span><span>${state.member ? state.member.member_number + " — " + state.member.name : "—"} <a href="#" onclick="goToStep(3); return false;" style="font-size:0.8rem; margin-left:8px;">Edit</a></span></div>

    <h3 style="margin-top:20px;">Items <a href="#" onclick="goToStep(4); return false;" style="font-size:0.8rem; margin-left:8px;">Edit Items</a></h3>
    ${state.basket
      .map(
        (item) => `<div class="receipt-line"><span>${item.name}${item.options.length ? " — " + item.options.map((o) => o.name).join(", ") : ""}</span><span class="mono">${money(item.total)}</span></div>`
      )
      .join("")}

    <div class="receipt-line"><span class="k">Payment Method</span><span>${state.paymentMethod} <a href="#" onclick="goToStep(5); return false;" style="font-size:0.8rem; margin-left:8px;">Edit</a></span></div>
    ${state.paymentMethod === "Cash" ? `<div class="receipt-line"><span class="k">Change Due</span><span class="mono">${money(parseFloat(state.amountReceived || 0) - total)}</span></div>` : ""}

    <div class="receipt-line" style="border-top:2px solid var(--border); font-weight:700; margin-top:10px; padding-top:14px;">
      <span>Total Price</span><span class="mono" style="font-size:1.2rem;">${money(total)}</span>
    </div>

    <div id="place-order-error" style="color:var(--red); margin-top:12px; font-size:0.88rem;"></div>

    <div class="btn-group" style="margin-top:20px;">
      <button class="btn btn-outline" onclick="goToStep(6)">← Back</button>
      <button class="btn btn-accent" id="place-order-btn" onclick="placeOrder()">Place Order</button>
    </div>
  `;
}

function placeOrder() {
  const btn = document.getElementById("place-order-btn");
  btn.disabled = true;
  btn.textContent = "Placing Order…";

  const payload = {
    location_id: state.location.id,
    table_number: state.table,
    allergy_status: state.allergyStatus,
    allergens: state.allergens,
    member_id: state.member ? state.member.id : null,
    payment_method: state.paymentMethod,
    amount_received: state.paymentMethod === "Cash" ? parseFloat(state.amountReceived || 0) : undefined,
    payment_confirmed: state.paymentMethod === "Card" ? state.paymentConfirmed : true,
    items: state.basket.map((item) =>
      item.type === "drink"
        ? { type: "drink", menu_item_id: item.menu_item_id, option_ids: item.option_ids, quantity: item.quantity }
        : { type: "sandwich", filling_id: item.filling_id, bread_id: item.bread_id, extra_ids: item.extra_ids, quantity: item.quantity }
    ),
  };

  fetch(window.CREATE_ORDER_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.error) {
        document.getElementById("place-order-error").textContent = data.error;
        btn.disabled = false;
        btn.textContent = "Place Order";
        return;
      }
      state.confirmedOrderNumber = data.order_number;
      goToStep(8);
    })
    .catch(() => {
      document.getElementById("place-order-error").textContent = "Something went wrong. Please try again.";
      btn.disabled = false;
      btn.textContent = "Place Order";
    });
}

// ---------------------------------------------------------------------------
// Step 9 — Confirmation
// ---------------------------------------------------------------------------

function renderConfirmationStep() {
  stepContainer.innerHTML = `
    <div class="empty-state">
      <div class="icon">✅</div>
      <h2>Order Placed</h2>
      <p class="text-muted">Order <strong class="mono">${state.confirmedOrderNumber}</strong> has been sent to the kitchen.</p>
      <div class="btn-group" style="justify-content:center; margin-top:20px;">
        <a href="${window.ORDERS_LIST_URL}" class="btn btn-outline">View My Orders</a>
        <button class="btn btn-accent" onclick="resetWizard()">Start New Order</button>
      </div>
    </div>
  `;
  basketContainer.innerHTML = "";
}

function resetWizard() {
  state.step = 0;
  state.location = null;
  state.table = null;
  state.allergyStatus = false;
  state.allergens = [];
  state.member = null;
  state.basket = [];
  state.paymentMethod = null;
  state.amountReceived = "";
  state.paymentConfirmed = false;
  state.builder = null;
  render();
}
