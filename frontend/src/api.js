const TOKENS_KEY = "argus.tokens";

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new Error(`${response.status} ${detail}`);
  }
  return response.status === 204 ? null : response.json();
}

export const api = {
  services: () => request("/api/services"),
  fleet: (window) => request(`/api/slo/budget?window=${window}`),
  uptime: (id, window) => request(`/api/services/${id}/uptime?window=${window}`),
  register: (body) => request("/api/services", { method: "POST", body: JSON.stringify(body) }),
  remove: (id) => request(`/api/services/${id}`, { method: "DELETE" }),
  beat: (id, token, status = "ok") =>
    request(`/api/services/${id}/heartbeat`, {
      method: "POST",
      headers: { "X-Argus-Token": token },
      body: JSON.stringify({ status, latency_ms: Math.round(20 + Math.random() * 80) }),
    }),
};

// Ingest tokens are shown once by the API. Keeping them in this browser lets the
// "send beat" buttons work for services registered from here, and nowhere else.
export const tokens = {
  all() {
    try {
      return JSON.parse(localStorage.getItem(TOKENS_KEY)) || {};
    } catch {
      return {};
    }
  },
  get(id) {
    return this.all()[id];
  },
  set(id, token) {
    try {
      localStorage.setItem(TOKENS_KEY, JSON.stringify({ ...this.all(), [id]: token }));
    } catch {
      /* private mode: the token is still shown once on screen */
    }
  },
  forget(id) {
    const { [id]: _removed, ...rest } = this.all();
    try {
      localStorage.setItem(TOKENS_KEY, JSON.stringify(rest));
    } catch {
      /* ignore */
    }
  },
};
