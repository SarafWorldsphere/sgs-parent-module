"use client";

import type { ReactNode } from "react";
import { useSchool } from "@saraswati/tenant-kit";
import CenteredFrame from "@/components/CenteredFrame";
import Sidebar from "@/components/Sidebar";

export default function ParentShell({ children }: { children: ReactNode }) {
  const school = useSchool();
  if (school.layout === "centered") {
    return <CenteredFrame>{children}</CenteredFrame>;
  }
  return (
    <div className="flex min-h-screen bg-gradient-to-br from-[#0f172a] via-[#1e1b4b] to-[#0f172a] font-sans">
      <Sidebar />
      <div className="flex-1 md:ml-64 flex flex-col min-w-0">{children}</div>
    </div>
  );
}
