import type { AppointmentSuggestion, BookingSummary, PatientProfile, UpcomingAppointment, BookingOut, HospitalUsersResponse, HospitalUserProfile, UpcomingByHospitalResponse } from "./types";

// Build API URL: prefer relative /api (uses Next.js rewrites when NEXT_PUBLIC_BACKEND_URL is set),
// fallback to absolute http://localhost:8000 for local backend without rewrites
function apiUrl(path: string) {
  const backend = process.env.NEXT_PUBLIC_BACKEND_URL;
  const isServer = typeof window === "undefined";
  if (backend) {
    // On the server, use absolute backend URL; on the client, prefer Next rewrites via relative /api
    if (isServer) {
      return `${backend}${path.startsWith("/") ? path : "/" + path}`;
    }
    return `/api${path.startsWith("/") ? path.slice(1) : path}`.replace("/apiapi", "/api");
  }
  const base = "http://localhost:8000";
  return `${base}${path.startsWith("/") ? path : "/" + path}`;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function createUserOrFetch(payload: { phone: string; name: string }): Promise<PatientProfile> {
  const res = await fetch(apiUrl("/api/users"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return json(res);
}



export async function fetchUpcoming(userId?: string): Promise<UpcomingAppointment[]> {
  const url = userId ? apiUrl(`/api/upcoming?userId=${encodeURIComponent(userId)}`) : apiUrl("/api/upcoming");
  const res = await fetch(url);
  return json(res);
}

export async function fetchBookings(userId?: string): Promise<BookingOut[]> {
  const url = userId ? apiUrl(`/api/bookings?userId=${encodeURIComponent(userId)}`) : apiUrl("/api/bookings");
  const res = await fetch(url);
  return json(res);
}

export async function fetchBooking(id: string | number): Promise<BookingOut> {
  const res = await fetch(apiUrl(`/api/bookings/${id}`));
  return json(res);
}

export async function fetchHospitalUsers(hospitalId?: number | string): Promise<HospitalUsersResponse> {
  const url = hospitalId ? apiUrl(`/api/hospital-users?hospitalId=${encodeURIComponent(String(hospitalId))}`) : apiUrl(`/api/hospital-users`);
  const res = await fetch(url, { cache: "no-store" });
  return json(res);
}

export async function fetchHospitalUserProfile(hospitalId: number | string, userId: number | string): Promise<HospitalUserProfile> {
  const res = await fetch(apiUrl(`/api/hospital-user-profile?hospitalId=${encodeURIComponent(String(hospitalId))}&userId=${encodeURIComponent(String(userId))}`), { cache: "no-store" });
  return json(res);
}

export async function fetchUpcomingByHospital(): Promise<UpcomingByHospitalResponse> {
  const res = await fetch(apiUrl(`/api/hospitals/upcoming`), { cache: "no-store" });
  return json(res);
}
