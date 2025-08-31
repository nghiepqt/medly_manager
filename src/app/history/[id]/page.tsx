import { fetchBooking } from "../../../lib/api";

export default async function BookingDetail({ params }: { params: Promise<{ id: string }> }) {
  const p = await params;
  const data = await fetchBooking(String(p.id));
  const c = data.content || {} as any;
  return (
    <main className="p-4 max-w-xl mx-auto">
      <h1 className="text-2xl font-semibold mb-4">Phiếu hẹn khám</h1>
      <div className="border rounded p-4 space-y-2">
        <div><span className="font-medium">Bệnh viện:</span> {c.hospital || "-"}</div>
        <div><span className="font-medium">Bệnh nhân:</span> {c.patient_name || "-"} ({c.phone_number || "-"})</div>
        <div><span className="font-medium">Khoa:</span> {c.department_name || "-"}</div>
        <div><span className="font-medium">Bác sĩ:</span> {c.doctor_name || "-"}</div>
        <div><span className="font-medium">Phòng khám:</span> {c.room_code || "-"}</div>
        <div><span className="font-medium">Thời gian:</span> {new Date(c.time_slot || data.created_at).toLocaleString("vi-VN")}</div>
        <div>
          <span className="font-medium">Triệu chứng:</span>
          <ul className="list-disc ml-5">
            {(c.symptoms || []).map((s: string, i: number) => <li key={i}>{s}</li>)}
          </ul>
        </div>
      </div>
    </main>
  );
}
