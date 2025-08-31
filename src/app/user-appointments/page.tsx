"use client";
import { useEffect, useMemo, useState } from "react";
import { fetchHospitalUsers, fetchHospitalUserProfile, fetchUpcomingByHospital } from "@/lib/api";
import type { HospitalUsersResponse, HospitalUserProfile, UpcomingByHospitalResponse } from "@/lib/types";

export default function UserAppointmentsPage() {
  const [tab, setTab] = useState<"users"|"upcoming">("users");
  return (
    <main className="px-4 sm:px-6 lg:px-8 py-5 max-w-[1600px] mx-auto">
      <h1 className="text-xl md:text-2xl font-semibold mb-4 text-left">Lịch khám của người dùng</h1>
      <div className="flex flex-wrap gap-2 mb-5" role="tablist" aria-label="User appointments tabs">
        <button aria-selected={tab==="users"} role="tab" className={`px-3 md:px-4 py-1.5 rounded border text-sm md:text-base ${tab==="users"?"bg-gray-900 text-white":"bg-white"}`} onClick={()=>setTab("users")}>Người dùng theo bệnh viện</button>
        <button aria-selected={tab==="upcoming"} role="tab" className={`px-3 md:px-4 py-1.5 rounded border text-sm md:text-base ${tab==="upcoming"?"bg-gray-900 text-white":"bg-white"}`} onClick={()=>setTab("upcoming")}>Lịch khám sắp tới</button>
      </div>
      {tab === "users" ? <TabUsers /> : <TabUpcoming />}
    </main>
  );
}

