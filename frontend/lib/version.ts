/**
 * FRONTEND_VERSION is read from package.json at build time via
 * NEXT_PUBLIC_APP_VERSION (injected by next.config.mjs).
 * To bump the version, update package.json only — this file never changes.
 *
 * API_VERSION_PREFIX must match API_VERSION in backend/version.py.
 * Update it here when the backend REST API moves to a new major version.
 */

export const FRONTEND_VERSION = process.env.NEXT_PUBLIC_APP_VERSION ?? "0.0.0";

/**
 * The API version this frontend build was written against.
 * Used in the /about page to detect frontend/backend version skew.
 */
export const API_VERSION_PREFIX = "v1";
