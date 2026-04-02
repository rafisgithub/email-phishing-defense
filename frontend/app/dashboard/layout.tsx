"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { signOut, getConnectionStatus, type ConnectionStatus } from "@/lib/api";

const NAV = [
  { label: "Dashboard", href: "/dashboard", icon: ChartIcon },
  { label: "Mailboxes", href: "/dashboard/mailboxes", icon: InboxIcon },
  { label: "Detections", href: "/dashboard/detections", icon: ShieldIcon },
  { label: "Settings", href: "/dashboard/settings", icon: CogIcon },
];

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);
  const [connStatus, setConnStatus] = useState<ConnectionStatus | null>(null);

  useEffect(() => {
    const fetchStatus = () => {
      getConnectionStatus()
        .then((res) => setConnStatus(res.data))
        .catch(() => {});
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleSignOut = async () => {
    setSigningOut(true);
    try {
      await signOut();
      router.push("/login");
    } catch {
      setSigningOut(false);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="hidden lg:flex lg:flex-col w-64 bg-white border-r border-gray-200">
        <div className="flex items-center gap-2 px-6 py-5 border-b border-gray-200">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
            <ShieldIcon className="w-5 h-5 text-white" />
          </div>
          <span className="text-lg font-bold text-gray-900">Email Phishing Defender</span>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map((item) => {
            const active =
              item.href === "/dashboard"
                ? pathname === "/dashboard"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  active
                    ? "bg-indigo-50 text-indigo-700"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`}
              >
                <item.icon
                  className={`w-5 h-5 ${active ? "text-indigo-600" : "text-gray-400"}`}
                />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="px-3 py-4 border-t border-gray-200 space-y-2">
          {/* Outlook Connection Status */}
          <Link
            href="/dashboard/settings"
            className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              connStatus === null
                ? "text-gray-400"
                : connStatus.connected
                ? "text-green-700 bg-green-50 hover:bg-green-100"
                : connStatus.error
                ? "text-amber-700 bg-amber-50 hover:bg-amber-100"
                : connStatus.tenant_count > 0
                ? "text-red-700 bg-red-50 hover:bg-red-100"
                : "text-gray-500 bg-gray-50 hover:bg-gray-100"
            }`}
          >
            <div className="relative">
              <OutlookIcon className="w-5 h-5" />
              <span
                className={`absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-white ${
                  connStatus === null
                    ? "bg-gray-300"
                    : connStatus.connected
                    ? "bg-green-500"
                    : connStatus.error
                    ? "bg-amber-400"
                    : "bg-red-400"
                }`}
              />
            </div>
            <div className="flex-1 min-w-0">
              <span className="block truncate">
                {connStatus === null
                  ? "Checking…"
                  : connStatus.connected
                  ? "Outlook Connected"
                  : connStatus.error
                  ? "Permission Issue"
                  : connStatus.tenant_count > 0
                  ? "Outlook Disconnected"
                  : "Outlook Not Connected"}
              </span>
              {connStatus && connStatus.tenant_count > 0 && (
                <span className="block text-xs opacity-75 truncate">
                  {connStatus.tenant_count} tenant{connStatus.tenant_count !== 1 ? "s" : ""}
                  {connStatus.error && !connStatus.connected ? " · Fix in Settings" : ""}
                </span>
              )}
            </div>
          </Link>

          <button
            onClick={handleSignOut}
            disabled={signingOut}
            className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-50 hover:text-gray-900 transition-colors disabled:opacity-50"
          >
            <LogOutIcon className="w-5 h-5 text-gray-400" />
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        {/* Mobile header */}
        <header className="lg:hidden flex items-center gap-2 px-4 py-3 bg-white border-b border-gray-200">
          <div className="w-7 h-7 rounded-md bg-indigo-600 flex items-center justify-center">
            <ShieldIcon className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-gray-900 flex-1">PhishGuard</span>
          {/* Mobile connection status dot */}
          <Link href="/dashboard/settings" className="flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium"
            style={{ background: connStatus?.connected ? "#dcfce7" : connStatus === null ? "#f3f4f6" : connStatus?.error ? "#fffbeb" : connStatus.tenant_count > 0 ? "#fef2f2" : "#f3f4f6" }}>
            <span className={`w-2 h-2 rounded-full ${connStatus === null ? "bg-gray-300" : connStatus.connected ? "bg-green-500" : connStatus.error ? "bg-amber-400" : connStatus.tenant_count > 0 ? "bg-red-400" : "bg-gray-300"}`} />
            <span className={connStatus?.connected ? "text-green-700" : connStatus?.error ? "text-amber-700" : connStatus?.tenant_count ? "text-red-700" : "text-gray-500"}>
              {connStatus === null ? "…" : connStatus.connected ? "Connected" : connStatus.error ? "Fix Perms" : connStatus.tenant_count > 0 ? "Disconnected" : "Not linked"}
            </span>
          </Link>
        </header>

        {/* Mobile nav */}
        <nav className="lg:hidden flex gap-1 px-4 py-2 bg-white border-b border-gray-200 overflow-x-auto">
          {NAV.map((item) => {
            const active =
              item.href === "/dashboard"
                ? pathname === "/dashboard"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium ${
                  active
                    ? "bg-indigo-100 text-indigo-700"
                    : "text-gray-500 hover:bg-gray-100"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="p-6 lg:p-8">{children}</div>
      </main>
    </div>
  );
}

/* ── Inline SVG icons ──────────────────────────────────────────────────── */

function ChartIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
    </svg>
  );
}

function InboxIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 13.5h3.86a2.25 2.25 0 012.012 1.244l.256.512a2.25 2.25 0 002.013 1.244h3.218a2.25 2.25 0 002.013-1.244l.256-.512a2.25 2.25 0 012.013-1.244h3.859m-17.5 0V6.75A2.25 2.25 0 014.5 4.5h15a2.25 2.25 0 012.25 2.25v6.75m-19.5 0v4.5A2.25 2.25 0 004.5 19.5h15a2.25 2.25 0 002.25-2.25v-4.5" />
    </svg>
  );
}

function ShieldIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
    </svg>
  );
}

function CogIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}

function LogOutIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
    </svg>
  );
}

function OutlookIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M24 7.387v10.478c0 .23-.08.424-.238.576-.158.154-.352.23-.58.23h-8.547v-6.959l1.6 1.229c.102.08.221.119.357.119s.255-.04.357-.12L24 7.387zm-.238-1.186c.08.064.156.14.203.238H15.41l5.59 4.478 3-2.4V6.2zm-9.127 12.47h8.73c.226 0 .42-.077.578-.23.16-.153.238-.348.238-.578v-.98l-3.6-2.76-1.57 1.26c-.1.08-.22.12-.36.12s-.26-.04-.36-.12l-1.57-1.26-2.086 1.6v2.948zM14.635 3.39L1.997 5.26v13.476l12.638 1.876V3.39zM8.39 16.078c-.63 0-1.18-.175-1.648-.526-.467-.35-.83-.83-1.087-1.44-.258-.608-.387-1.282-.387-2.022 0-.77.133-1.467.4-2.093.267-.627.638-1.12 1.114-1.48.476-.36 1.015-.54 1.616-.54.616 0 1.157.176 1.623.527.466.352.828.834 1.086 1.447.258.613.387 1.302.387 2.068 0 .752-.13 1.432-.39 2.04-.26.608-.628 1.088-1.103 1.44-.476.353-1.01.53-1.603.53l-.008.049zm.038-1.588c.352 0 .65-.275.895-.826.244-.55.367-1.28.367-2.19 0-.895-.12-1.612-.36-2.15-.24-.54-.542-.81-.903-.81-.37 0-.672.272-.908.818-.236.546-.354 1.27-.354 2.174 0 .92.118 1.652.354 2.198.236.524.54.786.91.786z" />
    </svg>
  );
}
