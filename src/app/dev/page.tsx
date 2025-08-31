"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import interact from "interactjs";

type BusyBlock = { id?: number; start: string; end: string };
type DoctorRow = { id: number; name: string; busy: BusyBlock[]; windows?: WindowBlock[] };
type DepartmentGroup = { id: number; name: string; doctors: DoctorRow[] };
type HospitalGroup = { id: number; name: string; departments: DepartmentGroup[] };
type WindowBlock = { id?: number; start: string; end: string; kind: "available" | "ooo" };

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const devApi = (pathAndQuery: string) => `${API_BASE}${pathAndQuery.startsWith("/") ? pathAndQuery : "/" + pathAndQuery}`;

function localDateISO(d = new Date()) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export default function DevPage() {
  const [date, setDate] = useState(() => localDateISO());
  const [range, setRange] = useState<"day" | "week">("day");
  const [schedule, setSchedule] = useState<{ hospitals: HospitalGroup[]; days: string[] }>({ hospitals: [], days: [] });
  const [error, setError] = useState<string | null>(null);
  const [hospitals, setHospitals] = useState<{ id: number; name: string }[]>([]);
  const [selectedHospital, setSelectedHospital] = useState<string>("");
  const [selection, setSelection] = useState<{ kind: 'hospital'|'department'|'doctor'; id: number; name: string }|null>(null);
  const [selectedDoctorIds, setSelectedDoctorIds] = useState<number[]>([]);
  const [anchor, setAnchor] = useState<{ depId: number; docId: number; index: number } | null>(null);
  const [showAdjust, setShowAdjust] = useState(false);
  const [loading, setLoading] = useState(false); // foreground loads
  const [refreshing, setRefreshing] = useState(false); // background 5-min refresh toast
  const [refreshTick, setRefreshTick] = useState(0);
  const [prefillRange, setPrefillRange] = useState<{ startISO: string; endISO: string } | null>(null);

  // Full-day hours 00..23 for day view and time axis
  const hours = Array.from({ length: 24 }, (_, i) => i);

  const load = async (mode: 'initial' | 'param' | 'background' = 'param') => {
  setError(null);
  if (mode === 'background') setRefreshing(true); else setLoading(true);
      try {
        const url = new URL(`${API_BASE}/api/dev/schedule`);
        url.searchParams.set("date_str", date);
        url.searchParams.set("range", range);
        if (selectedHospital) url.searchParams.set("hospital_id", selectedHospital);
        const res = await fetch(url.toString());
        if (!res.ok) {
          const t = await res.text().catch(() => "");
          throw new Error(t || `HTTP ${res.status}`);
        }
        const j = await res.json().catch(() => ({}));
        const hospitalsData = Array.isArray(j?.hospitals) ? j.hospitals : [];
        const dlist = Array.isArray(j?.days) ? j.days : [];
  const sched = { hospitals: hospitalsData, days: dlist };
        setSchedule(sched);
        setHospitals((sched.hospitals || []).map((h: any) => ({ id: h.id, name: h.name })));
  setRefreshTick(t => t + 1); // force re-mount of grids so blocks render reliably
      } catch (e: any) {
    setSchedule({ hospitals: [], days: [] });
        setError(e?.message || String(e));
      } finally {
        if (mode === 'background') setRefreshing(false); else setLoading(false);
      }
  };

  useEffect(() => { load('param'); }, [date, range, selectedHospital]);

  // Background refresh every 5 minutes with a small toast
  useEffect(() => {
    const id = setInterval(() => { load('background'); }, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, [date, range, selectedHospital]);

  return (
  <div className="py-6 max-w-[1400px] mx-auto relative">
      <h1 className="text-2xl font-bold">Quản lý lịch</h1>
      <div className="mt-3 flex items-center gap-3 flex-wrap">
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="border rounded-md px-3 py-2" />
        <select value={range} onChange={(e) => setRange(e.target.value as any)} className="border rounded-md px-3 py-2">
          <option value="day">Theo ngày</option>
          <option value="week">Theo tuần</option>
        </select>
        <select value={selectedHospital} onChange={(e) => setSelectedHospital(e.target.value)} className="border rounded-md px-3 py-2">
          <option value="">Tất cả bệnh viện</option>
          {hospitals.map(h => (
            <option key={h.id} value={String(h.id)}>{h.name}</option>
          ))}
        </select>
        <div className="flex items-center gap-3 text-xs text-gray-600">
          <span className="inline-flex items-center gap-1"><span className="inline-block h-2.5 w-4 rounded bg-green-200 border border-green-400" /> Rảnh</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block h-2.5 w-4 rounded bg-red-200 border border-red-400" /> Bận</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block h-2.5 w-4 rounded bg-gray-200 border border-gray-400" /> Nghỉ</span>
        </div>
  {/* Inline controls removed in favor of fixed floating action bar */}
      </div>
      {error && (
        <div className="mt-3 text-sm text-red-600">Không tải được lịch: {error}</div>
      )}
      {loading && (
        <div className="spinner-overlay"><div className="spinner lg" /></div>
      )}
      {refreshing && (
        <div className="fixed bottom-4 right-4 z-50">
          <div className="flex items-center gap-3 bg-white border rounded shadow-md px-3 py-2">
            <div className="spinner" />
            <div className="text-sm text-gray-700">Đang làm mới dữ liệu…</div>
          </div>
        </div>
      )}

      {/* Fixed action bar for selected scope: always visible at top-right above overlays */}
      {range === 'day' && (selection || selectedDoctorIds.length > 0) && (
        <div className="fixed top-4 right-4 z-50 flex items-center gap-2">
          <button
            className="bg-blue-600 text-white text-sm px-3 py-2 rounded hover:bg-blue-700 shadow"
            onClick={() => setShowAdjust(true)}
            title={selectedDoctorIds.length > 1 ? `Điều chỉnh: ${selectedDoctorIds.length} bác sĩ` : (selection ? `Điều chỉnh: ${selection.name}` : 'Điều chỉnh')}
          >
            Điều chỉnh
          </button>
          <button
            className="bg-red-600 text-white text-sm px-3 py-2 rounded hover:bg-red-700 shadow"
            onClick={async () => {
              const dayStr = (schedule.days && schedule.days[0]) || date;
              if (selectedDoctorIds.length > 0) {
                const ok = confirm(`Xóa toàn bộ khung giờ của ${selectedDoctorIds.length} bác sĩ trong ngày ${dayStr}?`);
                if (!ok) return;
                try {
                  const results = await Promise.allSettled(selectedDoctorIds.map(async (id) => {
                    const res = await fetch(devApi('/api/dev/windows/bulk-adjust'), {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ scopeKind: 'doctor', scopeId: id, dateStart: dayStr, dateEnd: dayStr, available: [], ooo: [], overwrite: true })
                    });
                    if (!res.ok) throw new Error(await res.text());
                    return res.json().catch(() => ({}));
                  }));
                  const failed = results.filter(r => r.status === 'rejected');
                  if (failed.length) alert(`Một số thao tác thất bại: ${failed.length}/${results.length}`);
                  load('param');
                } catch (e: any) {
                  alert(`Xóa khung giờ thất bại: ${e?.message || e}`);
                }
                return;
              }
              if (!selection) return;
              const ok = confirm(`Xóa toàn bộ khung giờ của \"${selection.name}\" trong ngày ${dayStr}?`);
              if (!ok) return;
              try {
                const res = await fetch(devApi('/api/dev/windows/bulk-adjust'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scopeKind: selection.kind, scopeId: selection.id, dateStart: dayStr, dateEnd: dayStr, available: [], ooo: [], overwrite: true }) });
                if (!res.ok) throw new Error(await res.text());
                await res.json().catch(() => ({}));
                load('param');
              } catch (e: any) { alert(`Xóa khung giờ thất bại: ${e?.message || e}`); }
            }}
            title={selectedDoctorIds.length > 1 ? `Xóa khung giờ đã lưu: ${selectedDoctorIds.length} bác sĩ` : (selection ? `Xóa khung giờ đã lưu: ${selection.name}` : 'Xóa khung giờ')}
          >
            Xóa
          </button>
        </div>
      )}

      {range === "day" ? (
        (schedule.hospitals || []).map((h) => {
          const effDays = (schedule.days && schedule.days.length > 0) ? schedule.days : [date];
          return (
            <HospitalGrid key={`${h.id}-${refreshTick}`} hospital={h} hours={hours} days={effDays} onSelect={setSelection} selection={selection}
              selectedDoctorIds={selectedDoctorIds}
              onDoctorClick={(ev, doc, dep, hosp, index) => {
                const isCtrl = ev.ctrlKey || ev.metaKey;
                const isShift = ev.shiftKey;
                if (isShift && anchor && anchor.depId === dep.id) {
                  const a = Math.min(anchor.index, index);
                  const b = Math.max(anchor.index, index);
                  const ids = dep.doctors.slice(a, b + 1).map(d => d.id);
                  setSelectedDoctorIds(ids);
                  // keep anchor
                } else if (isCtrl) {
                  setSelectedDoctorIds(prev => {
                    const set = new Set(prev);
                    if (set.has(doc.id)) set.delete(doc.id); else set.add(doc.id);
                    return Array.from(set);
                  });
                  setAnchor({ depId: dep.id, docId: doc.id, index });
                } else {
                  setSelectedDoctorIds([doc.id]);
                  setAnchor({ depId: dep.id, docId: doc.id, index });
                }
                setSelection({ kind: 'doctor', id: doc.id, name: `${hosp.name} • ${dep.name} • ${doc.name}` });
              }}
              onSpanSelect={(doc, dep, hosp, startISO, endISO) => {
                setSelection({ kind: 'doctor', id: doc.id, name: `${hosp.name} • ${dep.name} • ${doc.name}` });
                setSelectedDoctorIds([doc.id]);
                setPrefillRange({ startISO, endISO });
                setShowAdjust(true);
              }}
            />
          );
        })
      ) : (
        (schedule.hospitals || []).map((h) => (
          <WeekHospitalGrid key={`${h.id}-${refreshTick}`} hospital={h} days={schedule.days} />
        ))
      )}

      {showAdjust && range === 'day' && (selection || selectedDoctorIds.length > 0) && (
        <AdjustModal selection={selection || undefined} multipleDoctorIds={selectedDoctorIds} day={(schedule.days && schedule.days[0]) || date} initialRange={prefillRange || undefined} onClose={() => { setShowAdjust(false); setPrefillRange(null); }} onSaved={() => { setShowAdjust(false); setPrefillRange(null); load('param'); }} />
      )}
    </div>
  );
}

