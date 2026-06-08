/**
 * Single source of truth for the frontend application version.
 *
 * FRONTEND_VERSION follows semantic versioning (MAJOR.MINOR.PATCH).
 * Bump this manually in tandem with package.json when shipping a release.
 *
 * API_VERSION_PREFIX must match the API_VERSION in backend/version.py.
 * Update it here when you upgrade the backend API to a new major version,
 * so the /about page can flag a mismatch between the frontend and backend.
 */

export const FRONTEND_VERSION = "0.2.1";

/**
 * The API version this frontend build was written against.
 * Used in the /about page to detect frontend/backend version skew.
 */
export const API_VERSION_PREFIX = "v1";
