// Signed expiring cookie (HMAC-SHA256). Works in Edge middleware and Node.
const enc = new TextEncoder();
const hex = (b: ArrayBuffer) => [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
async function sign(data: string, secret: string) {
  const k = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return hex(await crypto.subtle.sign("HMAC", k, enc.encode(data)));
}
export const COOKIE = "radar_session";
export async function makeToken(secret: string, ttlSec = 60 * 60 * 12) {
  const exp = String(Math.floor(Date.now() / 1000) + ttlSec);
  return `${exp}.${await sign(exp, secret)}`;
}
export async function verifyToken(tok: string | undefined, secret: string | undefined) {
  if (!tok || !secret) return false;
  const [exp, mac] = tok.split(".");
  if (!exp || !mac || Number(exp) < Date.now() / 1000) return false;
  const want = await sign(exp, secret);
  let diff = want.length ^ mac.length;
  for (let i = 0; i < want.length; i++) diff |= want.charCodeAt(i) ^ (mac.charCodeAt(i) || 0);
  return diff === 0;
}
