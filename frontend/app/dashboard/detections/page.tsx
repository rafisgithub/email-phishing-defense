"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getDetections, type DetectionSummary, type PaginatedDetections } from "@/lib/api";

const VERDICT_STYLES: Record<string, string> = {
  safe: "bg-green-100 text-green-800",
  suspicious: "bg-yellow-100 text-yellow-800",
  phishing: "bg-red-100 text-red-800",
};

export default function DetectionsPage() {
  const [data, setData] = useState<PaginatedDetections | null>(null);
  const [verdict, setVerdict] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    const params: Record<string, string> = { page: String(page), per_page: "20" };
    if (verdict) params.verdict = verdict;
    if (search) params.search = search;

    getDetections(params)
      .then((res) => setData(res.data))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, verdict]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    load();
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Detections</h1>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            type="text"
            placeholder="Search subject or sender…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 w-64"
          />
          <button type="submit" className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700">
            Search
          </button>
        </form>

        <select
          value={verdict}
          onChange={(e) => { setVerdict(e.target.value); setPage(1); }}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="">All verdicts</option>
          <option value="safe">Safe</option>
          <option value="suspicious">Suspicious</option>
          <option value="phishing">Phishing</option>
        </select>
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
        </div>
      ) : !data || data.results.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
          No detections found.
        </div>
      ) : (
        <>
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-500 uppercase tracking-wide border-b border-gray-200 bg-gray-50">
                    <th className="px-6 py-3">Sender</th>
                    <th className="px-6 py-3">Subject</th>
                    <th className="px-6 py-3">Mailbox</th>
                    <th className="px-6 py-3">Score</th>
                    <th className="px-6 py-3">Verdict</th>
                    <th className="px-6 py-3">Reasons</th>
                    <th className="px-6 py-3">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((d: DetectionSummary) => (
                    <tr key={d.id} className="border-b border-gray-50 hover:bg-gray-50/50">
                      <td className="px-6 py-3 whitespace-nowrap">
                        <Link href={`/dashboard/detections/${d.id}`} className="text-indigo-600 hover:underline font-medium">
                          {d.sender_email}
                        </Link>
                        {d.sender_name && (
                          <p className="text-xs text-gray-400">{d.sender_name}</p>
                        )}
                      </td>
                      <td className="px-6 py-3 max-w-xs truncate">{d.subject}</td>
                      <td className="px-6 py-3 text-gray-500 text-xs">{d.mailbox_email}</td>
                      <td className="px-6 py-3 font-mono font-bold">{d.score}</td>
                      <td className="px-6 py-3">
                        <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${VERDICT_STYLES[d.verdict]}`}>
                          {d.verdict}
                        </span>
                      </td>
                      <td className="px-6 py-3">
                        <div className="flex flex-wrap gap-1">
                          {d.reason_codes.slice(0, 3).map((r) => (
                            <span key={r} className="inline-block px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-[10px]">
                              {r}
                            </span>
                          ))}
                          {d.reason_codes.length > 3 && (
                            <span className="text-[10px] text-gray-400">+{d.reason_codes.length - 3}</span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-3 text-gray-500 whitespace-nowrap text-xs">
                        {new Date(d.received_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between text-sm">
            <p className="text-gray-500">
              Page {data.page} of {data.total_pages} ({data.total} results)
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1.5 border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50"
              >
                Previous
              </button>
              <button
                onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                disabled={page >= data.total_pages}
                className="px-3 py-1.5 border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
