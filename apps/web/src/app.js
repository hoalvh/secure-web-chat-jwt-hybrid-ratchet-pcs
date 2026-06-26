const $ = (selector) => document.querySelector(selector);

const state = {
  token: "",
  user: null,
  device: null,
  contact: "",
  contactBundle: null,
  keyBundles: new Map(),
  packetIds: new Set(),
  lastMessages: [],
  adminData: null,
  ws: null,
  refreshTimer: null,
  renderedKey: null,
  decryptCache: new Map(),
};

const SESSION_KEY = "secure-chat-session";
const ZERO_32 = new Uint8Array(32);
const encoder = new TextEncoder();
const decoder = new TextDecoder();

function setText(selector, value) {
  const element = $(selector);
  if (element) {
    element.textContent = value;
  }
}

function authLog(message) {
  setText("#authStatus", message);
}

function saveSession() {
  if (!state.token || !state.user) return;
  sessionStorage.setItem(
    SESSION_KEY,
    JSON.stringify({
      token: state.token,
      user: state.user,
    }),
  );
}

function loadSession() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (_) {
    return null;
  }
}

function clearSession() {
  sessionStorage.removeItem(SESSION_KEY);
}

function canonical(value) {
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonical(item)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function toBase64Url(bytesLike) {
  const bytes = bytesLike instanceof Uint8Array ? bytesLike : new Uint8Array(bytesLike);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) {
    const chunk = bytes.subarray(index, index + 0x8000);
    binary += String.fromCharCode(...chunk);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function fromBase64Url(value) {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (value.length % 4)) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function bytesToHex(bytesLike) {
  const bytes = bytesLike instanceof Uint8Array ? bytesLike : new Uint8Array(bytesLike);
  return [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function prettyFingerprint(hex) {
  return hex.match(/.{1,4}/g)?.slice(0, 12).join(" ") ?? hex;
}

function shortFingerprint(hex) {
  return prettyFingerprint(hex).split(" ").slice(0, 3).join(" ");
}

function packetKey(packet) {
  const header = packet.header || {};
  return [
    header.conversation_id,
    header.sender_user_id,
    header.recipient_user_id,
    header.message_number,
  ].join(":");
}

function conversationId(userA, userB) {
  return [userA, userB].sort().join("__");
}

async function sha256(bytes) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
}

async function fingerprintForPublicKey(publicKeyJwk) {
  return bytesToHex(await sha256(encoder.encode(canonical(publicKeyJwk))));
}

async function hkdfBytes(inputBytes, saltBytes, infoText, lengthBytes = 32) {
  const key = await crypto.subtle.importKey("raw", inputBytes, "HKDF", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    {
      name: "HKDF",
      hash: "SHA-256",
      salt: saltBytes,
      info: encoder.encode(infoText),
    },
    key,
    lengthBytes * 8,
  );
  return new Uint8Array(bits);
}

async function deriveRootKey(remotePublicJwk) {
  const privateKey = await crypto.subtle.importKey(
    "jwk",
    state.device.privateKeyJwk,
    { name: "ECDH", namedCurve: "P-256" },
    false,
    ["deriveBits"],
  );
  const remotePublic = await crypto.subtle.importKey(
    "jwk",
    remotePublicJwk,
    { name: "ECDH", namedCurve: "P-256" },
    false,
    [],
  );
  const sharedBits = new Uint8Array(
    await crypto.subtle.deriveBits({ name: "ECDH", public: remotePublic }, privateKey, 256),
  );
  const localFingerprint = state.device.fingerprint;
  const remoteFingerprint = await fingerprintForPublicKey(remotePublicJwk);
  const salt = await sha256(encoder.encode([localFingerprint, remoteFingerprint].sort().join("|")));
  return hkdfBytes(sharedBits, salt, "root-from-ecdh", 32);
}

async function deriveMessageKey(rootKey, header) {
  let chainKey = await hkdfBytes(
    rootKey,
    ZERO_32,
    `chain:v1:${header.conversation_id}:${header.sender_user_id}->${header.recipient_user_id}`,
    32,
  );
  for (let step = 1; step < Number(header.message_number); step += 1) {
    chainKey = await hkdfBytes(chainKey, ZERO_32, `next-chain-key:${step}`, 32);
  }
  return hkdfBytes(chainKey, ZERO_32, `message-key:${header.message_number}`, 32);
}

async function encryptPacket(plaintext) {
  if (!state.contactBundle) {
    throw new Error("Open a contact before sending");
  }
  const rootKey = await deriveRootKey(state.contactBundle.identity_public_key);
  const messageNumber = await nextMessageNumber();
  const header = {
    version: 1,
    conversation_id: conversationId(state.user.id, state.contact),
    sender_user_id: state.user.id,
    sender_device_id: state.device.deviceId,
    recipient_user_id: state.contact,
    recipient_device_id: state.contactBundle.device_id,
    message_number: messageNumber,
    ratchet_public_key: state.device.fingerprint,
  };
  const messageKey = await deriveMessageKey(rootKey, header);
  const aesKey = await crypto.subtle.importKey("raw", messageKey, "AES-GCM", false, ["encrypt"]);
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const sealed = new Uint8Array(
    await crypto.subtle.encrypt(
      { name: "AES-GCM", iv: nonce, additionalData: encoder.encode(canonical(header)), tagLength: 128 },
      aesKey,
      encoder.encode(plaintext),
    ),
  );
  const ciphertext = sealed.slice(0, sealed.length - 16);
  const tag = sealed.slice(sealed.length - 16);
  return {
    version: 1,
    algorithm: "ECDH-P-256+HKDF-SHA256+AES-GCM",
    header,
    nonce: toBase64Url(nonce),
    ciphertext: toBase64Url(ciphertext),
    tag: toBase64Url(tag),
  };
}

async function decryptPacket(packet, options = {}) {
  const header = packet.header || {};
  if (header.version !== 1) {
    throw new Error("Unsupported packet version");
  }
  if (![header.sender_user_id, header.recipient_user_id].includes(state.user.id)) {
    throw new Error("Packet does not belong to this user");
  }
  const id = packetKey(packet);
  if (options.checkReplay && state.packetIds.has(id)) {
    throw new Error("Replay detected");
  }
  const peer = header.sender_user_id === state.user.id ? header.recipient_user_id : header.sender_user_id;
  const bundle = await getKeyBundle(peer);
  const rootKey = await deriveRootKey(bundle.identity_public_key);
  const messageKey = await deriveMessageKey(rootKey, header);
  const aesKey = await crypto.subtle.importKey("raw", messageKey, "AES-GCM", false, ["decrypt"]);
  const ciphertext = fromBase64Url(packet.ciphertext);
  const tag = fromBase64Url(packet.tag);
  const sealed = new Uint8Array(ciphertext.length + tag.length);
  sealed.set(ciphertext);
  sealed.set(tag, ciphertext.length);
  const plaintext = await crypto.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: fromBase64Url(packet.nonce),
      additionalData: encoder.encode(canonical(header)),
      tagLength: 128,
    },
    aesKey,
    sealed,
  );
  if (options.markSeen) {
    state.packetIds.add(id);
  }
  return decoder.decode(plaintext);
}

function openDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("secure-web-chat-demo", 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("devices")) db.createObjectStore("devices", { keyPath: "username" });
      if (!db.objectStoreNames.contains("safety")) db.createObjectStore("safety", { keyPath: "id" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function idbGet(storeName, key) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, "readonly");
    const request = tx.objectStore(storeName).get(key);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    tx.oncomplete = () => db.close();
  });
}