function HospitalGrid({ hospital, hours, days, onSelect, selection, onSpanSelect, selectedDoctorIds, onDoctorClick }: { hospital: HospitalGroup; hours: number[]; days: string[]; onSelect: (s: {kind:'hospital'|'department'|'doctor'; id:number; name:string} | null)=>void; selection: {kind:'hospital'|'department'|'doctor'; id:number; name:string} | null; onSpanSelect?: (doc: DoctorRow, dep: DepartmentGroup, hosp: HospitalGroup, startISO: string, endISO: string) => void; selectedDoctorIds?: number[]; onDoctorClick?: (ev: MouseEvent | any, doc: DoctorRow, dep: DepartmentGroup, hosp: HospitalGroup, index: number) => void }) {
  const selected = selection?.kind==='hospital' && selection.id===hospital.id;
  return (
    <div className="mt-6">
      <h2 className="font-semibold text-lg inline-flex items-center gap-2 cursor-pointer group" onClick={() => onSelect(selected ? null : { kind: 'hospital', id: hospital.id, name: hospital.name })}>
        <span className={`select-indicator lg ${selected ? 'selected' : ''}`} />
        <span>{hospital.name}</span>
      </h2>
      {hospital.departments.map((dep) => (
  <DepartmentGrid key={dep.id} department={dep} hours={hours} days={days} onSelect={onSelect} selection={selection} hospital={hospital} onSpanSelect={onSpanSelect} selectedDoctorIds={selectedDoctorIds} onDoctorClick={onDoctorClick} />
      ))}
    </div>
  );
}

