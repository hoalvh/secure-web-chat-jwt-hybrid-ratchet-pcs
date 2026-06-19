#!/usr/bin/env node

import { readFile } from "node:fs/promises";
import { webcrypto } from "node:crypto";
import { resolve } from "node:path";

const { subtle } = webcrypto;
const encoder = new TextEncoder();
const decoder = new TextDecoder();
const ZERO_32 = new Uint8Array(32);

function usage(exitCode = 0) {
  const text = `
Usage:
  node scripts/decrypt_message.mjs --list
  node scripts/decrypt_message.mjs --device <device-json> --index <message-index>
  node scripts/decrypt_message.mjs --device <device-json> --message-id <message-id>
  node scripts/decrypt_message.mjs --device <device-json> --sender <user> --recipient <user> --number <n>

Options:
  --store <path>       Server JSON store. Default: data/demo_store.json
  --device <path>      Browser device JSON from IndexedDB. Can be the full
                       record with privateKeyJwk, or a raw private JWK.
  --username <user>    Required only when --device is a raw private JWK.
  --list               Print message indexes from the server store.

Examples:
  node scripts/decrypt_message.mjs --list
  node scripts/decrypt_message.mjs --device .\\tmp\\abcdd-device.json --index 0
  node scripts/decrypt_message.mjs --device .\\tmp\\abcdd-device.json --sender abcdd --recipient truonhgabccc --number 1
`;
  console.log(text.trim());
  process.exit(exitCode);
}

function arg(name) {
  const index = process.argv.indexOf(name);
  if (index === -1) return null;
  return process.argv[index + 1] ?? null;
}

