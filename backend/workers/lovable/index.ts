// Deployment entry for a Lovable/Supabase Deno edge function.
// Keep worker.mjs, policy.json and deno.json beside this file.
import { createHandler } from './worker.mjs';
import policy from './policy.json' with { type: 'json' };
Deno.serve(createHandler({env:Deno.env.toObject(),policy}));