async function idbPut(storeName, value) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, "readwrite");
    const request = tx.objectStore(storeName).put(value);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    tx.oncomplete = () => db.close();
  });
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }
  const response = await fetch(path, {
    ...options,
    headers,
    credentials: "include",
    body: options.body && !(options.body instanceof FormData) ? JSON.stringify(options.body) : options.body,
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(data.detail || response.statusText);
  }
  return data;
}

async function submitAuth(mode) {
  const username = $("#usernameInput").value.trim();
  const password = $("#passwordInput").value;
  if (!username || !password) return;
  authLog(`${mode === "register" ? "Registering" : "Logging in"}...`);
  const data = await api(`/auth/${mode}`, { method: "POST", body: { username, password } });
  state.token = data.access_token;
  state.user = data.user;
  saveSession();
  await enterApp();
}

async function enterApp() {
  $("#authPanel").hidden = true;
  stopAutoRefresh();
  if (state.user.is_admin) {
    $("#appPanel").hidden = true;
    $("#adminPanel").hidden = false;
    setText("#adminTitle", `${state.user.username} server dashboard`);
    await loadAdminDashboard();
    authLog("");
    return;
  }

  $("#adminPanel").hidden = true;
  $("#appPanel").hidden = false;
  setText("#sessionTitle", `${state.user.username} secure session`);
  await ensureDevice();
  await loadUsers();
  connectWebSocket();
  startAutoRefresh();
  authLog("");
}

