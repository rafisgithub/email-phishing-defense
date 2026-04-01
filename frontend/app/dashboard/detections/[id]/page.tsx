"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getDetection, submitFeedback, type DetectionDetail } from "@/lib/api";

const VERDICT_STYLES: Record<string, string> = {
  safe: "bg-green-100 text-green-800 border-green-200",
  suspicious: "bg-yellow-100 text-yellow-800 border-yellow-200",
  phishing: "bg-red-100 text-red-800 border-red-200",
};

const SCORE_BG: Record<string, string> = {
  safe: "bg-green-500",
  suspicious: "bg-yellow-500",
  phishing: "bg-red-500",
};

export default function DetectionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<DetectionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [feedbackSent, setFeedbackSent] = useState(false);

  useEffect(() => {
    if (!id) return;
    getDetection(id)
      .then((res) => setData(res.data))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  const handleFeedback = async (type: string) => {
    if (!data) return;
    try {
      await submitFeedback(data.id, type);
      setFeedbackSent(true);
    } catch {
      /* ignore */
    }
  };

  if (loading)
    return (
      <div className="flex justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
      </div>
    );

  if (error || !data)
    return (
      <div className="text-center py-20 text-gray-500">
        <p>{error || "Not found"}</p>
        <Link href="/dashboard/detections" className="text-indigo-600 text-sm hover:underline mt-2 inline-block">
          Back to detections
        </Link>
      </div>
    );

  return (
    <div className="space-y-6 max-w-4xl">
      <Link href="/dashboard/detections" className="text-sm text-indigo-600 hover:underline">
        &larr; Back to detections
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold">{data.message.subject || "(No subject)"}</h1>
          <p className="text-sm text-gray-500 mt-1">
            From <span className="font-medium text-gray-700">{data.message.sender_email}</span>
            {data.message.sender_name && ` (${data.message.sender_name})`}
            &nbsp;&middot;&nbsp;{new Date(data.message.received_at).toLocaleString()}
          </p>
        </div>
        <div className={`px-4 py-2 rounded-xl border text-center ${VERDICT_STYLES[data.verdict]}`}>
          <p className="text-2xl font-bold">{data.score}</p>
          <p className="text-xs font-semibold uppercase">{data.verdict}</p>
        </div>
      </div>

      {/* Score bar */}
      <div className="bg-gray-200 rounded-full h-3 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${SCORE_BG[data.verdict]}`}
          style={{ width: `${data.score}%` }}
        />
      </div>

      {/* Reason Codes */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Detection Reasons</h2>
        {data.reason_codes.length === 0 ? (
          <p className="text-sm text-gray-400">No issues detected.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {data.reason_codes.map((code) => (
              <span key={code} className="px-3 py-1 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium">
                {code.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Evidence */}
      {Object.keys(data.evidence).length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Evidence</h2>
          <div className="space-y-3">
            {Object.entries(data.evidence).map(([key, val]) => (
              <div key={key}>
                <p className="text-xs font-semibold text-gray-500 uppercase">{key.replace(/_/g, " ")}</p>
                <pre className="mt-1 text-xs bg-gray-50 rounded-lg p-3 overflow-x-auto text-gray-700">
                  {JSON.stringify(val, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Links */}
      {data.links.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Extracted Links ({data.links.length})</h2>
          <div className="space-y-2">
            {data.links.map((link) => (
              <div key={link.id} className="flex items-start gap-2 text-sm">
                {link.is_suspicious && (
                  <span className="mt-0.5 w-4 h-4 rounded-full bg-red-100 text-red-600 flex items-center justify-center text-[10px] font-bold flex-shrink-0">!</span>
                )}
                <div className="min-w-0">
                  <p className="text-gray-700 break-all font-mono text-xs">{link.url}</p>
                  {link.display_text && link.display_text !== link.url && (
                    <p className="text-gray-400 text-xs">Display: {link.display_text}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions Taken */}
      {data.actions.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Actions Taken</h2>
          <div className="space-y-2">
            {data.actions.map((a) => (
              <div key={a.id} className="flex items-center gap-3 text-sm">
                <span className={`w-2 h-2 rounded-full ${a.status === "success" ? "bg-green-500" : a.status === "failed" ? "bg-red-500" : "bg-yellow-500"}`} />
                <span className="font-medium">{a.action_type.replace(/_/g, " ")}</span>
                <span className="text-gray-400">—</span>
                <span className={`text-xs ${a.status === "success" ? "text-green-600" : a.status === "failed" ? "text-red-600" : "text-yellow-600"}`}>
                  {a.status}
                </span>
                {a.executed_at && <span className="text-gray-400 text-xs">{new Date(a.executed_at).toLocaleString()}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Message body */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Email Body (Preview)</h2>
        <div className="text-sm text-gray-600 whitespace-pre-wrap max-h-60 overflow-y-auto bg-gray-50 rounded-lg p-4">
          {data.message.body_text || "(Empty body)"}
        </div>
      </div>

      {/* Feedback */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Feedback</h2>
        {feedbackSent ? (
          <p className="text-sm text-green-600">Thanks for your feedback!</p>
        ) : (
          <div className="flex gap-3">
            <button
              onClick={() => handleFeedback("confirmed")}
              className="px-4 py-2 bg-green-100 text-green-700 rounded-lg text-sm font-medium hover:bg-green-200"
            >
              Correct Detection
            </button>
            <button
              onClick={() => handleFeedback("false_positive")}
              className="px-4 py-2 bg-yellow-100 text-yellow-700 rounded-lg text-sm font-medium hover:bg-yellow-200"
            >
              False Positive
            </button>
            <button
              onClick={() => handleFeedback("false_negative")}
              className="px-4 py-2 bg-red-100 text-red-700 rounded-lg text-sm font-medium hover:bg-red-200"
            >
              Missed Threat
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
