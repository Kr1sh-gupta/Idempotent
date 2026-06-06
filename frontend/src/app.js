const api = "http://localhost:8000";
let selected = new Set();
let reservationId = null;
let paymentRef = null;

function idem(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function updateStatus(msg, type = 'info') {
  const statusEl = document.getElementById("status");
  statusEl.innerHTML = msg;
  statusEl.style.borderLeftColor = type === 'error' ? 'var(--danger)' : 
                                   type === 'success' ? 'var(--success)' : 
                                   type === 'warning' ? 'var(--warning)' : 'var(--primary)';
}

async function loadSeats() {
  try {
    const res = await fetch(`${api}/seats?show_id=show-1`);
    const data = await res.json();
    const box = document.getElementById("seats");
    box.innerHTML = "";
    data.seats.forEach((s) => {
      const b = document.createElement("button");
      b.className = `seat ${s.status === "SOLD" ? "sold" : "available"}`;
      if (selected.has(s.seat_no)) b.classList.add("selected");
      b.textContent = s.seat_no;
      if (s.status === "SOLD") b.disabled = true;
      b.onclick = () => {
        if (selected.has(s.seat_no)) selected.delete(s.seat_no); else selected.add(s.seat_no);
        renderSelected();
        b.classList.toggle("selected");
      };
      box.appendChild(b);
    });
  } catch (err) {
    updateStatus("Failed to load seats. Ensure API is running.", "error");
  }
}

function renderSelected() {
  document.getElementById("selected").textContent = [...selected].join(", ") || "none";
}

async function refreshTimeline() {
  if (!reservationId) return;
  const ind = document.getElementById("refresh-indicator");
  ind.style.opacity = 0.2;
  
  try {
    const res = await fetch(`${api}/demo/timeline?reservation_id=${reservationId}`);
    const data = await res.json();
    
    let html = `<div style="color: var(--success); margin-bottom: 10px;">Reservation: ${data.reservation.status}</div>`;
    
    if (data.events && data.events.length > 0) {
      data.events.forEach(ev => {
        const time = new Date(ev.at).toLocaleTimeString();
        
        let extraHighlight = "";
        if (ev.details && ev.details.payment_ref) {
          extraHighlight = `
            <div style="color: #60a5fa; font-weight: bold; background: rgba(96, 165, 250, 0.1); padding: 4px 8px; border-radius: 4px; margin: 6px 0; font-size: 0.85rem;">
              <div>🔑 Payment Ref:</div>
              <div style="font-family: monospace; word-break: break-all; margin-top: 2px;">${ev.details.payment_ref}</div>
            </div>`;
        }
        
        html += `<div class="log-entry">
          <span style="color: var(--warning)">[${time}]</span> 
          <strong style="color: #fff">${ev.event_type}</strong>
          <br/>
          ${extraHighlight}
          <pre style="color: var(--text-muted); margin: 4px 0 0 0; padding: 6px; background: rgba(0,0,0,0.2); border-radius: 4px; font-size: 0.75rem; overflow-x: auto; font-family: monospace;">${JSON.stringify(ev.details, null, 2)}</pre>
        </div>`;
      });
    } else {
      html += `<div>No events logged yet.</div>`;
    }
    
    document.getElementById("timeline").innerHTML = html;
  } catch(e) {
    console.error(e);
  }
  
  setTimeout(() => ind.style.opacity = 1, 300);
}

async function reserve() {
  if (!selected.size) return updateStatus("Please select at least one seat first.", "warning");
  
  document.getElementById("reserve").disabled = true;
  document.getElementById("reserve").classList.add("loading-pulse");
  updateStatus("Reserving seats...", "info");
  
  const payload = {
    movie_id: "movie-1",
    show_id: "show-1",
    seat_ids: [...selected],
    user_ref: "demo-user",
    idempotency_key: idem("reserve")
  };
  
  try {
    const r = await fetch(`${api}/reservations`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
    const data = await r.json();
    reservationId = data.reservation_id;
    updateStatus(`✅ Reserved successfully! ID: <strong style="color:white">${reservationId}</strong>`, "success");
    
    document.getElementById("pay").disabled = false;
    document.getElementById("reserve").classList.remove("loading-pulse");
    
    await refreshTimeline();
  } catch (err) {
    updateStatus("Error reserving seats.", "error");
    document.getElementById("reserve").disabled = false;
    document.getElementById("reserve").classList.remove("loading-pulse");
  }
}

let activePaymentIdem = null;
let paymentInProgress = false;

async function pay() {
  if (!reservationId) return updateStatus("Reserve first", "warning");
  
  // Generate idempotency key only on the first click of this session
  if (!activePaymentIdem) {
    activePaymentIdem = idem("pay");
  }
  
  const currentClickId = Date.now().toString().slice(-4);
  updateStatus(`Sent payment request [Click ID: ${currentClickId}]...`, "warning");
  
  const reqIdem = activePaymentIdem;
  const isDropSimulated = document.getElementById("simulate-drop").checked;
  
  try {
    const r = await fetch(`${api}/payments/initiate`, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        ...(isDropSimulated && { "X-Simulate-Drop": "true" })
      },
      body: JSON.stringify({ reservation_id: reservationId, idempotency_key: reqIdem })
    });
    
    if (r.status === 409) {
      updateStatus(`⛔ [Click ID: ${currentClickId}] Blocked by Idempotency Lock! Another request is already processing.`, "error");
      return;
    }
    
    if (r.status === 504) {
      updateStatus(`🚨 NETWORK DISCONNECTED: 504 Gateway Timeout.<br/>The server processed the payment, but the connection dropped before returning the response to you! <br/><br/><strong>Did you get charged? Try clicking "Retry Payment"!</strong>`, "error");
      
      const payBtn = document.getElementById("pay");
      payBtn.textContent = "Retry Payment";
      payBtn.classList.remove("loading-pulse");
      payBtn.disabled = false;
      document.getElementById("simulate-drop").checked = false; // Turn off toggle so next click works
      
      await refreshTimeline();
      return;
    }
    
    const d = await r.json();
    if (!paymentRef) paymentRef = d.payment_ref;
    
    const idemHeader = r.headers.get("X-Idempotency") || "MISS";
    
    if (idemHeader === "HIT") {
      updateStatus(`⚡ <strong>IDEMPOTENCY CACHE HIT!</strong><br/>The server recognized your idempotency key, saw it had already processed the payment during the dropped connection, and instantly returned the cached response. <br/><strong>You were NOT charged twice!</strong>`, "success");
    } else {
      updateStatus(`✅ [Click ID: ${currentClickId}] Payment processed successfully!`, "success");
    }
    document.getElementById("confirm").disabled = false;
    document.getElementById("pay").disabled = true; // Disable after successful creation
    document.getElementById("pay").textContent = "Pay Now"; // Reset text
    
  } catch (err) {
    updateStatus(`Error during payment initiation: ${err.message}`, "error");
  }
  
  await refreshTimeline();
}

async function confirm() {
  if (!paymentRef) return updateStatus("Initiate payment first", "warning");
  
  const btn = document.getElementById("confirm");
  btn.disabled = true;
  btn.classList.add("loading-pulse");
  updateStatus("Confirming payment...", "info");
  
  try {
    const r = await fetch(`${api}/payments/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payment_ref: paymentRef, idempotency_key: idem("confirm") })
    });
    const d = await r.json();
    
    updateStatus(`🎉 Payment Confirmed! Status: ${d.status}`, "success");
    
    // Refresh board
    selected.clear();
    renderSelected();
    await loadSeats();
    await refreshTimeline();
    
    // Reset flow
    reservationId = null;
    paymentRef = null;
    activePaymentIdem = null;
    document.getElementById("reserve").disabled = false;
  } catch(err) {
    updateStatus("Error confirming payment.", "error");
  } finally {
    btn.classList.remove("loading-pulse");
  }
}

document.getElementById("reserve").onclick = reserve;
document.getElementById("pay").onclick = pay;
document.getElementById("confirm").onclick = confirm;

loadSeats();
setInterval(refreshTimeline, 2000);