async function restoreSession() {
  const saved = loadSession();
  if (!saved?.token) {
    authLog("Ready");
    return;
  }

  state.token = saved.token;
  authLog("Restoring session...");
  try {
    const data = await api("/me");
    state.user = data.user;
    saveSession();
    await enterApp();
  } catch (_) {
    state.token = "";
    state.user = null;
    clearSession();
    authLog("Session expired. Please login again.");
  }
}

async function ensureDevice() {
  let record = await idbGet("devices", state.user.id);
  if (!record) {
    const keyPair = await crypto.subtle.generateKey(
      { name: "ECDH", namedCurve: "P-256" },
      true,
      ["deriveBits"],
    );
    const publicKeyJwk = await crypto.subtle.exportKey("jwk", keyPair.publicKey);
    const privateKeyJwk = await crypto.subtle.exportKey("jwk", keyPair.privateKey);
    const fingerprint = await fingerprintForPublicKey(publicKeyJwk);
    record = {
      username: state.user.id,
      deviceId: `${state.user.id}-browser`,
      publicKeyJwk,
      privateKeyJwk,
      fingerprint,
      createdAt: new Date().toISOString(),
    };
    await idbPut("devices", record);
  }
  state.device = record;
  await api("/devices", {
    method: "POST",
    body: {
      device_id: record.deviceId,
      device_label: "Browser demo device",
      public_key_jwk: record.publicKeyJwk,
      fingerprint: record.fingerprint,
    },
  });
  setText("#deviceBadge", `Device ${shortFingerprint(record.fingerprint)}`);
  setText("#localDeviceId", record.deviceId);
  setText("#localKeyFingerprint", prettyFingerprint(record.fingerprint));
}

async function getKeyBundle(username) {
  const clean = username.trim().toLowerCase();
  if (state.keyBundles.has(clean)) {
    return state.keyBundles.get(clean);
  }
  const bundle = await api(`/keys/bundle/${encodeURIComponent(clean)}`);
  state.keyBundles.set(clean, bundle);
  return bundle;
}

async function loadUsers() {
  const data = await api("/users");
  const list = $("#userList");
  list.innerHTML = "";
  if (!data.users.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No contacts found";
    list.append(empty);
    return;
  }
  for (const user of data.users) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "user-item";
    item.addEventListener("click", () => openContact(user.username));

    const left = document.createElement("span");
    left.className = "user-left";
    const avatar = document.createElement("span");
    avatar.className = "avatar avatar-sm";
    avatar.textContent = (user.username[0] || "?").toUpperCase();

    const text = document.createElement("span");
    text.className = "user-meta";
    const name = document.createElement("strong");
    name.textContent = user.username;
    const meta = document.createElement("small");
    meta.textContent = user.created_at ? `Joined ${new Date(user.created_at).toLocaleDateString()}` : "Ready";
    text.append(name, meta);
    left.append(avatar, text);

    const action = document.createElement("span");
    action.className = "user-action";
    action.textContent = "Chat";
    item.append(left, action);
    list.append(item);
  }
}

function textOrDash(value) {
  return value === undefined || value === null || value === "" ? "-" : String(value);
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

async function copyCell(text, el) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (_) {
    // clipboard may be unavailable (e.g. insecure context); ignore
  }
  el.classList.add("copied");
  setTimeout(() => el.classList.remove("copied"), 800);
}

function appendCell(row, value, options = {}) {
  const cell = document.createElement("td");
  if (options.code) {
    const code = document.createElement("code");
    const text = typeof value === "string" ? value : JSON.stringify(value);
    code.textContent = text;
    code.title = "Click to copy"; // hover expands the value; click copies it
    code.addEventListener("click", () => copyCell(text, code));
    cell.append(code);
  } else {
    cell.textContent = textOrDash(value);
  }
  row.append(cell);
}

function appendBadgeCell(row, text, className) {
  const cell = document.createElement("td");
  const badge = document.createElement("span");
  badge.className = className;
  badge.textContent = text;
  cell.append(badge);
  row.append(cell);
}

function appendEmptyRow(tbody, colspan, message) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = colspan;
  cell.textContent = message;
  row.append(cell);
  tbody.append(row);
}

