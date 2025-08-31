"use client";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { PatientProfile } from "./types";

type Ctx = {
  user: PatientProfile | null;
  setUser: (u: PatientProfile | null) => void;
};

const UserCtx = createContext<Ctx | undefined>(undefined);

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<PatientProfile | null>(null);
  // hydrate from localStorage
  useEffect(() => {
    try {
      const raw = localStorage.getItem("medly.user");
      if (raw) setUser(JSON.parse(raw));
    } catch {}
  }, []);
  const value = useMemo(() => ({ user, setUser: (u: PatientProfile | null) => {
    setUser(u);
    try {
      if (u) localStorage.setItem("medly.user", JSON.stringify(u));
      else localStorage.removeItem("medly.user");
    } catch {}
  }}), [user]);
  return <UserCtx.Provider value={value}>{children}</UserCtx.Provider>;
}

export function useUser() {
  const ctx = useContext(UserCtx);
  if (!ctx) throw new Error("useUser must be used within UserProvider");
  return ctx;
}
