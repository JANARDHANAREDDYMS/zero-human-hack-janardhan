export function createHandler(opts: {
  env: Record<string, string | undefined>;
  policy: unknown;
  validators: Record<string, (data: unknown) => boolean>;
  fetcher?: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
}): (request: Request) => Promise<Response>;
export const MAX_OUTPUT_TOKENS: number;
