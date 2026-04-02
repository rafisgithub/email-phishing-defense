"use client";

import { useEffect, useState } from "react";
import { getMailboxes, getConnectionStatus, type MailboxItem, type ConnectionStatus } from "@/lib/api";
import Link from "next/link";

export default function MailboxesPage() {
  const [mailboxes, setMailboxes] = useState<MailboxItem[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [connStatus, setConnStatus] = useState<ConnectionStatus | null>(null);

  const load = (q?: string) => {
    setLoading(true);
    getMailboxes(q)
      .then((res) => setMailboxes(res.data))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    getConnectionStatus()
      .then((res) => setConnStatus(res.data))
      .catch(() => {});
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    load(search);
  };

  return (
    <div className="space-y-6">
      {/* Connection Status Banner */}
      {connStatus !== null && (
        <div
          className={`flex items-center gap-3 rounded-lg px-4 py-3 text-sm ${
            connStatus.connected
              ? "bg-green-50 border border-green-200 text-green-800"
              : connStatus.tenant_count > 0
              ? "bg-red-50 border border-red-200 text-red-800"
              : "bg-yellow-50 border border-yellow-200 text-yellow-800"
          }`}
        >
          <span
            className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
              connStatus.connected ? "bg-green-500 animate-pulse" : connStatus.tenant_count > 0 ? "bg-red-400" : "bg-yellow-400"
            }`}
          />
          <span className="flex-1">
            {connStatus.connected
              ? `Outlook connected — ${connStatus.tenant_count} tenant${connStatus.tenant_count !== 1 ? "s" : ""} active`
              : connStatus.tenant_count > 0
              ? "Outlook connection lost. Token may have expired."
              : "No Outlook account connected."}
          </span>
          {!connStatus.connected && (
            <Link
              href="/dashboard/settings"
              className="flex-shrink-0 px-3 py-1 rounded-md bg-white border text-xs font-medium hover:bg-gray-50"
            >
              {connStatus.tenant_count > 0 ? "Reconnect" : "Connect Now"}
            </Link>
          )}
        </div>
      )}

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Mailboxes</h1>
        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            type="text"
            placeholder="Search mailboxes…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <button type="submit" className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700">
            Search
          </button>
        </form>
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
        </div>
      ) : mailboxes.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
          No mailboxes found. Connect a Microsoft 365 tenant in Settings.
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 uppercase tracking-wide border-b border-gray-200 bg-gray-50">
                  <th className="px-6 py-3">Email</th>
                  <th className="px-6 py-3">Display Name</th>
                  <th className="px-6 py-3">Tenant</th>
                  <th className="px-6 py-3 text-center">Messages</th>
                  <th className="px-6 py-3 text-center">Threats</th>
                  <th className="px-6 py-3 text-center">VIP</th>
                  <th className="px-6 py-3">Last Checked</th>
                </tr>
              </thead>
              <tbody>
                {mailboxes.map((mb) => (
                  <tr key={mb.id} className="border-b border-gray-50 hover:bg-gray-50/50">
                    <td className="px-6 py-3 font-medium">{mb.email}</td>
                    <td className="px-6 py-3 text-gray-600">{mb.display_name || "—"}</td>
                    <td className="px-6 py-3 text-gray-600">{mb.tenant_name || "—"}</td>
                    <td className="px-6 py-3 text-center">{mb.message_count}</td>
                    <td className="px-6 py-3 text-center">
                      {mb.threat_count > 0 ? (
                        <span className="inline-block px-2 py-0.5 rounded-full bg-red-100 text-red-700 text-xs font-medium">
                          {mb.threat_count}
                        </span>
                      ) : (
                        <span className="text-gray-400">0</span>
                      )}
                    </td>
                    <td className="px-6 py-3 text-center">
                      {mb.is_vip ? (
                        <span className="inline-block px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 text-xs font-medium">VIP</span>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>
                    <td className="px-6 py-3 text-gray-500 text-xs">
                      {mb.last_checked_at ? new Date(mb.last_checked_at).toLocaleString() : "Never"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