function TabUsers() {
  const [data, setData] = useState<HospitalUsersResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<{ hospitalId: number; userId: string } | null>(null);
  const [profile, setProfile] = useState<HospitalUserProfile | null>(null);

  useEffect(()=>{ setError(null); fetchHospitalUsers().then(setData).catch(e=>setError(String(e))); },[]);
  useEffect(()=>{
    if (!selected) return; setProfile(null);
    fetchHospitalUserProfile(selected.hospitalId, selected.userId).then(setProfile).catch(()=>{});
  }, [selected]);

  return (
  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Left: hospital -> users */}
      <div className="lg:max-h-[70vh] overflow-y-auto pr-0 lg:pr-1">
        {!data && !error && <div className="text-sm text-gray-500">Đang tải...</div>}
        {error && <div className="text-sm text-red-600">Lỗi tải dữ liệu: {error}</div>}
        {data?.hospitals.map(h => (
          <div key={h.id} className="mb-6 border rounded-lg bg-white shadow-sm">
            <div className="px-4 py-2.5 font-medium border-b sticky top-0 bg-white z-10">{h.name}</div>
            {/* Header row for desktop */}
            {h.users.length>0 && (
              <div className="hidden lg:grid grid-cols-12 text-xs text-gray-500 px-4 py-2 border-b bg-gray-50">
                <div className="col-span-4">Người dùng</div>
                <div className="col-span-3">SĐT</div>
                <div className="col-span-3">CCCD</div>
                <div className="col-span-2 text-right">Số lần</div>
              </div>
            )}
            <div className="divide-y">
              {h.users.map(u => (
                <button key={u.id} className="w-full text-left px-4 py-2.5 hover:bg-gray-50 flex lg:grid lg:grid-cols-12 lg:items-center justify-between gap-2" onClick={()=>setSelected({ hospitalId: h.id, userId: u.id })}>
                  <div className="lg:col-span-4">
                    <div className="font-medium text-sm md:text-base">{u.name}</div>
                    <div className="text-xs text-gray-600 lg:hidden">{u.phone} {u.cccd ? `• CCCD ${u.cccd}`: ''}</div>
                  </div>
                  <div className="hidden lg:block lg:col-span-3 text-sm text-gray-700">{u.phone}</div>
                  <div className="hidden lg:block lg:col-span-3 text-sm text-gray-700">{u.cccd || '-'}</div>
                  <div className="lg:col-span-2 text-xs lg:text-sm text-gray-500 lg:text-right">{u.appointments} lần</div>
                </button>
              ))}
              {h.users.length===0 && (<div className="px-4 py-3 text-sm text-gray-500">Chưa có người dùng.</div>)}
            </div>
          </div>
        ))}
      </div>
      {/* Right: profile */}
      <div className="lg:max-h-[70vh] overflow-y-auto">
        <div className="border rounded-lg bg-white shadow-sm">
          <div className="px-4 py-2.5 font-medium border-b sticky top-0 bg-white z-10">Hồ sơ người dùng</div>
          {!selected && <div className="p-4 text-sm text-gray-500">Chọn một người dùng để xem hồ sơ.</div>}
          {selected && !profile && <div className="p-4 text-sm text-gray-500">Đang tải hồ sơ...</div>}
          {profile && (
            <div className="p-4 space-y-5">
              <div>
                <div className="font-medium text-base md:text-lg">{profile.user.name}</div>
                <div className="text-sm text-gray-600">SĐT: {profile.user.phone} {profile.user.cccd && `• CCCD ${profile.user.cccd}`} {profile.user.bhyt && `• BHYT ${profile.user.bhyt}`}</div>
                <div className="text-sm mt-0.5">Bệnh viện: {profile.hospital.name}</div>
              </div>
              <div>
                <div className="font-medium mb-2">Lịch đã đặt ở bệnh viện này</div>
                <div className="space-y-2">
                  {profile.appointments.map((a) => {
                    const c: any = a.content || {};
                    const hospital = c.hospital || profile.hospital.name;
                    const patientName = c.patient_name || profile.user.name;
                    const phone = c.phone_number || profile.user.phone;
                    const department = c.department_name || a.department;
                    const doctorName = c.doctor_name || a.doctorName;
                    const roomCode = c.room_code || undefined;
                    const whenIso = c.time_slot || a.when;
                    const symptoms: string[] = Array.isArray(c.symptoms) ? c.symptoms : [];
                    return (
                      <details key={a.id} className="border rounded overflow-hidden group">
                        <summary className="px-3 py-2 cursor-pointer text-sm bg-gray-50 flex items-center justify-between gap-3">
                          <span>{new Date(a.when).toLocaleString("vi-VN")} • {a.department} • BS. {a.doctorName} {typeof a.stt!=="undefined" && a.stt!==null ? `• STT ${a.stt}` : ''}</span>
                          <span className="text-xs text-gray-400">#{a.id}</span>
                        </summary>
                        <div className="p-3 bg-white">
                          <AppointmentSlip
                            hospital={hospital}
                            patientName={patientName}
                            phoneNumber={phone}
                            departmentName={department}
                            doctorName={doctorName}
                            roomCode={roomCode}
                            timeSlot={whenIso}
                            symptoms={symptoms}
                            stt={a.stt}
                          />
                        </div>
                      </details>
                    );
                  })}
                  {profile.appointments.length===0 && <div className="text-sm text-gray-500">Chưa có lịch nào.</div>}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TabUpcoming() {
  const [data, setData] = useState<UpcomingByHospitalResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(()=>{ setError(null); fetchUpcomingByHospital().then(setData).catch(e=>setError(String(e))); },[]);
  return (
    <div>
      {error && <div className="text-sm text-red-600">Lỗi tải dữ liệu: {error}</div>}
      {!data && !error && <div className="text-sm text-gray-500">Đang tải...</div>}
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {data?.hospitals.map(h => (
      <div key={h.id} className="border rounded-lg bg-white shadow-sm flex flex-col max-h-[70vh]">
            <div className="px-4 py-2.5 font-medium border-b sticky top-0 bg-white z-10">{h.name}</div>
            <div className="divide-y overflow-y-auto">
      {h.appointments.map(a => (
                <div key={a.id} className="px-4 py-2 md:py-3 text-sm md:text-[15px] flex items-start justify-between gap-3">
                  <div>
        <div className="font-medium">{new Date(a.when).toLocaleString("vi-VN")} {typeof a.stt!=="undefined" && a.stt!==null ? `• STT ${a.stt}` : ''}</div>
                    <div className="text-gray-600">{a.department} • BS. {a.doctorName}</div>
                    <div className="text-gray-500 text-xs md:text-sm">{a.user.name} • {a.user.phone}</div>
                  </div>
                  <div className="text-xs text-gray-400 whitespace-nowrap">#{a.id}</div>
                </div>
              ))}
              {h.appointments.length===0 && <div className="px-4 py-3 text-sm text-gray-500">Không có lịch sắp tới.</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// -------- Appointment Slip (Giấy hẹn khám) --------
function pad2(n: number) { return String(n).padStart(2, "0"); }
function formatVNDateParts(iso: string) {
  const d = new Date(iso);
  return { d: pad2(d.getDate()), m: pad2(d.getMonth()+1), y: d.getFullYear(), h: pad2(d.getHours()), min: pad2(d.getMinutes()) };
}

function AppointmentSlip({ hospital, patientName, phoneNumber, departmentName, doctorName, roomCode, timeSlot, symptoms, stt }: {
  hospital: string;
  patientName: string;
  phoneNumber?: string;
  departmentName?: string;
  doctorName?: string;
  roomCode?: string;
  timeSlot: string;
  symptoms?: string[];
  stt?: number | null;
}) {
  const t = formatVNDateParts(timeSlot);
  return (
    <div className="border rounded-md">
      <div className="px-4 py-3 border-b flex items-start justify-between gap-3">
        <div>
          <div className="font-semibold text-base">{hospital}</div>
        </div>
        {typeof stt!=="undefined" && stt!==null && (
          <div className="text-base text-gray-700">STT: <span className="font-bold">{stt}</span></div>
        )}
      </div>
      <div className="px-4 py-4 space-y-3 text-sm">
        <div className="font-bold text-center text-xl">GIẤY HẸN KHÁM</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Field label="Họ tên người bệnh" value={patientName} />
          <Field label="Số điện thoại" value={phoneNumber || "-"} />
          {departmentName && <Field label="Khoa" value={departmentName} />}
          {doctorName && <Field label="Bác sĩ" value={doctorName} />}
          {roomCode && <Field label="Phòng khám" value={roomCode} />}
          <Field label="Thời gian khám" value={`${t.h}:${t.min} ngày ${t.d}/${t.m}/${t.y}`} />
        </div>
        {symptoms && symptoms.length>0 && (
          <div>
            <div className="text-[13px] text-gray-600">Triệu chứng</div>
            <div className="mt-1 whitespace-pre-wrap border rounded px-2 py-1 bg-gray-50">{symptoms.join(", ")}</div>
          </div>
        )}
        <div className="flex items-start justify-between pt-4">
          <div className="text-xs text-gray-500 w-2/3">Lưu ý: Vui lòng đến trước giờ hẹn 10–15 phút để làm thủ tục.</div>
          <div className="text-xs text-gray-500 text-right">
            <div>Ngày {t.d} tháng {t.m} năm {t.y}</div>
          </div>
        </div>
      </div>
      <div className="px-4 py-2 border-t bg-gray-50 text-right">
        <button className="px-3 py-1.5 text-sm border rounded hover:bg-white" onClick={() => window.print()}>In phiếu</button>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value?: string }) {
  return (
    <div className="flex flex-col">
      <div className="text-[13px] text-gray-600">{label}</div>
      <div className="mt-1 border rounded px-2 py-1 bg-gray-50 min-h-[34px]">{value || "-"}</div>
    </div>
  );
}