function renderAdminStats(storage) {
  const stats = $("#adminStats");
  stats.innerHTML = "";
  // icon + colour come from this fixed whitelist (no user data), so the static
  // markup below is safe; the dynamic value/label are set via textContent.
  const items = [
    ["Users", storage.users, "ti-users", "bg-primary"],
    ["Devices", storage.devices, "ti-device-desktop", "bg-azure"],
    ["Conversations", storage.conversations ?? 0, "ti-messages", "bg-purple"],
    ["Messages", storage.messages, "ti-lock", "bg-green"],
    ["Sessions", storage.refresh_sessions, "ti-key", "bg-orange"],
    ["Events", storage.security_events, "ti-activity", "bg-red"],
  ];
  for (const [label, value, icon, color] of items) {
    const col = document.createElement("div");
    col.className = "col-6 col-sm-4 col-xl-2";
    col.innerHTML =
      '<div class="card card-sm"><div class="card-body">' +
      '<div class="row align-items-center">' +
      `<div class="col-auto"><span class="avatar ${color} text-white"><i class="ti ${icon}"></i></span></div>` +
      '<div class="col"><div class="h1 mb-0 stat-value"></div><div class="text-secondary stat-label"></div></div>' +
      "</div></div></div>";
    col.querySelector(".stat-value").textContent = value;
    col.querySelector(".stat-label").textContent = label;
    stats.append(col);
  }
}

function renderAdminUsers(users) {
  const tbody = $("#adminUsersBody");
  tbody.innerHTML = "";
  if (!users.length) {
    appendEmptyRow(tbody, 4, "No users");
    return;
  }
  for (const user of users) {
    const row = document.createElement("tr");
    appendCell(row, user.username);
    appendCell(row, user.is_admin ? "admin" : "user");
    appendCell(row, user.password_hash, { code: true });
    appendCell(row, formatTime(user.created_at));
    tbody.append(row);
  }
}

function renderAdminMessages(messages) {
  const tbody = $("#adminMessagesBody");
  tbody.innerHTML = "";
  if (!messages.length) {
    appendEmptyRow(tbody, 6, "No stored ciphertext");
    return;
  }
  for (const message of messages) {
    const row = document.createElement("tr");
    appendCell(row, `#${message.message_number || "-"} ${message.conversation_id || message.id}`);
    appendCell(row, `${message.sender_user_id} -> ${message.recipient_user_id}`);
    appendCell(row, message.nonce, { code: true });
    appendCell(row, message.ciphertext, { code: true });
    appendCell(row, message.tag, { code: true });
    appendCell(row, formatTime(message.server_received_at));
    tbody.append(row);
  }
}

function renderAdminDevices(devices) {
  const tbody = $("#adminDevicesBody");
  tbody.innerHTML = "";
  if (!devices.length) {
    appendEmptyRow(tbody, 4, "No device public keys");
    return;
  }
  for (const device of devices) {
    const row = document.createElement("tr");
    appendCell(row, device.user_id);
    appendCell(row, device.device_label || device.id);
    appendCell(row, prettyFingerprint(device.fingerprint), { code: true });
    appendCell(row, device.identity_public_key, { code: true });
    tbody.append(row);
  }
}

function renderAdminSessions(sessions) {
  const tbody = $("#adminSessionsBody");
  tbody.innerHTML = "";
  if (!sessions.length) {
    appendEmptyRow(tbody, 5, "No refresh sessions");
    return;
  }
  for (const session of sessions) {
    const row = document.createElement("tr");
    appendCell(row, session.user_id);
    appendCell(row, session.id, { code: true });
    appendCell(row, session.refresh_token_hash, { code: true });
    appendCell(row, formatTime(session.expires_at ? session.expires_at * 1000 : null));
    appendCell(row, session.revoked_at ? formatTime(session.revoked_at) : "-");
    tbody.append(row);
  }
}

function renderAdminConversations(conversations) {
  const tbody = $("#adminConversationsBody");
  tbody.innerHTML = "";
  if (!conversations.length) {
    appendEmptyRow(tbody, 4, "No conversations");
    return;
  }
  for (const conversation of conversations) {
    const row = document.createElement("tr");
    appendCell(row, conversation.id, { code: true });
    appendCell(row, `${conversation.participant_a} ↔ ${conversation.participant_b}`);
    appendCell(row, formatTime(conversation.created_at));
    appendCell(row, formatTime(conversation.last_message_at));
    tbody.append(row);
  }
}

