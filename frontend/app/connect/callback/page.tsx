"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { m365Callback } from "@/lib/api";
import Link from "next/link";

export default function ConnectCallbackPage() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const tenant = searchParams.get("tenant");
    const consent = searchParams.get("admin_consent");

    if (!tenant) {
      setStatus("error");
      setMessage("Missing tenant ID in callback.");
      return;
    }

    m365Callback(tenant, consent === "True")
      .then((res) => {
        setStatus("success");
        setMessage(res.message || "Tenant connected successfully!");
      })
      .catch((e) => {
        setStatus("error");
        setMessage(e.message || "Failed to process callback.");
      });
  }, [searchParams]);

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <div className="bg-white rounded-xl border border-gray-200 p-8 max-w-md w-full text-center">
        {status === "loading" && (
          <>
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600 mx-auto mb-4" />
            <p className="text-gray-600">Connecting your Microsoft 365 tenant…</p>
          </>
        )}
        {status === "success" && (
          <>
            <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
            </div>
            <h2 className="text-lg font-bold text-gray-900 mb-2">Connected!</h2>
            <p className="text-gray-600 text-sm mb-6">{message}</p>
            <Link href="/dashboard/settings" className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">
              Go to Settings
            </Link>
          </>
        )}
        {status === "error" && (
          <>
            <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-red-600" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h2 className="text-lg font-bold text-gray-900 mb-2">Connection Failed</h2>
            <p className="text-gray-600 text-sm mb-6">{message}</p>
            <Link href="/dashboard/settings" className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-300">
              Back to Settings
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