function DepartmentGrid({ department, hours, days, onSelect, selection, hospital, onSpanSelect, selectedDoctorIds, onDoctorClick }: { department: DepartmentGroup; hours: number[]; days: string[]; onSelect: (s: {kind:'hospital'|'department'|'doctor'; id:number; name:string} | null)=>void; selection: {kind:'hospital'|'department'|'doctor'; id:number; name:string} | null; hospital: HospitalGroup; onSpanSelect?: (doc: DoctorRow, dep: DepartmentGroup, hosp: HospitalGroup, startISO: string, endISO: string) => void; selectedDoctorIds?: number[]; onDoctorClick?: (ev: MouseEvent | any, doc: DoctorRow, dep: DepartmentGroup, hosp: HospitalGroup, index: number) => void }) {
  const cellWidth = 72; // keep in sync with DoctorRowGrid
  const colCount = hours.length;
  const selected = selection?.kind==='department' && selection.id===department.id;
  return (
    <div className="mt-4">
      <h3 className="font-medium inline-flex items-center gap-2 cursor-pointer group" onClick={() => onSelect(selected ? null : { kind: 'department', id: department.id, name: `${hospital.name} • ${department.name}` })}>
        <span className={`select-indicator ${selected ? 'selected' : ''}`} />
        <span>{department.name}</span>
      </h3>
      <div className="mt-2 overflow-x-auto">
          <div className="border rounded-lg" style={{ minWidth: `${220 + colCount * cellWidth}px` }}>
          <div className="grid" style={{ gridTemplateColumns: `220px 1fr` }}>
            <div className="p-2 text-xs text-gray-500 border-b">Bác sĩ</div>
            <div className="border-b">
                <div className="grid" style={{ gridTemplateColumns: `repeat(${colCount}, ${cellWidth}px)`, width: `${colCount * cellWidth}px` }}>
                  {hours.map((h) => (
                    <div key={`h-${h}`} className="py-2 px-0 text-[10px] text-gray-500 text-left">
                      {String(h).padStart(2, "0")}:00
                    </div>
                  ))}
                </div>
            </div>
          </div>
          {department.doctors.map((doc, idx) => (
            <DoctorRowGrid key={doc.id} doc={doc as any} hours={hours} days={days} onSelect={onSelect} selection={selection} department={department} hospital={hospital} onSpanSelect={onSpanSelect} isSelected={selectedDoctorIds?.includes(doc.id) || false} onClickLabel={(ev) => onDoctorClick && onDoctorClick(ev, doc, department, hospital, idx)} />
          ))}
        </div>
      </div>
    </div>
  );
}

