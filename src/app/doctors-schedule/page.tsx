import { redirect } from "next/navigation";

export default function DoctorsSchedule() {
  // Alias to existing Dev schedule page for now
  redirect("/dev");
}
