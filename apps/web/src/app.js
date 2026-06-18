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
  ws: null,
  refreshTimer: null,
};

const SESSION_KEY = "secure-chat-session";
const ZERO_32 = new Uint8Array(32);
const encoder = new TextEncoder();
const decoder = new TextDecoder();

function setText(selector, value) {
  $(selector).textContent = value;
}

function setJson(selector, value) {
  setText(selector, JSON.stringify(value, null, 2));
}

function authLog(message) {
  setText("#authStatus", message);
}

function labLog(value) {
  if (typeof value === "string") {
    setText("#labOutput", value);
  } else {
    setJson("#labOutput", value);
  }
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
  setText("#deviceBadge", `Device ${prettyFingerprint(record.fingerprint).split(" ").slice(0, 3).join(" ")}`);
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
    empty.className = "user-item";
    empty.textContent = "No other users yet";
    list.append(empty);
    return;
  }
  for (const user of data.users) {
    const item = document.createElement("div");
    item.className = "user-item";
    const name = document.createElement("strong");
    name.textContent = user.username;
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Open";
    button.addEventListener("click", () => openContact(user.username));
    item.append(name, button);
    list.append(item);
  }
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
  setText("#conversationTitle", `${state.user.username} to ${clean}`);
  $("#messageInput").disabled = false;
  $("#sendButton").disabled = false;
  $("#cryptoBadge").className = "badge neutral";
  setText("#cryptoBadge", "ECDH ready");
  await refreshMessages();
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

async function refreshMessages() {
  if (!state.contact) return;
  const data = await api(`/messages/offline?peer=${encodeURIComponent(state.contact)}`);
  state.lastMessages = data.messages.sort((a, b) => a.server_received_at.localeCompare(b.server_received_at));
  const messageList = $("#messageList");
  messageList.innerHTML = "";
  for (const message of state.lastMessages) {
    const packet = message.packet;
    let body = "";
    let failed = false;
    try {
      body = await decryptPacket(packet);
      state.packetIds.add(packetKey(packet));
    } catch (error) {
      body = `Decrypt failed: ${error.message}`;
      failed = true;
    }
    const bubble = document.createElement("article");
    bubble.className = `message ${packet.header.sender_user_id === state.user.id ? "me" : ""}`;
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = `${packet.header.sender_user_id} #${packet.header.message_number} ${failed ? "decrypt failed" : "encrypted"}`;
    const text = document.createElement("div");
    text.className = "body";
    text.textContent = body;
    bubble.append(meta, text);
    messageList.append(bubble);
  }
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
      setText("#labBadge", "Auto refresh failed");
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
      setText("#labBadge", "WS auth ok");
    }
    if (frame.type === "encrypted_message" && state.contact) {
      await refreshMessages();
    }
  });
  ws.addEventListener("close", () => {
    if (state.user) setText("#labBadge", "WS closed");
  });
}

function latestPacketForLab() {
  if (!state.lastMessages.length) {
    throw new Error("Open a conversation with at least one message first");
  }
  return state.lastMessages[state.lastMessages.length - 1];
}

async function runServerDump() {
  const data = await api("/lab/messages");
  labLog({
    scenario: "SERVER_COMPROMISE_VIEWED",
    plaintext_exposed: data.messages.some((message) => message.plaintext !== null),
    rows: data.messages,
  });
}

async function runStolenJwt() {
  const data = await api("/lab/messages");
  labLog({
    scenario: "JWT_STOLEN_SIMULATED",
    server_access_with_token: true,
    decrypts_plaintext_without_device_key: false,
    visible_ciphertext_rows: data.messages.length,
  });
}

async function runReplay() {
  const message = latestPacketForLab();
  const data = await api("/lab/replay", { method: "POST", body: { message_id: message.id } });
  const replayKey = packetKey(data.packet);
  const replayRejected = state.packetIds.has(replayKey);
  labLog({
    scenario: "REPLAY_REJECTED",
    message_id: message.id,
    replay_accepted: !replayRejected,
    result: replayRejected ? "Replay detected by duplicate message counter" : "Replay would be accepted",
  });
}

async function runTamper() {
  const message = latestPacketForLab();
  const data = await api("/lab/tamper", { method: "POST", body: { message_id: message.id } });
  let tamperAccepted = false;
  let result = "";
  try {
    await decryptPacket(data.packet);
    tamperAccepted = true;
    result = "Tampered packet decrypted";
  } catch (error) {
    result = `Tamper detected: ${error.message || "AES-GCM tag invalid"}`;
  }
  labLog({
    scenario: "TAMPER_REJECTED",
    message_id: message.id,
    tamper_accepted: tamperAccepted,
    result,
  });
}

async function runKeySubstitution() {
  if (!state.contact) {
    throw new Error("Open a contact first");
  }
  await api("/lab/key-substitution", { method: "POST", body: { username: state.contact } });
  const fakeKeyPair = await crypto.subtle.generateKey(
    { name: "ECDH", namedCurve: "P-256" },
    true,
    ["deriveBits"],
  );
  const fakePublic = await crypto.subtle.exportKey("jwk", fakeKeyPair.publicKey);
  const fakeFingerprint = await fingerprintForPublicKey(fakePublic);
  const warningShown = fakeFingerprint !== state.contactBundle.fingerprint;
  $("#trustBadge").className = warningShown ? "badge bad" : "badge ok";
  setText("#trustBadge", warningShown ? "Key changed" : "Key verified");
  labLog({
    scenario: "KEY_SUBSTITUTION_WARNING",
    original_fingerprint: prettyFingerprint(state.contactBundle.fingerprint),
    substituted_fingerprint: prettyFingerprint(fakeFingerprint),
    key_substitution_warning_shown: warningShown,
  });
}

async function runPcs() {
  const data = await api("/lab/state-compromise", {
    method: "POST",
    body: {
      compromise_at_message: 3,
      rekey_at_message: 5,
      total_messages: 8,
    },
  });
  labLog({ scenario: "DH_REKEY_RECOVERED", ...data.metrics });
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
  clearSession();
  $("#appPanel").hidden = true;
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
      labLog({ error: message });
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
bind("#serverDumpButton", "click", runServerDump);
bind("#jwtButton", "click", runStolenJwt);
bind("#replayButton", "click", runReplay);
bind("#tamperButton", "click", runTamper);
bind("#keySubButton", "click", runKeySubstitution);
bind("#pcsButton", "click", runPcs);

restoreSession();
