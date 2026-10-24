import { equalSecret } from './auth.mjs';

export async function deploymentCheck(request: Request, token: string | undefined, version: { build_id: string; wire_schema_version: string }) {
  const respond = (status: number, body: unknown) => Response.json(body, {
    status, headers: { 'Cache-Control': 'no-store', 'Vary': 'Authorization' },
  });
  if (request.method !== 'GET') return respond(405, { error: 'GET required' });
  if (!token || token.length < 32) return respond(503, { error: 'Deployment check unavailable' });
  const auth = request.headers.get('authorization') || '';
  if (auth.length > 1024 || !await equalSecret(auth, `Bearer ${token}`)) return respond(401, { error: 'Unauthorized' });
  return respond(200, { build_id: version.build_id, wire_schema_version: version.wire_schema_version });
}