function renderAdminEvents(events) {
  const tbody = $("#adminEventsBody");
  tbody.innerHTML = "";
  if (!events.length) {
    appendEmptyRow(tbody, 6, "No security events");
    return;
  }
  for (const event of [...events].reverse()) {
    const row = document.createElement("tr");
    const level = (event.severity || "info").toLowerCase();
    appendBadgeCell(row, level, `sev sev-${level}`);
    appendCell(row, event.type);
    appendCell(row, event.actor_user_id || "system");

    const sourceCell = document.createElement("td");
    sourceCell.className = "source-cell";
    const ip = document.createElement("span");
    ip.textContent = event.actor_ip || "-";
    sourceCell.append(ip);
    if (event.actor_user_agent) {
      const agent = document.createElement("small");
      agent.textContent = event.actor_user_agent;
      agent.title = event.actor_user_agent;
      sourceCell.append(agent);
    }
    row.append(sourceCell);

    appendCell(row, formatTime(event.created_at));
    appendCell(row, event.detail || {}, { code: true });
    tbody.append(row);
  }
}

function renderAdminDashboard(data) {
  state.adminData = data;
  setText("#adminStoragePath", data.storage.store_file);
  renderAdminStats(data.storage);
  renderAdminUsers(data.users);
  renderAdminConversations(data.conversations || []);
  renderAdminMessages(data.messages);
  renderAdminDevices(data.devices);
  renderAdminSessions(data.refresh_sessions);
  renderAdminEvents(data.security_events);
}

async function loadAdminDashboard() {
  setText("#adminStatus", "Loading");
  const data = await api("/admin/dashboard");
  renderAdminDashboard(data);
  setText("#adminStatus", "Loaded");
}

async function openContact(username) {
  const clean = username.trim().toLowerCase();
  if (!clean) return;
  state.contact = clean;
  state.contactBundle = await getKeyBundle(clean);
  const safetyId = `${state.user.id}:${clean}`;
  const savedSafety = await idbGet("safety", safetyId);
  const current = state.contactBundle.fingerprint;
  if (savedSafety && savedSafety.fingerprint !== current) {
    $("#trustBadge").className = "badge bad";
    setText("#trustBadge", "Key changed");
  } else {
    $("#trustBadge").className = "badge ok";
    setText("#trustBadge", savedSafety ? "Key verified" : "Unverified key");
    if (!savedSafety) {
      await idbPut("safety", { id: safetyId, fingerprint: current, firstSeenAt: new Date().toISOString() });
    }
  }
  setText("#fingerprintView", prettyFingerprint(current));
  setText("#keyOwner", clean);
  setText("#keyDevice", state.contactBundle.device_id);
  setText("#conversationTitle", `${state.user.username} to ${clean}`);
  setText("#contactMeta", `Conversation ${conversationId(state.user.id, clean)} - message keys derived locally`);
  $("#messageInput").disabled = false;
  $("#sendButton").disabled = false;
  $("#cryptoBadge").className = "badge neutral";
  setText("#cryptoBadge", "ECDH ready");
  state.renderedKey = null; // force a fresh render when switching contacts
  await refreshMessages({ force: true });
}

async function nextMessageNumber() {
  const data = await api(`/messages/offline?peer=${encodeURIComponent(state.contact)}`);
  let max = 0;
  for (const message of data.messages) {
    const header = message.packet.header;
    if (header.sender_user_id === state.user.id && header.recipient_user_id === state.contact) {
      max = Math.max(max, Number(header.message_number));
    }
  }
  return max + 1;
}

async function refreshMessages(options = {}) {
  if (!state.contact) return;
  const data = await api(`/messages/offline?peer=${encodeURIComponent(state.contact)}`);
  const messages = data.messages.sort((a, b) => a.server_received_at.localeCompare(b.server_received_at));
  state.lastMessages = messages;

  // Only touch the DOM when the conversation actually changed. The 2.5s poll
  // (and WebSocket pushes) otherwise rebuilt the whole list every time, which
  // made the chat flicker continuously.
  const signature = messages.map((message) => message.id).join("|");
  if (!options.force && signature === state.renderedKey) return;

  const fragment = document.createDocumentFragment();
  if (!messages.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state conversation-empty";
    empty.textContent = "No messages in this conversation";
    fragment.append(empty);
  }
  for (const message of messages) {
    const packet = message.packet;
    const cacheKey = packetKey(packet);
    let body;
    let failed = false;
    if (state.decryptCache.has(cacheKey)) {
      body = state.decryptCache.get(cacheKey);
    } else {
      try {
        body = await decryptPacket(packet);
        state.packetIds.add(cacheKey);
        state.decryptCache.set(cacheKey, body); // cache so re-renders skip crypto
      } catch (error) {
        body = `Decrypt failed: ${error.message}`;
        failed = true;
      }
    }
    const bubble = document.createElement("article");
    bubble.className = `message ${packet.header.sender_user_id === state.user.id ? "me" : ""}`;
    const meta = document.createElement("div");
    meta.className = "meta";
    const actor = packet.header.sender_user_id === state.user.id ? "You" : packet.header.sender_user_id;
    meta.textContent = `${actor} - #${packet.header.message_number} - ${failed ? "decrypt failed" : "decrypted locally"}`;
    const text = document.createElement("div");
    text.className = "body";
    text.textContent = body;
    bubble.append(meta, text);
    fragment.append(bubble);
  }
  // Swap the whole list in one atomic operation (no empty flash).
  const messageList = $("#messageList");
  messageList.replaceChildren(fragment);
  state.renderedKey = signature;
  messageList.scrollTop = messageList.scrollHeight;
  $("#cryptoBadge").className = "badge ok";
  setText("#cryptoBadge", "AES-GCM active");
}

