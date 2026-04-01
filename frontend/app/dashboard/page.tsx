"use client";

import { useEffect, useState } from "react";
import { getDashboard, type DashboardData, type DetectionSummary } from "@/lib/api";
import Link from "next/link";

const VERDICT_STYLES: Record<string, string> = {
  safe: "bg-green-100 text-green-800",
  suspicious: "bg-yellow-100 text-yellow-800",
  phishing: "bg-red-100 text-red-800",
};

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getDashboard()
      .then((res) => setData(res.data))
      .catch((e) => setError(e.message));
  }, []);

  if (error)
    return (
      <div className="text-center py-20 text-gray-500">
        <p className="text-lg font-medium">Unable to load dashboard</p>
        <p className="text-sm mt-1">{error}</p>
      </div>
    );

  if (!data)
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
      </div>
    );

  const cards = [
    { label: "Emails Scanned", value: data.total_emails_scanned, color: "text-gray-900" },
    { label: "Threats Detected", value: data.total_threats, color: "text-red-600" },
    { label: "Suspicious", value: data.total_suspicious, color: "text-yellow-600" },
    { label: "Phishing", value: data.total_phishing, color: "text-red-700" },
    { label: "Safe", value: data.total_safe, color: "text-green-600" },
    { label: "Mailboxes", value: data.total_mailboxes, color: "text-indigo-600" },
  ];

  const maxStat = Math.max(...data.daily_stats.map((d) => d.total), 1);

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {cards.map((c) => (
          <div key={c.label} className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{c.label}</p>
            <p className={`text-2xl font-bold mt-1 ${c.color}`}>{c.value.toLocaleString()}</p>
          </div>
        ))}
      </div>

      {/* 30-day chart */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Email Volume (Last 30 Days)</h2>
        <div className="flex items-end gap-[2px] h-32">
          {data.daily_stats.map((d) => (
            <div key={d.date} className="flex-1 flex flex-col items-center gap-[1px]" title={`${d.date}: ${d.total} total, ${d.threats} threats`}>
              <div
                className="w-full bg-red-400 rounded-t-sm"
                style={{ height: `${(d.threats / maxStat) * 100}%`, minHeight: d.threats ? 2 : 0 }}
              />
              <div
                className="w-full bg-indigo-400 rounded-t-sm"
                style={{ height: `${((d.total - d.threats) / maxStat) * 100}%`, minHeight: d.total - d.threats ? 2 : 0 }}
              />
            </div>
          ))}
        </div>
        <div className="flex justify-between text-[10px] text-gray-400 mt-1">
          <span>{data.daily_stats[0]?.date}</span>
          <span>{data.daily_stats[data.daily_stats.length - 1]?.date}</span>
        </div>
        <div className="flex gap-4 mt-2 text-xs text-gray-500">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-indigo-400" />Safe</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-400" />Threats</span>
        </div>
      </div>

      {/* Recent Detections */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">Recent Detections</h2>
          <Link href="/dashboard/detections" className="text-xs text-indigo-600 hover:underline">
            View all
          </Link>
        </div>
        {data.recent_detections.length === 0 ? (
          <p className="p-6 text-sm text-gray-400">No detections yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 uppercase tracking-wide border-b border-gray-100">
                  <th className="px-6 py-3">Sender</th>
                  <th className="px-6 py-3">Subject</th>
                  <th className="px-6 py-3">Score</th>
                  <th className="px-6 py-3">Verdict</th>
                  <th className="px-6 py-3">Date</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_detections.map((d: DetectionSummary) => (
                  <tr key={d.id} className="border-b border-gray-50 hover:bg-gray-50/50">
                    <td className="px-6 py-3 whitespace-nowrap">
                      <Link href={`/dashboard/detections/${d.id}`} className="text-indigo-600 hover:underline">
                        {d.sender_email}
                      </Link>
                    </td>
                    <td className="px-6 py-3 max-w-xs truncate">{d.subject}</td>
                    <td className="px-6 py-3 font-mono">{d.score}</td>
                    <td className="px-6 py-3">
                      <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${VERDICT_STYLES[d.verdict]}`}>
                        {d.verdict}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-gray-500 whitespace-nowrap">
                      {new Date(d.received_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