function DoctorRowGrid({ doc, hours, days, onSelect, selection, department, hospital, onSpanSelect, isSelected, onClickLabel }: { doc: DoctorRow & { windows?: WindowBlock[] }; hours: number[]; days: string[]; onSelect: (s: {kind:'hospital'|'department'|'doctor'; id:number; name:string} | null)=>void; selection: {kind:'hospital'|'department'|'doctor'; id:number; name:string} | null; department: DepartmentGroup; hospital: HospitalGroup; onSpanSelect?: (doc: DoctorRow, dep: DepartmentGroup, hosp: HospitalGroup, startISO: string, endISO: string) => void; isSelected?: boolean; onClickLabel?: (ev: MouseEvent | any) => void }) {
  const rowRef = useRef<HTMLDivElement>(null);
  // dimensions
  const colCount = hours.length; // day view columns across 24 hours
  const cellWidth = 72; // px per 1-hour column
  const cellHeight = 36; // row height
  const [dragSel, setDragSel] = useState<{ startX: number; endX: number; active: boolean } | null>(null);
  const dragRef = useRef<{ startX: number; endX: number; active: boolean } | null>(null);

  useEffect(() => {
    if (!rowRef.current) return;
    const nodes = Array.from(rowRef.current.querySelectorAll('.avail-block, .ooo-block')) as HTMLElement[];
    const instances = nodes.map((node) => {
      const inst = interact(node);
      inst
        .draggable({
          listeners: {
            move(event: any) {
              const target = event.target as HTMLDivElement;
              const x = (parseFloat(target.getAttribute("data-x") || "0") + event.dx);
              target.style.transform = `translate(${x}px, 0px)`;
              target.setAttribute("data-x", String(x));
            },
            end: async (event: any) => {
              await persistBlock(event.target as HTMLDivElement);
            },
          },
          modifiers: [
            interact.modifiers.snap({
              targets: [interact.snappers.grid({ x: cellWidth / 4, y: cellHeight })],
              range: Infinity,
              relativePoints: [{ x: 0, y: 0 }],
            }),
          ],
          inertia: true,
        })
        .resizable({
          edges: { left: true, right: true },
          listeners: {
            move(event: any) {
              const target = event.target as HTMLDivElement;
              let x = parseFloat(target.getAttribute("data-x") || "0");
              target.style.width = `${event.rect.width}px`;
              x += event.deltaRect.left;
              target.style.transform = `translate(${x}px, 0px)`;
              target.setAttribute("data-x", String(x));
            },
            end: async (event: any) => {
              await persistBlock(event.target as HTMLDivElement);
            },
          },
          modifiers: [
            interact.modifiers.snapSize({ targets: [interact.snappers.grid({ x: cellWidth / 4, y: cellHeight })] }),
          ],
          inertia: true,
        });
      return inst;
    });
    return () => { instances.forEach((i) => i.unset()); };
  }, [cellWidth, cellHeight, doc.id, (doc.windows || []).length]);

  const persistBlock = async (el: HTMLDivElement) => {
  // Safety: ensure the block belongs to this row/doctor
  if (rowRef.current && !rowRef.current.contains(el)) {
    return;
  }
  const elDocAttr = el.getAttribute("data-doc");
  if (elDocAttr && Number(elDocAttr) !== doc.id) {
    // Ignore cross-row events; reset transient transform
    el.style.transform = "";
    el.setAttribute("data-x", "0");
    return;
  }
  // Use bounding rect relative to the cells container so transforms are accounted
  const container = rowRef.current?.querySelector('.cells') as HTMLDivElement | null;
  if (!container) return;
  const elRect = el.getBoundingClientRect();
  const cRect = container.getBoundingClientRect();
  let leftPx = (elRect.left - cRect.left) + container.scrollLeft;
  let widthPx = elRect.width;
  // clamp within day width
  const maxWidth = colCount * cellWidth;
  leftPx = Math.max(0, Math.min(maxWidth, leftPx));
  widthPx = Math.max(1, Math.min(maxWidth - leftPx, widthPx));
  // boundary-based mapping; compute in 15-min quarters
  const pxPer15 = cellWidth / 4;
  let startQuarters = Math.round(leftPx / pxPer15);
  if (startQuarters < 0) startQuarters = 0;
  let durationQuarters = Math.max(1, Math.round(widthPx / pxPer15));
    // clamp end within 24h (in quarters)
    const maxQuarters = 24 * 4;
    if (startQuarters + durationQuarters > maxQuarters) {
      startQuarters = Math.max(0, maxQuarters - durationQuarters);
    }
    const startMins = startQuarters * 15;
    const endMins = Math.min(24 * 60, startMins + durationQuarters * 15);
    const day = days[0];
    const start = new Date(`${day}T00:00:00`);
    start.setMinutes(start.getMinutes() + startMins);
    const end = new Date(`${day}T00:00:00`);
    end.setMinutes(end.getMinutes() + endMins);
    const kind = el.classList.contains("avail-block") ? "available" : "ooo";
    const existingId = el.getAttribute("data-id");
  const createRes = await fetch(devApi(`/api/dev/windows`), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
     body: JSON.stringify({ doctorId: doc.id, start: toLocalNaiveISO(start), end: toLocalNaiveISO(end), kind }),
    });
    if (!createRes.ok) {
      const t = await createRes.text();
      alert(`Lưu block lỗi: ${t}`);
      // revert visual
      el.style.transform = "";
      el.setAttribute("data-x", "0");
      return;
    }
    const j = await createRes.json();
    // If we had an existing window id, delete it after successful create
    if (existingId) {
      const del = await fetch(devApi(`/api/dev/windows/${existingId}`), { method: "DELETE" });
      if (!del.ok) {
        // Not fatal for the user flow; log and continue
        console.warn('Failed to delete old window', await del.text());
      }
    }
    el.setAttribute("data-id", String(j.id));
  // Reset transform and sync absolute positioning to avoid drift in subsequent drags
  el.style.transform = "";
  el.setAttribute("data-x", "0");
  el.style.left = `${(startMins / 60) * cellWidth}px`;
  el.style.width = `${((endMins - startMins) / 60) * cellWidth}px`;
  };

  const createBlockAt = async (quarterIndex: number, kind: "available" | "ooo", durationMinutes = 60) => {
    const day = days[0];
    const start = new Date(`${day}T00:00:00`);
    start.setMinutes(quarterIndex * 15);
    const end = new Date(start);
    end.setMinutes(start.getMinutes() + durationMinutes);
    const res = await fetch(devApi(`/api/dev/windows`), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
         body: JSON.stringify({ doctorId: doc.id, start: toLocalNaiveISO(start), end: toLocalNaiveISO(end), kind }),
    });
    if (!res.ok) {
      const t = await res.text();
      alert(`Tạo block lỗi: ${t}`);
      return;
    }
    const j = await res.json();
    // optimistic UI: add a block element
    const container = rowRef.current?.querySelector(".cells") as HTMLDivElement;
    if (!container) return;
    const block = document.createElement("div");
    block.className = `${kind === "available" ? "avail-block bg-green-200 border-green-300" : "ooo-block bg-gray-200 border-gray-300"} absolute top-1 bottom-1 border rounded`;
  const left = ((quarterIndex * 15) / 60) * cellWidth;
  block.style.left = `${left}px`;
  block.style.width = `${(durationMinutes / 60) * cellWidth}px`;
    block.setAttribute("data-x", "0");
    block.setAttribute("data-id", String(j.id));
  block.setAttribute("data-doc", String(doc.id));
    container.appendChild(block);
    // bind interact handlers to the new block only in this row
    const inst = interact(block);
    inst
      .draggable({
        listeners: {
          move(event: any) {
            const target = event.target as HTMLDivElement;
            const x = (parseFloat(target.getAttribute("data-x") || "0") + event.dx);
            target.style.transform = `translate(${x}px, 0px)`;
            target.setAttribute("data-x", String(x));
          },
          end: async (event: any) => {
            await persistBlock(event.target as HTMLDivElement);
          },
        },
        modifiers: [
          interact.modifiers.snap({ targets: [interact.snappers.grid({ x: cellWidth / 4, y: cellHeight })], range: Infinity, relativePoints: [{ x: 0, y: 0 }] }),
        ],
        inertia: true,
      })
      .resizable({
        edges: { left: true, right: true },
        listeners: {
          move(event: any) {
            const target = event.target as HTMLDivElement;
            let x = parseFloat(target.getAttribute("data-x") || "0");
            target.style.width = `${event.rect.width}px`;
            x += event.deltaRect.left;
            target.style.transform = `translate(${x}px, 0px)`;
            target.setAttribute("data-x", String(x));
          },
          end: async (event: any) => {
            await persistBlock(event.target as HTMLDivElement);
          },
        },
        modifiers: [
          interact.modifiers.snapSize({ targets: [interact.snappers.grid({ x: cellWidth / 4, y: cellHeight })] }),
        ],
        inertia: true,
      });
  };

  return (
    <div className="grid items-stretch" style={{ gridTemplateColumns: `220px 1fr` }}>
      <div className="p-2 border-r text-sm">
        {(() => {
          const selDoctor = selection?.kind==='doctor' && selection.id===doc.id;
          const selDept = selection?.kind==='department' && selection.id===department.id;
          const selHosp = selection?.kind==='hospital' && selection.id===hospital.id;
          const selected = selDoctor || selDept || selHosp;
          return (
            <div className="font-medium inline-flex items-center gap-2 cursor-pointer group" onClick={(ev) => { onClickLabel ? onClickLabel(ev) : onSelect(selDoctor ? null : { kind: 'doctor', id: doc.id, name: `${hospital.name} • ${department.name} • ${doc.name}` }); }}>
              <span className={`select-indicator sm ${(selected || isSelected) ? 'selected' : ''}`} />
              <span>{doc.name}</span>
            </div>
          );
        })()}
      </div>
      <div className="relative" style={{ height: `${cellHeight}px` }} ref={rowRef}>
        <div
          className="cells relative border-t"
          style={{ width: `${colCount * cellWidth}px`, height: `${cellHeight}px` }}
          onDoubleClick={(e) => {
            const container = e.currentTarget as HTMLDivElement;
            const rect = container.getBoundingClientRect();
            const x = (e.clientX - rect.left) + container.scrollLeft;
      // boundary-based, 15-min granularity
      const q = Math.max(0, Math.min(24 * 4 - 4, Math.round(x / (cellWidth / 4))));
            // Default to available: 60 minutes
            createBlockAt(q, "available", 60);
          }}
          onMouseDown={(e) => {
            if (e.button !== 0) return;
            const target = e.target as HTMLElement;
            if (target.closest('.avail-block, .ooo-block, .busy-block')) return; // ignore drags starting on blocks
            const container = e.currentTarget as HTMLDivElement;
            const rect = container.getBoundingClientRect();
            const x = (e.clientX - rect.left) + container.scrollLeft;
            const width = colCount * cellWidth;
            const clampedX = Math.max(0, Math.min(width, x));
            const init = { startX: clampedX, endX: clampedX, active: true };
            dragRef.current = init;
            setDragSel(init);
            const onMove = (ev: MouseEvent) => {
              const nx = Math.max(0, Math.min(width, (ev.clientX - rect.left) + container.scrollLeft));
              dragRef.current = dragRef.current ? { ...dragRef.current, endX: nx } : { startX: nx, endX: nx, active: true };
              setDragSel((s) => (s ? { ...s, endX: nx } : s));
            };
            const onUp = (ev: MouseEvent) => {
              window.removeEventListener('mousemove', onMove);
              window.removeEventListener('mouseup', onUp);
              const s = dragRef.current;
              dragRef.current = null;
              setDragSel(null);
              if (s) {
                const minX = Math.max(0, Math.min(s.startX, s.endX));
                const maxX = Math.max(0, Math.max(s.startX, s.endX));
                const pxPer15 = cellWidth / 4;
                let startQ = Math.round(minX / pxPer15);
                let endQ = Math.round(maxX / pxPer15);
                if (endQ <= startQ) endQ = startQ + 1; // at least 15 minutes
                const maxQ = 24 * 4;
                startQ = Math.max(0, Math.min(maxQ - 1, startQ));
                endQ = Math.max(1, Math.min(maxQ, endQ));
                const day = days[0];
                const start = new Date(`${day}T00:00:00`);
                start.setMinutes(startQ * 15);
                const end = new Date(`${day}T00:00:00`);
                end.setMinutes(endQ * 15);
                if (onSpanSelect) {
                  // Defer parent updates to avoid setState during child render warning
                  setTimeout(() => onSpanSelect(doc, department, hospital, start.toISOString(), end.toISOString()), 0);
                }
              }
            };
            window.addEventListener('mousemove', onMove);
            window.addEventListener('mouseup', onUp);
          }}
        >
          {/* hour vertical guides at hour boundaries under the labels */}
          {hours.map((_, i) => (
            <div key={`vl-${i}`} className="absolute top-0 bottom-0" style={{ left: `${i * cellWidth}px`, width: '1px', backgroundColor: '#e5e7eb' }} />
          ))}
          {/* day boundaries at 00:00 and 24:00 */}
          <div className="absolute top-0 bottom-0" style={{ left: 0, width: '1px', backgroundColor: '#cbd5e1' }} />
          <div className="absolute top-0 bottom-0" style={{ left: `${colCount * cellWidth}px`, width: '1px', backgroundColor: '#cbd5e1' }} />
          {/* schedule windows: available (green), out of office (gray) — day view clamped to 00:00–23:59 */}
          {(doc.windows || []).map((w, idx) => {
            const s = new Date(w.start);
            const e = new Date(w.end);
            const day = days[0];
            const dayStart = new Date(`${day}T00:00:00`);
            const dayEnd = new Date(`${day}T23:59:59`);
            // clamp to day range
            const start = s < dayStart ? dayStart : s;
            const end = e > dayEnd ? dayEnd : e;
            if (end <= start) return null;
            const left = (((start.getTime() - dayStart.getTime()) / 60000) / 60) * cellWidth;
            const width = Math.max(8, (((end.getTime() - start.getTime()) / 60000) / 60) * cellWidth);
            const cls = w.kind === "available" ? "avail-block bg-green-200 border-green-300" : "ooo-block bg-gray-200 border-gray-300";
            return (
              <div key={w.id ?? `w-${idx}`} className={`absolute top-1 bottom-1 border rounded ${cls}`}
                style={{ left, width }} data-id={w.id} data-x={0} data-doc={doc.id} />
            );
          })}
          {/* drag selection overlay */}
          {dragSel?.active && (
            <div
              className="absolute top-1 bottom-1 bg-blue-200/40 border border-blue-400 rounded pointer-events-none"
              style={{ left: `${Math.min(dragSel.startX, dragSel.endX)}px`, width: `${Math.max(1, Math.abs(dragSel.endX - dragSel.startX))}px` }}
            />
          )}
          {/* busy slots (red) overlay — day view clamped */}
          {doc.busy.map((b, idx) => {
            const s = new Date(b.start);
            const e = new Date(b.end);
            const day = days[0];
            const dayStart = new Date(`${day}T00:00:00`);
            const dayEnd = new Date(`${day}T23:59:59`);
            const start = s < dayStart ? dayStart : s;
            const end = e > dayEnd ? dayEnd : e;
            if (end <= start) return null;
            const left = (((start.getTime() - dayStart.getTime()) / 60000) / 60) * cellWidth;
            const width = Math.max(8, (((end.getTime() - start.getTime()) / 60000) / 60) * cellWidth);
            return (
              <div key={b.id ?? `tmp-${idx}`} className="busy-block absolute top-1 bottom-1 bg-red-200 border border-red-300 rounded pointer-events-none"
                style={{ left, width }} data-id={b.id} data-x={0} data-doc={doc.id} />
            );
          })}
        </div>
        </div>
      </div>
  );
}

