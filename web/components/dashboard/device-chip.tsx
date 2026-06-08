"use client";

import { useEffect, useState } from "react";
import { Wifi, WifiOff } from "lucide-react";
import { api, type ApiDeviceStatus } from "@/lib/api";

export function DeviceChip() {
  const [status, setStatus] = useState<ApiDeviceStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const s = await api.deviceStatus();
        if (!cancelled) setStatus(s);
      } catch {
        if (!cancelled) setStatus({ connected: false, port: null, baud: 115200, description: "" });
      }
    }
    check();
    const id = setInterval(check, 5000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  if (!status) return null;

  return (
    <div
      className="flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px]"
      style={{
        borderColor: status.connected ? "rgba(0,255,170,0.3)" : "rgba(255,255,255,0.1)",
        color: status.connected ? "var(--accent)" : "var(--text-faint)",
      }}
      title={status.connected ? `${status.port} · ${status.baud} baud` : status.description}
    >
      {status.connected
        ? <Wifi size={10} strokeWidth={2} />
        : <WifiOff size={10} strokeWidth={2} />}
      {status.connected ? `Device · ${status.port}` : "No device"}
    </div>
  );
}
