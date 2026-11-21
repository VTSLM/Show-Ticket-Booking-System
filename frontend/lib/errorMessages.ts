/**
 * Centralized, user-friendly error messages.
 *
 * Every raw technical string (Firebase codes, HTTP status text, network errors)
 * is mapped here so the rest of the app can call a single helper instead of
 * duplicating mapping logic.
 */

/* ------------------------------------------------------------------ */
/*  Firebase Auth error codes → friendly strings                       */
/* ------------------------------------------------------------------ */

const FIREBASE_MESSAGES: Record<string, string> = {
  "auth/invalid-credential":
    "Incorrect email or password. Please try again.",
  "auth/wrong-password":
    "Incorrect email or password. Please try again.",
  "auth/user-not-found":
    "Incorrect email or password. Please try again.",
  "auth/invalid-email":
    "Please enter a valid email address.",
  "auth/email-already-in-use":
    "An account with this email already exists. Please sign in.",
  "auth/weak-password":
    "Your password is too weak. Use at least 8 characters with a mix of letters, numbers and symbols.",
  "auth/too-many-requests":
    "Too many attempts. Please wait a moment and try again.",
  "auth/user-disabled":
    "This account has been disabled. Contact support for help.",
  "auth/account-exists-with-different-credential":
    "An account with this email already exists using a different sign-in method.",
  "auth/popup-closed-by-user":
    "Sign-in was cancelled. Please try again.",
  "auth/popup-blocked":
    "Sign-in popup was blocked by your browser. Allow popups and try again.",
  "auth/network-request-failed":
    "Unable to connect. Check your internet connection and try again.",
  "auth/requires-recent-login":
    "Your session has expired. Please log in again.",
  "auth/expired-action-code":
    "This link has expired. Please request a new one.",
  "auth/invalid-action-code":
    "This link is invalid or has already been used.",
};

/**
 * Extract a user-friendly message from a Firebase Auth error.
 *
 * Firebase errors carry a `code` property (e.g. `"auth/invalid-credential"`).
 * If the code is recognised we return the mapped text; otherwise we return a
 * safe generic fallback so raw Firebase internals never reach the UI.
 */
export function friendlyFirebaseMessage(
  error: unknown,
  fallback = "Something went wrong. Please try again."
): string {
  if (error && typeof error === "object" && "code" in error) {
    const code = (error as { code: string }).code;
    if (FIREBASE_MESSAGES[code]) return FIREBASE_MESSAGES[code];
  }
  // Keep the original message only if it already looks user-readable
  // (i.e. not a Firebase internal like "Firebase: Error (auth/...)").
  if (error instanceof Error) {
    const msg = error.message;
    if (
      msg.startsWith("Firebase:") ||
      msg.includes("auth/") ||
      msg.includes("firebaseError")
    ) {
      return fallback;
    }
  }
  return fallback;
}

/* ------------------------------------------------------------------ */
/*  HTTP / API error mapping                                           */
/* ------------------------------------------------------------------ */

const HTTP_MESSAGES: Record<number, string> = {
  400: "The request could not be completed. Please check your input and try again.",
  401: "Your session has expired. Please log in again.",
  403: "You don't have permission to perform this action.",
  404: "The requested resource was not found.",
  409: "This action conflicts with the current state. Please refresh and try again.",
  422: "Some of the information provided is invalid. Please check and try again.",
  429: "Too many requests. Please wait a moment and try again.",
  500: "Something went wrong on our end. Please try again later.",
  502: "The server is temporarily unavailable. Please try again later.",
  503: "The service is temporarily unavailable. Please try again later.",
  504: "The request timed out. Please try again later.",
};

/**
 * Map an HTTP status code + optional backend `detail` to a user-friendly
 * string.
 *
 * When the backend sends a descriptive `detail` it is usually already
 * human-readable (e.g. "Cannot create show on a screen with no seats and no
 * admission zones"), so we pass it through.  We only override when `detail`
 * looks like a raw status text ("Internal Server Error") or is missing.
 */