function startAutoRefresh() {
  stopAutoRefresh();
  state.refreshTimer = window.setInterval(async () => {
    if (!state.token || !state.contact) return;
    try {
      await refreshMessages();
    } catch (_) {
      setText("#syncBadge", "Refresh failed");
    }
  }, 2500);
}

function stopAutoRefresh() {
  if (state.refreshTimer) {
    window.clearInterval(state.refreshTimer);
    state.refreshTimer = null;
  }
}

async function sendMessage(event) {
  event.preventDefault();
  const input = $("#messageInput");
  const plaintext = input.value.trim();
  if (!plaintext) return;
  $("#sendButton").disabled = true;
  try {
    const started = performance.now();
    const packet = await encryptPacket(plaintext);
    await api("/messages", { method: "POST", body: { packet } });
    input.value = "";
    setText("#cryptoBadge", `Encrypted ${Math.round(performance.now() - started)} ms`);
    await refreshMessages();
  } finally {
    $("#sendButton").disabled = false;
  }
}

function connectWebSocket() {
  if (state.ws) state.ws.close();
  const wsUrl = `${location.origin.replace(/^http/, "ws")}/ws`;
  const ws = new WebSocket(wsUrl);
  state.ws = ws;
  ws.addEventListener("open", () => {
    ws.send(JSON.stringify({ type: "auth", access_token: state.token }));
  });
  ws.addEventListener("message", async (event) => {
    const frame = JSON.parse(event.data);
    if (frame.type === "auth_ok") {
      setText("#syncBadge", "WS auth ok");
    }
    if (frame.type === "encrypted_message" && state.contact) {
      await refreshMessages();
    }
  });
  ws.addEventListener("close", () => {
    if (state.user) setText("#syncBadge", "WS closed");
  });
}

async function logout() {
  try {
    if (state.token) await api("/auth/logout", { method: "POST" });
  } catch (_) {
    // Ignore logout network failures for local demo reset.
  }
  if (state.ws) state.ws.close();
  stopAutoRefresh();
  state.token = "";
  state.user = null;
  state.device = null;
  state.contact = "";
  state.contactBundle = null;
  state.keyBundles.clear();
  state.packetIds.clear();
  state.lastMessages = [];
  state.renderedKey = null;
  state.decryptCache.clear();
  state.adminData = null;
  clearSession();
  $("#appPanel").hidden = true;
  $("#adminPanel").hidden = true;
  $("#authPanel").hidden = false;
  authLog("Logged out");
}

function bind(selector, eventName, handler) {
  $(selector).addEventListener(eventName, async (event) => {
    try {
      await handler(event);
    } catch (error) {
      const message = error.message || String(error);
      authLog(message);
      setText("#syncBadge", "Action failed");
      setText("#adminStatus", "Action failed");
      console.error(error);
    }
  });
}

bind("#authForm", "submit", (event) => {
  event.preventDefault();
  return submitAuth("login");
});
bind("#registerButton", "click", () => submitAuth("register"));
bind("#logoutButton", "click", logout);
bind("#loadUsersButton", "click", loadUsers);
bind("#refreshButton", "click", refreshMessages);
bind("#openContactButton", "click", () => openContact($("#contactInput").value));
bind("#messageForm", "submit", sendMessage);
bind("#adminRefreshButton", "click", loadAdminDashboard);
bind("#adminLogoutButton", "click", logout);

restoreSession();
