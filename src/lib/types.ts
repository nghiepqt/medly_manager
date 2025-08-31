export type PatientProfile = {
  id: string;
  name: string;
  phone: string;
};

export type AppointmentSuggestion = never;

export type BookingSummary = {
  userId: string;
  name: string;
  phone: string;
  need: string;
  symptoms?: string;
  hospitalId: string;
  hospitalName: string;
  department: string;
  doctorId: string;
  doctorName: string;
  time: string; // ISO
};

export type ConversationTurn = never;
export type ConversationRecord = never;

export type UpcomingAppointment = {
  id: string;
  when: string; // ISO
  stt?: number | null;
  hospitalName: string;
  doctorName: string;
  department: string;
};

export type BookingOut = {
  id: number;
  created_at: string; // ISO
  stt?: number | null;
  content: {
    hospital?: string;
    patient_name?: string;
    phone_number?: string;
    doctor_name?: string;
    department_name?: string;
    room_code?: string;
    time_slot?: string;
    symptoms?: string[];
  };
};

export type HospitalUsersResponse = {
  hospitals: Array<{
    id: number;
    name: string;
    users: Array<{ id: string; name: string; phone: string; cccd?: string | null; appointments: number; last_when?: string | null }>;
  }>;
};

export type HospitalUserProfile = {
  hospital: { id: number; name: string };
  user: { id: string; name: string; phone: string; cccd?: string | null; bhyt?: string | null };
  appointments: Array<{ id: number; when: string; stt?: number | null; doctorName: string; department: string; content: any }>;
};

export type UpcomingByHospitalResponse = {
  hospitals: Array<{
    id: number;
    name: string;
  appointments: Array<{ id: string; when: string; stt?: number | null; user: { id: string; name: string; phone: string }; department: string; doctorName: string }>;
  }>;
};
