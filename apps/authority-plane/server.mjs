#!/usr/bin/env node
// The authority plane's production front (CR-3).
//
// In development Vite serves `dist`'s sources and proxies `/api` to the governed
// runtime worker's private TLS listener (`vite.config.ts`). Nothing plays that part in
// a built deployment, so this is that one process: it serves the built SPA and
// forwards `/api/*` to the worker over the private segment, which keeps the worker's
// origin private — the client's `VITE_WORKER_BASE_URL` stays unset and its `/api`
// default is same-origin (`src/api/client.ts`).
//
//   PORT        the port to listen on (default 8080)
//   WORKER_URL  the worker's private origin (default https://127.0.0.1:8444)
//
// The boundary this process holds, beyond the client's:
//
//   * only GET is forwarded, and only to a path `security/approved-operations.json`
//     approves — the same four AP-5 reads, read from the manifest rather than repeated
//     here, so a manifest that stops approving one stops this proxy forwarding it;
//   * no request header from the browser is forwarded. The plane holds no credential
//     and forwards none (README, "Run"); a read carries no header the worker reads, and
//     the write proof header can therefore never cross this process.
//
// The worker's certificate is private and not in a browser's or Node's trust store, so
// this proxy does not verify it, exactly as the dev proxy does not (`secure: false`).
// What protects the hop is the private segment, which is the deployment condition CR-3
// states; this process must not be given a public worker origin.
import { createReadStream, existsSync, readFileSync, statSync } from "node:fs";
import http from "node:http";
import https from "node:https";
import path from "node:path";
import { fileURLToPath } from "node:url";

const APP = path.dirname(fileURLToPath(import.meta.url));
const DIST = path.join(APP, "dist");
const INDEX = path.join(DIST, "index.html");
const MANIFEST = path.join(APP, "security", "approved-operations.json");

const PORT = Number(process.env.PORT ?? 8080);
const WORKER = new URL(process.env.WORKER_URL ?? "https://127.0.0.1:8444");
const API_PREFIX = "/api";

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".txt": "text/plain; charset=utf-8",
};

/** The approved reads, as matchers, from the manifest the boundary verifier holds. */
export function approvedMatchers(manifestText) {
  const manifest = JSON.parse(manifestText);
  return manifest.approved_paths.map((entry) => {
    const [method, template] = entry.split(" ");
    const source = template
      .split("/")
      .map((segment) => (/^\{[^}]*\}$/.test(segment) ? "[^/]+" : segment.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")))
      .join("/");
    return { method, template, pattern: new RegExp(`^${source}$`) };
  });
}

export function isApproved(matchers, method, pathname) {
  return matchers.some((m) => m.method === method && m.pattern.test(pathname));
}

/** The file `dist` should answer a request with, or null if the path escapes `dist`. */
export function resolveAsset(pathname) {
  let decoded;
  try {
    decoded = decodeURIComponent(pathname);
  } catch {
    return null;
  }
  const resolved = path.resolve(DIST, "." + path.posix.normalize(decoded));
  if (resolved !== DIST && !resolved.startsWith(DIST + path.sep)) return null;
  return resolved;
}

function sendJson(res, status, body) {
  const text = JSON.stringify(body);
  res.writeHead(status, { "content-type": "application/json; charset=utf-8", "content-length": Buffer.byteLength(text) });
  res.end(text);
}

function sendIndex(res, method) {
  if (!existsSync(INDEX)) return sendJson(res, 500, { error: "not_built", detail: "dist/index.html is missing; run npm run build" });
  const size = statSync(INDEX).size;
  res.writeHead(200, { "content-type": MIME[".html"], "content-length": size, "cache-control": "no-cache" });
  if (method === "HEAD") return res.end();
  createReadStream(INDEX).pipe(res);
}

function serveStatic(req, res) {
  const { pathname } = new URL(req.url, "http://localhost");
  const file = resolveAsset(pathname);
  if (file && existsSync(file) && statSync(file).isFile()) {
    const ext = path.extname(file);
    const immutable = pathname.startsWith("/assets/");
    res.writeHead(200, {
      "content-type": MIME[ext] ?? "application/octet-stream",
      "content-length": statSync(file).size,
      "cache-control": immutable ? "public, max-age=31536000, immutable" : "no-cache",
    });
    if (req.method === "HEAD") return res.end();
    return createReadStream(file).pipe(res);
  }
  // SPA fallback: the router owns every other path.
  return sendIndex(res, req.method);
}

function proxy(req, res, matchers) {
  const requested = new URL(req.url, "http://localhost");
  const pathname = requested.pathname.slice(API_PREFIX.length) || "/";
  if (req.method !== "GET") {
    return sendJson(res, 405, { error: "method_not_allowed", detail: "this front forwards reads only" });
  }
  if (!isApproved(matchers, "GET", pathname)) {
    return sendJson(res, 404, { error: "not_approved", detail: "not one of the reads security/approved-operations.json approves" });
  }
  const transport = WORKER.protocol === "https:" ? https : http;
  const upstream = transport.request(
    {
      protocol: WORKER.protocol,
      hostname: WORKER.hostname,
      port: WORKER.port || (WORKER.protocol === "https:" ? 443 : 80),
      path: pathname + requested.search,
      method: "GET",
      // changeOrigin: the worker sees its own host, not the browser's.
      headers: { host: WORKER.host, accept: "application/json" },
      rejectUnauthorized: false,
      timeout: 15_000,
    },
    (answer) => {
      res.writeHead(answer.statusCode ?? 502, {
        "content-type": answer.headers["content-type"] ?? MIME[".json"],
        "cache-control": "no-store",
      });
      answer.pipe(res);
    },
  );
  upstream.on("timeout", () => upstream.destroy(new Error("the worker did not answer in time")));
  upstream.on("error", (err) => {
    if (!res.headersSent) sendJson(res, 502, { error: "worker_unreachable", detail: err.message });
    else res.destroy();
  });
  req.resume(); // a read carries no body, and none is forwarded
  upstream.end();
}

export function createServer(matchers) {
  return http.createServer((req, res) => {
    const { pathname } = new URL(req.url ?? "/", "http://localhost");
    if (pathname === API_PREFIX || pathname.startsWith(API_PREFIX + "/")) return proxy(req, res, matchers);
    if (req.method !== "GET" && req.method !== "HEAD") {
      return sendJson(res, 405, { error: "method_not_allowed", detail: "this front serves reads only" });
    }
    return serveStatic(req, res);
  });
}

function main() {
  const matchers = approvedMatchers(readFileSync(MANIFEST, "utf-8"));
  createServer(matchers).listen(PORT, "0.0.0.0", () => {
    console.log(
      `authority plane on :${PORT}; /api -> ${WORKER.origin} (${matchers.length} approved reads, certificate unverified by design — private segment only, CR-3)`,
    );
  });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
