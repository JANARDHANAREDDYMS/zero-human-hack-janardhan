export function toWireSchema(schema: unknown): any;
export function fromWireOutput(data: unknown, schema: unknown): unknown;
export function acceptsNull(schema: unknown, root: unknown): boolean;
export function isUnconstrained(schema: unknown): boolean;
export function decodeTypedValue(value: unknown): unknown;
export const TYPED_VALUE_DESC: string;
export const JSON_TEXT_DESC: string;
export const JSON_TEXT_ARRAY_DESC: string;