export function friendlyApiMessage(
  status: number,
  detail?: unknown
): string {
  if (status >= 500) {
    return HTTP_MESSAGES[status] || "Something went wrong on our end. Please try again later.";
  }

  if (status === 401) {
    const text = typeof detail === "string" ? detail.toLowerCase() : "";
    if (text.includes("session") || text.includes("inactivity") || text.includes("revoked")) {
      return "Your session has expired. Please log in again.";
    }
    if (text.includes("credential") || text.includes("password") || text.includes("email")) {
      return "Incorrect email or password. Please try again.";
    }
    return "Please log in to continue.";
  }

  if (status === 403) {
    return "You don't have permission to perform this action.";
  }

  if (status === 422 && Array.isArray(detail)) {
    const fields = detail
      .map((issue) => {
        if (!issue || typeof issue !== "object") return "";
        const item = issue as { loc?: unknown[]; msg?: unknown };
        const field = item.loc?.filter((part) => part !== "body" && part !== "query").at(-1);
        return typeof field === "string" && typeof item.msg === "string"
          ? `${field.replaceAll("_", " ")}: ${item.msg}`
          : typeof item.msg === "string" ? item.msg : "";
      })
      .filter(Boolean);
    if (fields.length) return `Please check the following: ${fields.join("; ")}`;
  }

  if (status === 422 && detail && typeof detail === "object") {
    const validation = detail as { message?: unknown; errors?: unknown };
    const errors = Array.isArray(validation.errors)
      ? validation.errors.filter((item): item is string => typeof item === "string")
      : validation.errors && typeof validation.errors === "object"
        ? Object.values(validation.errors as Record<string, unknown>)
            .filter((item): item is string => typeof item === "string")
        : [];
    if (errors.length) return `Please check the following: ${errors.join("; ")}`;
    if (typeof validation.message === "string" && !isInternalError(validation.message)) {
      return validation.message;
    }
  }

  // If the backend sent a real detail string that isn't the HTTP status text,
  // use it as-is — the routers already craft readable messages.
  if (
    typeof detail === "string" &&
    detail.trim() &&
    detail !== "Request failed" &&
    !isRawStatusText(detail) &&
    !isInternalError(detail)
  ) {
    return detail;
  }
  return HTTP_MESSAGES[status] || "Something went wrong. Please try again.";
}

/** Detect raw HTTP status-text strings browsers/servers produce. */
function isRawStatusText(detail: string): boolean {
  const raw = [
    "Internal Server Error",
    "Bad Gateway",
    "Service Unavailable",
    "Gateway Timeout",
    "Not Found",
    "Forbidden",
    "Unauthorized",
    "Bad Request",
    "Method Not Allowed",
    "OK",
  ];
  return raw.includes(detail);
}

/** Detect messages that reveal internal details. */
function isInternalError(detail: string): boolean {
  const lower = detail.toLowerCase();
  return (
    lower.includes("traceback") ||
    lower.includes("internal server error") ||
    lower.includes("database error") ||
    lower.includes("postgres") ||
    lower.includes("asyncpg") ||
    lower.includes("sqlstate") ||
    lower.includes("constraint ") ||
    lower.includes(" at character ") ||
    lower.includes("file \"") ||
    lower.includes("typeerror") ||
    lower.includes("referenceerror") ||
    lower.includes("syntaxerror") ||
    lower.includes("networkerror") ||
    lower.includes("failed to fetch") ||
    lower.includes("econnrefused") ||
    lower.includes("stack trace") ||
    lower.includes(" at ") && lower.includes(".ts:") ||
    lower.includes("syntax error") ||
    lower.includes("sql") ||
    lower.includes("relation ") ||
    lower.includes("column ") ||
    lower.includes("undefined") ||
    lower.includes("cannot read properties")
  );
}

/* ------------------------------------------------------------------ */
/*  Network / fetch wrapper                                            */
/* ------------------------------------------------------------------ */

/**
 * Wraps a thrown error from `fetch()` or any network-layer failure into a
 * user-friendly message.
 */
export function friendlyNetworkMessage(error: unknown): string {
  if (error instanceof TypeError) {
    // `TypeError: Failed to fetch` is the standard browser error for network
    // failures (CORS, DNS, offline, etc.).
    return "Unable to connect. Check your internet connection and try again.";
  }
  if (error instanceof Error && error.name === "AbortError") {
    return "The request was cancelled.";
  }
  return "Something went wrong. Please try again.";
}

/**
 * Generic catch-all: turn any unknown thrown value into a safe user-facing
 * string. Use this in places where `toast.error(e.message)` would leak
 * technical details.
 */
export function friendlyErrorMessage(
  error: unknown,
  fallback = "Something went wrong. Please try again."
): string {
  if (error instanceof Error) {
    const msg = error.message;
    // "Failed to fetch" is a network error that should be reworded.
    if (msg === "Failed to fetch" || msg === "NetworkError when attempting to fetch resource.") {
      return "Unable to connect. Check your internet connection and try again.";
    }
    // "Not authenticated" is thrown by our own api.ts — keep it friendly.
    if (msg === "Not authenticated") {
      return "Please log in to continue.";
    }
    if (
      msg.startsWith("Firebase:") ||
      msg.includes("auth/") ||
      isInternalError(msg) ||
      isRawStatusText(msg) ||
      error.name !== "Error" ||
      /^[A-Z][A-Z0-9_]+$/.test(msg)
    ) {
      return fallback;
    }
    return msg;
  }
  return fallback;
}
