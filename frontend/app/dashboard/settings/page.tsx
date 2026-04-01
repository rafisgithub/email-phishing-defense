"use client";

import { useEffect, useState } from "react";
import {
  getAllowList,
  getBlockList,
  addToAllowList,
  addToBlockList,
  connectM365,
  type ListEntry,
} from "@/lib/api";

export default function SettingsPage() {
  const [allowList, setAllowList] = useState<ListEntry[]>([]);
  const [blockList, setBlockList] = useState<ListEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const [newAllow, setNewAllow] = useState("");
  const [newBlock, setNewBlock] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    Promise.all([getAllowList(), getBlockList()])
      .then(([a, b]) => {
        setAllowList(a.data);
        setBlockList(b.data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleAddAllow = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAllow.trim()) return;
    try {
      const res = await addToAllowList(newAllow.trim());
      setAllowList((prev) => [res.data, ...prev]);
      setNewAllow("");
      setMsg("Domain added to allow list.");
    } catch (err: unknown) {
      setMsg(err instanceof Error ? err.message : "Failed to add domain");
    }
  };

  const handleAddBlock = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBlock.trim()) return;
    try {
      const res = await addToBlockList(newBlock.trim());
      setBlockList((prev) => [res.data, ...prev]);
      setNewBlock("");
      setMsg("Domain added to block list.");
    } catch (err: unknown) {
      setMsg(err instanceof Error ? err.message : "Failed to add domain");
    }
  };

  const handleConnectM365 = async () => {
    try {
      const callbackUrl = `${window.location.origin}/connect/callback`;
      const res = await connectM365(callbackUrl);
      window.location.href = res.data.consent_url;
    } catch (err: unknown) {
      setMsg(err instanceof Error ? err.message : "Failed to initiate connection");
    }
  };

  return (
    <div className="space-y-8 max-w-3xl">
      <h1 className="text-2xl font-bold">Settings</h1>

      {msg && (
        <div className="bg-indigo-50 text-indigo-700 rounded-lg px-4 py-2 text-sm">
          {msg}
          <button onClick={() => setMsg("")} className="ml-2 font-bold">&times;</button>
        </div>
      )}

      {/* Microsoft 365 Connection */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-2">Microsoft 365 Integration</h2>
        <p className="text-sm text-gray-500 mb-4">
          Connect your Microsoft 365 tenant to start monitoring mailboxes for phishing threats.
        </p>
        <button
          onClick={handleConnectM365}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 inline-flex items-center gap-2"
        >
          <svg className="w-5 h-5" viewBox="0 0 23 23" fill="none">
            <rect x="1" y="1" width="10" height="10" fill="#F25022" />
            <rect x="12" y="1" width="10" height="10" fill="#7FBA00" />
            <rect x="1" y="12" width="10" height="10" fill="#00A4EF" />
            <rect x="12" y="12" width="10" height="10" fill="#FFB900" />
          </svg>
          Connect Microsoft 365
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-600" /></div>
      ) : (
        <>
          {/* Allow List */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Allow List</h2>
            <p className="text-xs text-gray-500 mb-3">Domains on this list will bypass phishing detection.</p>
            <form onSubmit={handleAddAllow} className="flex gap-2 mb-4">
              <input
                type="text"
                placeholder="e.g. trusted-company.com"
                value={newAllow}
                onChange={(e) => setNewAllow(e.target.value)}
                className="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <button type="submit" className="px-4 py-1.5 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700">
                Add
              </button>
            </form>
            {allowList.length === 0 ? (
              <p className="text-sm text-gray-400">No allowed domains.</p>
            ) : (
              <div className="space-y-2">
                {allowList.map((e) => (
                  <div key={e.id} className="flex items-center justify-between bg-green-50 rounded-lg px-3 py-2">
                    <div>
                      <span className="text-sm font-medium text-green-800">{e.domain}</span>
                      {e.reason && <span className="text-xs text-green-600 ml-2">— {e.reason}</span>}
                    </div>
                    <span className="text-xs text-green-500">{new Date(e.created_at).toLocaleDateString()}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Block List */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Block List</h2>
            <p className="text-xs text-gray-500 mb-3">Domains on this list will always be flagged as phishing.</p>
            <form onSubmit={handleAddBlock} className="flex gap-2 mb-4">
              <input
                type="text"
                placeholder="e.g. malicious-domain.com"
                value={newBlock}
                onChange={(e) => setNewBlock(e.target.value)}
                className="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <button type="submit" className="px-4 py-1.5 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700">
                Add
              </button>
            </form>
            {blockList.length === 0 ? (
              <p className="text-sm text-gray-400">No blocked domains.</p>
            ) : (
              <div className="space-y-2">
                {blockList.map((e) => (
                  <div key={e.id} className="flex items-center justify-between bg-red-50 rounded-lg px-3 py-2">
                    <div>
                      <span className="text-sm font-medium text-red-800">{e.domain}</span>
                      {e.reason && <span className="text-xs text-red-600 ml-2">— {e.reason}</span>}
                    </div>
                    <span className="text-xs text-red-500">{new Date(e.created_at).toLocaleDateString()}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
