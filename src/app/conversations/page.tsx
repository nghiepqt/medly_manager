"use client";
import { redirect } from "next/navigation";

export default function ConversationsPage() {
  // Legacy route removed. Redirect to doctors schedule.
  redirect("/doctors-schedule");
  return null;
}
