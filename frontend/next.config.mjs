/**
 * Security headers for every route.
 *
 * CSP choices (Next 16 App Router, no nonces):
 * - script-src 'unsafe-inline': Next injects inline bootstrap/hydration scripts. Removing it needs a
 *   nonce via middleware; do that if the event's app handles untrusted HTML.
 * - 'unsafe-eval' and ws: are added in `next dev` only (React Refresh + HMR websocket).
 * - style-src 'unsafe-inline': Next/Tailwind inject style tags.
 * - connect-src: the API origin (NEXT_PUBLIC_API_URL) for fetch + EventSource (SSE trace stream).
 * - frame-ancestors 'none' + X-Frame-Options DENY: no clickjacking via iframes.
 * @type {import('next').NextConfig}
 */
const isDev = process.env.NODE_ENV !== "production";

function apiOrigin() {
  try {
    return new URL(process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8787").origin;
  } catch {
    return "http://localhost:8787";
  }
}

const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self' ${apiOrigin()}${isDev ? " ws:" : ""}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig = {
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
