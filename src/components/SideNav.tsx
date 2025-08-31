"use client";
import Link from "next/link";

export default function SideNav({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <div className={`fixed inset-0 z-50 ${open ? "" : "pointer-events-none"}`}>
      {/* Backdrop */}
      <div
        aria-hidden
        onClick={onClose}
        className={`absolute inset-0 bg-black/30 transition-opacity ${open ? "opacity-100" : "opacity-0"}`}
      />
      {/* Panel */}
      <nav
        className={`absolute left-0 top-0 h-full w-[80%] max-w-[320px] bg-white shadow-xl transition-transform ${open ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="p-4 border-b flex items-center justify-between">
          <div className="text-lg font-semibold">Menu</div>
          <button onClick={onClose} className="h-9 px-3 border rounded-md">Close</button>
        </div>
        <ul className="p-2 text-base">
          <li>
            <Link className="block rounded-md px-3 py-3 active:bg-gray-100" href="/doctors-schedule" onClick={onClose}>
              Lịch của bác sĩ
            </Link>
          </li>
          <li>
            <Link className="block rounded-md px-3 py-3 active:bg-gray-100" href="/user-appointments" onClick={onClose}>
              Lịch khám của người dùng
            </Link>
          </li>
        </ul>
      </nav>
    </div>
  );
}
