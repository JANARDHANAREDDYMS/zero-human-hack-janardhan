// Shared bearer comparison; never logs credentials.
export async function equalSecret(a, b) {
  const hash = s => crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  const [x, y] = await Promise.all([hash(a), hash(b)]);
  const xa = new Uint8Array(x), ya = new Uint8Array(y);
  let diff = 0;
  for (let i = 0; i < xa.length; i++) diff |= xa[i] ^ ya[i];
  return diff === 0;
}