function hasFlag(name) {
  return process.argv.includes(name);
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

function fromBase64Url(value) {
  return new Uint8Array(Buffer.from(value.replace(/-/g, "+").replace(/_/g, "/"), "base64"));
}

function bytesToHex(bytesLike) {
  const bytes = bytesLike instanceof Uint8Array ? bytesLike : new Uint8Array(bytesLike);
  return [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function sha256(bytes) {
  return new Uint8Array(await subtle.digest("SHA-256", bytes));
}

async function hkdfBytes(inputBytes, saltBytes, infoText, lengthBytes = 32) {
  const key = await subtle.importKey("raw", inputBytes, "HKDF", false, ["deriveBits"]);
  const bits = await subtle.deriveBits(
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

async function fingerprintForPublicKey(publicKeyJwk) {
  return bytesToHex(await sha256(encoder.encode(canonical(publicKeyJwk))));
}

function publicJwkFromPrivate(privateJwk) {
  return {
    crv: privateJwk.crv,
    ext: privateJwk.ext ?? true,
    key_ops: [],
    kty: privateJwk.kty,
    x: privateJwk.x,
    y: privateJwk.y,
  };
}

function normalizeDeviceRecord(rawDevice, usernameArg) {
  if (rawDevice.privateKeyJwk) {
    return {
      username: rawDevice.username,
      deviceId: rawDevice.deviceId,
      privateKeyJwk: rawDevice.privateKeyJwk,
      publicKeyJwk: rawDevice.publicKeyJwk ?? publicJwkFromPrivate(rawDevice.privateKeyJwk),
      fingerprint: rawDevice.fingerprint,
    };
  }

  if (!rawDevice.d) {
    throw new Error("Device JSON must contain privateKeyJwk or raw private JWK field d.");
  }
  if (!usernameArg) {
    throw new Error("--username is required when --device is a raw private JWK.");
  }
  return {
    username: usernameArg,
    deviceId: `${usernameArg}-browser`,
    privateKeyJwk: rawDevice,
    publicKeyJwk: publicJwkFromPrivate(rawDevice),
    fingerprint: null,
  };
}

function selectMessage(store, localUsername) {
  const messages = store.messages ?? [];
  const messageId = arg("--message-id");
  const indexRaw = arg("--index");
  const sender = arg("--sender");
  const recipient = arg("--recipient");
  const numberRaw = arg("--number");

  if (messageId) {
    return messages.find((message) => message.id === messageId);
  }
  if (indexRaw !== null) {
    const index = Number(indexRaw);
    if (!Number.isInteger(index) || index < 0) {
      throw new Error("--index must be a non-negative integer.");
    }
    return messages[index];
  }
  if (sender && recipient && numberRaw !== null) {
    const number = Number(numberRaw);
    return messages.find((message) => {
      const header = message.packet?.header ?? {};
      return (
        header.sender_user_id === sender &&
        header.recipient_user_id === recipient &&
        Number(header.message_number) === number
      );
    });
  }

  const firstForUser = messages.find((message) => {
    const header = message.packet?.header ?? {};
    return [header.sender_user_id, header.recipient_user_id].includes(localUsername);
  });
  if (firstForUser) return firstForUser;
  throw new Error("Choose a message with --index, --message-id, or --sender/--recipient/--number.");
}

function findRemoteDevice(store, header, localUsername) {
  const localIsSender = header.sender_user_id === localUsername;
  const localIsRecipient = header.recipient_user_id === localUsername;
  if (!localIsSender && !localIsRecipient) {
    throw new Error(`Private key username ${localUsername} is not in this message route.`);
  }

  const remoteUserId = localIsSender ? header.recipient_user_id : header.sender_user_id;
  const remoteDeviceId = localIsSender ? header.recipient_device_id : header.sender_device_id;
  const devices = store.devices ?? {};
  const exact = devices[remoteDeviceId];
  if (exact?.identity_public_key) return exact;

  const candidates = Object.values(devices).filter(
    (device) => device.user_id === remoteUserId && !device.revoked_at && device.identity_public_key,
  );
  if (!candidates.length) {
    throw new Error(`Cannot find remote public key for ${remoteUserId}.`);
  }
  candidates.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
  return candidates[0];
}

async function decryptMessage(store, device, message) {
  const packet = message.packet;
  const header = packet?.header;
  if (!packet || !header) {
    throw new Error("Selected message does not contain packet.header.");
  }

  const privateKey = await subtle.importKey(
    "jwk",
    device.privateKeyJwk,
    { name: "ECDH", namedCurve: "P-256" },
    false,
    ["deriveBits"],
  );
  const remoteDevice = findRemoteDevice(store, header, device.username);
  const remotePublicJwk = remoteDevice.identity_public_key;
  const remotePublic = await subtle.importKey(
    "jwk",
    remotePublicJwk,
    { name: "ECDH", namedCurve: "P-256" },
    false,
    [],
  );
  const sharedBits = new Uint8Array(
    await subtle.deriveBits({ name: "ECDH", public: remotePublic }, privateKey, 256),
  );

  const localFingerprint = device.fingerprint ?? (await fingerprintForPublicKey(device.publicKeyJwk));
  const remoteFingerprint = await fingerprintForPublicKey(remotePublicJwk);
  const salt = await sha256(encoder.encode([localFingerprint, remoteFingerprint].sort().join("|")));
  const rootKey = await hkdfBytes(sharedBits, salt, "root-from-ecdh", 32);
  let chainKey = await hkdfBytes(
    rootKey,
    ZERO_32,
    `chain:v1:${header.conversation_id}:${header.sender_user_id}->${header.recipient_user_id}`,
    32,
  );
  for (let step = 1; step < Number(header.message_number); step += 1) {
    chainKey = await hkdfBytes(chainKey, ZERO_32, `next-chain-key:${step}`, 32);
  }
  const messageKey = await hkdfBytes(chainKey, ZERO_32, `message-key:${header.message_number}`, 32);
  const aesKey = await subtle.importKey("raw", messageKey, "AES-GCM", false, ["decrypt"]);

  const ciphertext = fromBase64Url(packet.ciphertext);
  const tag = fromBase64Url(packet.tag);
  const sealed = new Uint8Array(ciphertext.length + tag.length);
  sealed.set(ciphertext);
  sealed.set(tag, ciphertext.length);

  const plaintext = await subtle.decrypt(
    {
      name: "AES-GCM",
      iv: fromBase64Url(packet.nonce),
      additionalData: encoder.encode(canonical(header)),
      tagLength: 128,
    },
    aesKey,
    sealed,
  );

  return {
    message_id: message.id,
    route: `${header.sender_user_id} -> ${header.recipient_user_id}`,
    conversation_id: header.conversation_id,
    message_number: header.message_number,
    local_user: device.username,
    remote_user: remoteDevice.user_id,
    local_fingerprint: localFingerprint,
    remote_fingerprint: remoteFingerprint,
    plaintext: decoder.decode(plaintext),
  };
}

async function readJson(path) {
  return JSON.parse(await readFile(resolve(path), "utf8"));
}

async function main() {
  if (hasFlag("--help") || hasFlag("-h")) usage(0);

  const storePath = arg("--store") ?? "data/demo_store.json";
  const store = await readJson(storePath);

  if (hasFlag("--list")) {
    const rows = (store.messages ?? []).map((message, index) => {
      const header = message.packet?.header ?? {};
      return {
        index,
        id: message.id,
        route: `${header.sender_user_id ?? "?"} -> ${header.recipient_user_id ?? "?"}`,
        conversation_id: header.conversation_id,
        message_number: header.message_number,
        received_at: message.server_received_at,
      };
    });
    console.table(rows);
    return;
  }

  const devicePath = arg("--device");
  if (!devicePath) usage(1);

  const rawDevice = await readJson(devicePath);
  const device = normalizeDeviceRecord(rawDevice, arg("--username"));
  const message = selectMessage(store, device.username);
  if (!message) {
    throw new Error("Message not found. Run with --list to see available indexes.");
  }

  try {
    const result = await decryptMessage(store, device, message);
    console.log(JSON.stringify({ ok: true, ...result }, null, 2));
  } catch (error) {
    console.error(
      JSON.stringify(
        {
          ok: false,
          error: error.message,
          hint: "Check that the private key belongs to sender/recipient, data/demo_store.json has the exact packet header, and the remote public key has not changed.",
        },
        null,
        2,
      ),
    );
    process.exit(2);
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
