// Swap this stub for your real HTTP/WebSocket client later.
export async function sendCommand(cmd) {
  // Example HTTP call:
  // return fetch("/api/gimbal", {
  //   method: "POST",
  //   headers: { "Content-Type": "application/json" },
  //   body: JSON.stringify({ cmd }),
  // }).then(r => r.ok ? { ok: true } : { ok: false });

  // Demo latency:
  await new Promise((r) => setTimeout(r, 300));
  return { ok: true, cmd };
}