// Adjust modal
function AdjustModal({ selection, multipleDoctorIds, day, onClose, onSaved, initialRange }: { selection?: {kind:'hospital'|'department'|'doctor'; id:number; name:string}; multipleDoctorIds?: number[]; day: string; onClose: () => void; onSaved?: () => void; initialRange?: { startISO: string; endISO: string } }) {
  const [dateStart, setDateStart] = useState(day);
  const [dateEnd, setDateEnd] = useState(day);
  const [available, setAvailable] = useState<Array<{start:string; end:string}>>([{ start: '08:00', end: '17:00' }]);
  const [ooo, setOoo] = useState<Array<{start:string; end:string}>>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string|null>(null);
  const [selectedKind, setSelectedKind] = useState<"available" | "ooo">('available');
  const prefilled = useRef(false);
  useEffect(() => {
    if (!initialRange) return;
    const sHM = isoToHM(initialRange.startISO);
    const eHM = isoToHM(initialRange.endISO);
    if (selectedKind === 'available') {
      setAvailable([{ start: sHM, end: eHM }]);
      setOoo([]);
    } else {
      setOoo([{ start: sHM, end: eHM }]);
      setAvailable([]);
    }
    if (!prefilled.current) {
      // ensure date range aligns to selected day (only once)
      const d = initialRange.startISO.slice(0, 10);
      setDateStart(d);
      setDateEnd(d);
      prefilled.current = true;
    }
  }, [initialRange, selectedKind]);
  const addRule = (setter: any) => setter((arr: any[]) => [...arr, { start: '08:00', end: '12:00' }]);
  const removeRule = (setter: any, idx: number) => setter((arr: any[]) => arr.filter((_, i) => i !== idx));
  const onSubmit = async () => {
    setSubmitting(true); setError(null);
    try {
      if (multipleDoctorIds && multipleDoctorIds.length > 1) {
        // Apply per doctor
        const results = await Promise.allSettled(multipleDoctorIds.map(async (id) => {
          const body = { scopeKind: 'doctor', scopeId: id, dateStart, dateEnd, available, ooo, overwrite: true };
          const res = await fetch(devApi('/api/dev/windows/bulk-adjust'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
          if (!res.ok) throw new Error(await res.text());
          return res.json().catch(() => ({}));
        }));
        const failed = results.filter(r => r.status === 'rejected');
        if (failed.length) throw new Error(`Một số thao tác thất bại: ${failed.length}/${results.length}`);
      } else if (selection) {
        const body = { scopeKind: selection.kind, scopeId: selection.id, dateStart, dateEnd, available, ooo, overwrite: true };
        const res = await fetch(devApi('/api/dev/windows/bulk-adjust'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        if (!res.ok) throw new Error(await res.text());
      } else {
        throw new Error('Chưa chọn đối tượng');
      }
      onClose();
      onSaved && onSaved();
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setSubmitting(false);
    }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded shadow-xl w-full max-w-[720px] p-4">
        <div className="flex items-center justify-between">
          <div className="font-semibold">Điều chỉnh lịch • {multipleDoctorIds && multipleDoctorIds.length > 1 ? `${multipleDoctorIds.length} bác sĩ` : (selection?.name || '')}</div>
          <button className="text-gray-600" onClick={onClose}>×</button>
        </div>
        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <div className="text-sm font-medium">Khoảng ngày áp dụng</div>
            <div className="mt-1 flex items-center gap-2">
              <input type="date" value={dateStart} onChange={(e)=>setDateStart(e.target.value)} className="border rounded px-2 py-1" disabled={!!initialRange} title={initialRange? 'Ngày bị khóa theo khoảng đã chọn' : undefined} />
              <span>→</span>
              <input type="date" value={dateEnd} onChange={(e)=>setDateEnd(e.target.value)} className="border rounded px-2 py-1" disabled={!!initialRange} title={initialRange? 'Ngày bị khóa theo khoảng đã chọn' : undefined} />
            </div>
          </div>
          {initialRange && (
            <div>
              <div className="text-sm font-medium">Khoảng đã chọn</div>
              <div className="mt-1 text-sm flex items-center gap-3">
                <span className="inline-block rounded bg-gray-100 px-2 py-0.5">
                  {isoToHM(initialRange.startISO)} → {isoToHM(initialRange.endISO)}
                </span>
                <label className="inline-flex items-center gap-1 text-gray-700">
                  <input type="radio" name="kind" checked={selectedKind==='available'} onChange={()=>setSelectedKind('available')} /> Rảnh
                </label>
                <label className="inline-flex items-center gap-1 text-gray-700">
                  <input type="radio" name="kind" checked={selectedKind==='ooo'} onChange={()=>setSelectedKind('ooo')} /> Nghỉ
                </label>
              </div>
            </div>
          )}
        </div>
        {!initialRange && (
          <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <div className="text-sm font-medium flex items-center justify-between">
                <span>Giờ có mặt tại bệnh viện</span>
                <button className="text-blue-600 text-xs" onClick={()=>addRule(setAvailable)}>+ Thêm</button>
              </div>
              <div className="mt-2 space-y-2">
                {available.map((r, idx)=>(
                  <div key={idx} className="flex items-center gap-2">
                    <input type="time" value={r.start} onChange={(e)=>setAvailable(arr=>arr.map((x,i)=>i===idx?{...x,start:e.target.value}:x))} className="border rounded px-2 py-1" />
                    <span>→</span>
                    <input type="time" value={r.end} onChange={(e)=>setAvailable(arr=>arr.map((x,i)=>i===idx?{...x,end:e.target.value}:x))} className="border rounded px-2 py-1" />
                    <button className="text-red-600 text-xs" onClick={()=>removeRule(setAvailable, idx)}>X</button>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="text-sm font-medium flex items-center justify-between">
                <span>Giờ vắng mặt tại bệnh viện</span>
                <button className="text-blue-600 text-xs" onClick={()=>addRule(setOoo)}>+ Thêm</button>
              </div>
              <div className="mt-2 space-y-2">
                {ooo.map((r, idx)=>(
                  <div key={idx} className="flex items-center gap-2">
                    <input type="time" value={r.start} onChange={(e)=>setOoo(arr=>arr.map((x,i)=>i===idx?{...x,start:e.target.value}:x))} className="border rounded px-2 py-1" />
                    <span>→</span>
                    <input type="time" value={r.end} onChange={(e)=>setOoo(arr=>arr.map((x,i)=>i===idx?{...x,end:e.target.value}:x))} className="border rounded px-2 py-1" />
                    <button className="text-red-600 text-xs" onClick={()=>removeRule(setOoo, idx)}>X</button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
        {error && <div className="mt-3 text-sm text-red-600">{error}</div>}
        <div className="mt-4 flex items-center justify-end gap-2">
          <button className="px-3 py-2 rounded border" onClick={onClose}>Hủy</button>
          <button className="px-3 py-2 rounded bg-blue-600 text-white disabled:opacity-60" disabled={submitting} onClick={onSubmit}>{submitting? 'Đang lưu...' : 'Lưu'}</button>
        </div>
      </div>
    </div>
  );
}

function indexToDate(index: number, days: string[], hours: number[]): Date {
  const dayIndex = 0; // day view only
  const hour = hours[0] + index;
  return new Date(`${days[dayIndex]}T${String(hour).padStart(2, "0")}:00:00`);
}

function dateToIndex(dt: Date, days: string[], hours: number[]): number {
  const hour = dt.getHours();
  return Math.max(0, hour - hours[0]);
}

// ------- Week view (time rows, day columns) -------
function WeekHospitalGrid({ hospital, days }: { hospital: HospitalGroup; days: string[] }) {
  const rowHeight = 36; // px per hour row
  const totalHeight = rowHeight * 24;
  const [depId, setDepId] = useState<string>("");
  const [docId, setDocId] = useState<string>("");
  const [selectedInfo, setSelectedInfo] = useState<{ doctor: string; start: string; end: string } | null>(null);
  const [popover, setPopover] = useState<{ x: number; y: number; data: any } | null>(null);

  const deps = hospital.departments;
  const docs = useMemo(() => {
    const list: { id: number; name: string }[] = [];
    deps.forEach(d => d.doctors.forEach(doc => { if (!depId || String(d.id) === depId) list.push({ id: doc.id, name: doc.name }); }));
    return list;
  }, [deps, depId]);

  // Helper to compute top/height in the column
  const toMinutes = (dt: Date) => dt.getHours() * 60 + dt.getMinutes();

  return (
    <div className="mt-6">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-lg">{hospital.name}</h2>
        <div className="flex items-center gap-4">
          {/* Filters */}
          <select className="border rounded-md px-2 py-1" value={depId} onChange={(e) => { setDepId(e.target.value); setDocId(""); }}>
            <option value="">Tất cả khoa</option>
            {deps.map(d => <option key={d.id} value={String(d.id)}>{d.name}</option>)}
          </select>
          <select className="border rounded-md px-2 py-1" value={docId} onChange={(e) => setDocId(e.target.value)}>
            <option value="">Tất cả bác sĩ</option>
            {docs.map(d => <option key={d.id} value={String(d.id)}>{d.name}</option>)}
          </select>
        </div>
      </div>
      <div className="mt-2 overflow-x-auto">
        <div className="min-w-[1100px] border rounded-lg">
          {/* Header: empty cell + day columns */}
          <div className="grid" style={{ gridTemplateColumns: `120px repeat(${days.length}, 1fr)` }}>
            <div className="p-2 text-xs text-gray-500 border-b">Giờ</div>
            {days.map((d) => (
              <div key={d} className="p-2 text-xs text-gray-600 border-b text-center">
                {formatVNDate(d)}
              </div>
            ))}
          </div>
          {/* Body: time labels + day columns with blocks */}
          <div className="grid" style={{ gridTemplateColumns: `120px repeat(${days.length}, 1fr)` }}>
            {/* Time labels */}
            <div className="relative" style={{ height: `${totalHeight}px` }}>
              {Array.from({ length: 24 }, (_, h) => (
                <div key={h} className="absolute left-0 right-0 border-b text-[10px] text-gray-500 pr-2 text-right" style={{ top: `${h * rowHeight}px`, height: `${rowHeight}px`, lineHeight: `${rowHeight}px` }}>
                  {String(h).padStart(2, "0")}:00
                </div>
              ))}
            </div>
            {/* Day columns */}
            {days.map((d) => (
              <div key={`col-${d}`} className="relative border-l" style={{ height: `${totalHeight}px` }}>
                {/* hour grid lines */}
                {Array.from({ length: 24 }, (_, h) => (
                  <div key={h} className="absolute left-0 right-0 border-b border-dashed" style={{ top: `${h * rowHeight}px`, height: `${rowHeight}px` }} />
                ))}
                {/* Hide available/OOO in week view by request */}
                {/* busy slots (red) per doctor */}
                {hospital.departments.flatMap(dep => dep.doctors.map(dr => ({ dep, dr }))).filter(({ dep, dr }) => (
                  (!depId || String(dep.id) === depId) && (!docId || String(dr.id) === docId)
                )).flatMap(({ dep, dr }) => dr.busy.map(b => ({ b, dr }))).filter(({ b }) => (new Date(b.start)).toISOString().slice(0,10) === d).map(({ b, dr }, idx) => {
                  const s = new Date(b.start);
                  const e = new Date(b.end);
                  const top = (toMinutes(s) / 60) * rowHeight;
                  const height = Math.max(8, ((toMinutes(e) - toMinutes(s)) / 60) * rowHeight);
                  const label = `${dr.name} • ${String(s.getHours()).padStart(2, '0')}:${String(s.getMinutes()).padStart(2, '0')}–${String(e.getHours()).padStart(2, '0')}:${String(e.getMinutes()).padStart(2, '0')}`;
                  return (
                    <div key={b.id ?? `b-${idx}`} className="absolute left-1 right-1 bg-red-200 border border-red-400 rounded text-[11px] px-1 py-0.5 cursor-pointer"
                      style={{ top, height, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}
                      onClick={async (evt) => {
                        const el = evt.currentTarget as HTMLDivElement | null;
                        const rect = el?.getBoundingClientRect() || { right: evt.clientX, top: evt.clientY } as any;
                        setSelectedInfo({ doctor: dr.name, start: s.toISOString(), end: e.toISOString() });
                        // Fetch appointment detail by doctor and start time
                        try {
                          const params = new URLSearchParams({ doctor_id: String(dr.id), start: toLocalNaiveISO(s) });
                          const res = await fetch(devApi(`/api/appointments/lookup?${params.toString()}`));
                          const j = await res.json();
                          setPopover({ x: (rect as any).right + 8, y: (rect as any).top, data: j });
                        } catch (e) {
                          // fallback popover with basic info
                          setPopover({ x: (rect as any).right + 8, y: (rect as any).top, data: { error: String(e) } });
                        }
                      }}
                    >
                      {label}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
      {popover && (
        <FloatingPopover x={popover.x} y={popover.y} onClose={() => setPopover(null)}>
          <PopoverContent data={popover.data} fallback={selectedInfo || undefined} />
        </FloatingPopover>
      )}
    </div>
  );
}

function formatVNDate(d: string) {
  const dt = new Date(`${d}T00:00:00`);
  return dt.toLocaleDateString('vi-VN', { weekday: 'short', day: '2-digit', month: '2-digit' });
}

function formatVNTime(iso: string) {
  const dt = new Date(iso);
  return dt.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
}

function pad2(n: number) { return String(n).padStart(2, '0'); }
function isoToHM(iso: string) {
  const d = new Date(iso);
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

// Format local-naive ISO string (no timezone) e.g., 2025-08-31T07:00:00
function toLocalNaiveISO(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth()+1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}

function FloatingPopover({ x, y, onClose, children }: { x: number; y: number; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed z-50" style={{ left: x, top: y }}>
      <div className="relative bg-white border rounded shadow-xl w-[320px] p-3">
        <button className="absolute -right-2 -top-2 h-6 w-6 rounded-full bg-gray-200 text-gray-700 text-sm" onClick={onClose}>×</button>
        {children}
      </div>
    </div>
  );
}

function PopoverContent({ data, fallback }: { data: any; fallback?: { doctor: string; start: string; end: string } }) {
  const ap = data?.appointment;
  if (data?.error) {
    return <div className="text-sm text-red-600">Lỗi tải thông tin: {String(data.error)}</div>;
  }
  if (!ap && fallback) {
    return (
      <div className="text-sm">
        <div className="font-medium">{fallback.doctor}</div>
        <div>Thời gian: {formatVNTime(fallback.start)} - {formatVNTime(fallback.end)}</div>
      </div>
    );
  }
  if (!ap) {
    return <div className="text-sm text-gray-600">Không tìm thấy phiếu hẹn cho ca này.</div>;
  }
  const c = ap.content || {};
  return (
    <div className="text-sm space-y-1">
      <div className="font-medium">{c.patient_name || ap.user?.name || 'Bệnh nhân'}</div>
      <div>Bệnh viện: {c.hospital || ap.hospital || '-'}</div>
      <div>Khoa: {c.department_name || ap.department || '-'}</div>
      <div>Bác sĩ: {c.doctor_name || ap.doctor?.name || '-'}</div>
      <div>Giờ khám: {formatVNTime(c.time_slot || ap.when)}</div>
      {c.room_code && <div>Phòng: {c.room_code}</div>}
      {Array.isArray(c.symptoms) && c.symptoms.length > 0 && (
        <div>Triệu chứng: {c.symptoms.join(', ')}</div>
      )}
      {ap.user?.phone && <div>SĐT: {ap.user.phone}</div>}
    </div>
  );
}
