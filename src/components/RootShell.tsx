"use client";
import Link from "next/link";
import { useState } from "react";
import SideNav from "@/components/SideNav";
import { usePathname } from "next/navigation";

export default function RootShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const isDev = pathname?.startsWith("/dev");
  const isWidePage = isDev || pathname?.startsWith("/user-appointments") || pathname?.startsWith("/doctors-schedule");
  return (
    <div className="min-h-dvh w-full bg-white">
      {/* Top bar */}
  <header className="sticky top-0 z-40 flex items-center justify-between px-4 py-3 border-b bg-white text-black">
        <button
          aria-label="Toggle navigation"
          onClick={() => setOpen((v) => !v)}
          className="h-10 w-10 rounded-md border flex items-center justify-center active:scale-95"
        >
          <span className="sr-only">Menu</span>
          <div className="space-y-1.5">
            <div className="h-0.5 w-6 bg-black" />
            <div className="h-0.5 w-6 bg-black" />
            <div className="h-0.5 w-6 bg-black" />
          </div>
        </button>
        <Link href="/" className="text-base font-semibold">Medly</Link>
        <div className="w-10" />
      </header>

      <SideNav open={open} onClose={() => setOpen(false)} />

  <main className={isWidePage ? "w-full px-6 pb-10 text-black" : "mx-auto max-w-md px-4 pb-24 text-black"}>{children}</main>

      {/* Bottom safe area spacer */}
      <div className="h-4" />
    </div>
  );
}
