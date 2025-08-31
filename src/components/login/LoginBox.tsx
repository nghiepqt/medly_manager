"use client";
import { useState } from "react";
import { createUserOrFetch, fetchUpcoming, fetchBookings } from "@/lib/api";
import { useUser } from "@/lib/userContext";

export default function LoginBox() {
  const { user, setUser } = useUser();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      const cleanPhone = phone.replace(/\D/g, "");
      const u = await createUserOrFetch({ name: name.trim(), phone: cleanPhone });
      setUser(u);
      // warm up caches by fetching user-scoped data (non-blocking)
      try { fetchUpcoming(u.id).catch(() => {}); } catch {}
      try { fetchBookingsByUser(u.id).catch(() => {}); } catch {}
    } catch (e: any) {
      setErr(e?.message || "Đăng nhập thất bại");
    } finally {
      setLoading(false);
    }
  };

  const logout = () => setUser(null);

  if (user) {
    return (
      <div className="p-4 rounded-lg border bg-gray-50 flex items-center justify-between">
        <div>
          <div className="text-sm text-gray-600">Đã đăng nhập</div>
          <div className="font-medium">{user.name} • {user.phone}</div>
        </div>
        <button className="text-sm text-red-600" onClick={logout}>Đăng xuất</button>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="p-4 rounded-lg border space-y-3">
      <div className="font-medium">Đăng nhập tạm thời</div>
      <div className="text-xs text-gray-500">Nhập tên và số điện thoại để tìm hoặc tạo tài khoản.</div>
      <div className="grid grid-cols-1 gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="h-10 rounded-md border px-3"
          placeholder="Tên của bạn"
          required
        />
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          className="h-10 rounded-md border px-3"
          placeholder="Số điện thoại"
          inputMode="tel"
          required
        />
      </div>
      {err && <div className="text-sm text-red-600">{err}</div>}
      <button disabled={loading} className="h-10 rounded-md bg-blue-600 text-white px-4">
        {loading ? "Đang kiểm tra..." : "Đăng nhập"}
      </button>
    </form>
  );
}

async function fetchBookingsByUser(userId: string) {
  const base = process.env.NEXT_PUBLIC_BACKEND_URL || "";
  const url = `${base}/api/bookings?userId=${encodeURIComponent(userId)}`;
  await fetch(url, { cache: "no-store" });
}
