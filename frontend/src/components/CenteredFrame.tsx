"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useSchool } from "@saraswati/tenant-kit";
import { clearAICache } from "@/lib/aiService";
import { schoolLogo } from "@saraswati/tenant-kit";
import { parentMenu } from "@/lib/parentNav";

export default function CenteredFrame({ children }: { children: ReactNode }) {
  const school = useSchool();
  const pathname = usePathname();

  return (
    <div className="min-h-screen" style={{ background: "var(--school-background)" }}>
      <header className="text-white" style={{ background: "var(--school-primary)" }}>
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 px-4 py-4">
          <div className="flex items-center gap-3">
            <img src={schoolLogo(school.tenantId)} alt="" className="h-10 w-auto" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-base font-semibold">{school.schoolName}</p>
              <p className="text-xs text-white/70">Parent Dashboard</p>
            </div>
            <button
              type="button"
              className="rounded-lg px-3 py-2 text-sm font-semibold text-white/90 hover:bg-white/10"
              onClick={() => {
                clearAICache();
                window.location.replace("/");
              }}
            >
              Logout
            </button>
          </div>
          <nav className="flex gap-2 overflow-x-auto pb-1">
            {parentMenu.map((item) => {
              const isActive = pathname.startsWith(item.path);
              return (
                <Link
                  key={item.path}
                  href={item.path}
                  className={`whitespace-nowrap rounded-lg px-3 py-2 text-sm ${
                    isActive ? "bg-[var(--school-accent)] text-white" : "text-white/80 hover:bg-white/10"
                  }`}
                >
                  <span className="mr-1">{item.icon}</span>
                  {item.name}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      <div className="mx-auto w-full max-w-5xl px-4 py-6">{children}</div>
    </div>
  );
}
