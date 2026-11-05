'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { XMarkIcon, ArrowRightOnRectangleIcon } from '@heroicons/react/24/outline';
import { clearAICache } from '@/lib/aiService';

// ── Logout Confirmation Dialog ────────────────────────────────────────────────

function LogoutDialog({ onConfirm, onCancel }: { onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onCancel} />
      <div className="relative bg-slate-800 rounded-2xl shadow-2xl w-full max-w-sm z-[210] overflow-hidden border border-white/10">
        <div className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-11 h-11 rounded-full bg-red-500/20 flex items-center justify-center text-xl shrink-0">👋</div>
            <div>
              <h3 className="font-black text-white text-lg leading-tight">Log out?</h3>
              <p className="text-sm text-slate-400 mt-0.5">Are you sure you want to logout?</p>
            </div>
          </div>
          <div className="flex gap-3 mt-6">
            <button
              onClick={onCancel}
              className="flex-1 py-2.5 rounded-xl border font-semibold text-sm text-slate-300 hover:bg-white/10 transition-colors"
              style={{ borderColor: 'rgba(255,255,255,0.15)' }}
            >
              Cancel
            </button>
            <button
              onClick={onConfirm}
              className="flex-1 py-2.5 rounded-xl font-bold text-sm text-white bg-red-500 hover:bg-red-600 transition-colors"
            >
              Logout
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Toast ─────────────────────────────────────────────────────────────────────

function Toast({ message }: { message: string }) {
  return (
    <div className="fixed top-4 right-4 z-[300] bg-green-600 text-white text-sm font-semibold px-4 py-2.5 rounded-xl shadow-lg">
      {message}
    </div>
  );
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

export default function Sidebar() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const [showLogoutDlg, setShowLogoutDlg] = useState(false);
  const [showToast, setShowToast] = useState(false);

  // Listen for toggle events dispatched by TopBar's hamburger button
  useEffect(() => {
    const handleToggle = () => setIsOpen(prev => !prev);
    window.addEventListener('sgsSidebarToggle', handleToggle);
    return () => window.removeEventListener('sgsSidebarToggle', handleToggle);
  }, []);

  // Auto-close sidebar when route changes (mobile navigation)
  useEffect(() => {
    setIsOpen(false);
  }, [pathname]);

  const handleLogoutConfirm = () => {
    const sgsUrl = process.env.NEXT_PUBLIC_SGS_URL;
    if (!sgsUrl) {
      console.error('[SGS] NEXT_PUBLIC_SGS_URL is not configured. Cannot redirect after logout.');
      alert('Logout redirect is not configured. Please contact your administrator.');
      return;
    }
    clearAICache();
    setShowLogoutDlg(false);
    setShowToast(true);
    setTimeout(() => {
      window.location.replace(sgsUrl);
    }, 1000);
  };

  const menuItems = [
    { name: 'Dashboard',            icon: '🏠', path: '/parent/dashboard' },
    { name: 'Student Timetable', icon: '📅', path: '/parent/timetable' },
    { name: 'Assessments',          icon: '📝', path: '/parent/assessments' },
    { name: 'Assignments',          icon: '📄', path: '/parent/assignments' },
    { name: 'Quiz Performance',     icon: '📊', path: '/parent/quiz' },
    { name: 'Teacher Remarks',      icon: '💬', path: '/parent/remarks' },
    { name: 'Notices',              icon: '🔔', path: '/parent/notices' },
    { name: 'Notifications',        icon: '🔔', path: '/parent/notifications' },
    { name: 'Communication Center', icon: '🏫', path: '/parent/communication' },
  ];

  return (
    <>
      {/* Mobile overlay — sits behind sidebar, above page content */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 md:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}

      <aside
        className={`
          w-full sm:w-64 bg-slate-900/95 backdrop-blur-md text-white flex flex-col h-screen
          fixed left-0 top-0 overflow-y-auto z-40 border-r border-white/5
          transition-transform duration-300 ease-in-out
          ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        `}
      >
        <div className="p-6 flex items-center gap-3 border-b border-white/10">
          <img src="/parent/logo.jpeg" alt="SGS-SWAIS" className="h-10 w-auto" />
          <div className="flex-1 min-w-0">
            <p className="text-xs text-gray-400">Parent Dashboard</p>
          </div>
          {/* Close button — mobile only */}
          <button
            onClick={() => setIsOpen(false)}
            className="md:hidden text-gray-400 hover:text-white transition-colors shrink-0"
            aria-label="Close menu"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 py-6">
          <ul className="space-y-2 px-4">
            {menuItems.map((item, index) => {
              const isActive = pathname.startsWith(item.path);
              return (
                <li key={index}>
                  <Link
                    href={item.path}
                    className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                      isActive
                        ? 'bg-orange-600 text-white'
                        : 'text-slate-300 hover:bg-white/10 hover:text-white'
                    }`}
                  >
                    <span>{item.icon}</span>
                    <span className="font-medium">{item.name}</span>
                  </Link>
                </li>
              );
            })}

            {/* Logout — separated from nav items by a divider */}
            <li className="pt-2 mt-2 border-t border-white/10">
              <button
                onClick={() => setShowLogoutDlg(true)}
                className="w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors text-red-400 hover:bg-red-500/10 hover:text-red-300"
              >
                <ArrowRightOnRectangleIcon className="w-5 h-5 shrink-0" />
                <span className="font-medium">Logout</span>
              </button>
            </li>
          </ul>
        </nav>

        <div className="p-4 mt-auto">
          <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-center text-slate-300 shadow-sm">
            <div className="flex justify-center mb-2">
              <span className="text-4xl">👨‍👩‍👦</span>
            </div>
            <p className="text-sm font-medium leading-tight">
              Stay connected with your child&apos;s learning journey.
            </p>
          </div>
        </div>
      </aside>

      {showLogoutDlg && (
        <LogoutDialog
          onConfirm={handleLogoutConfirm}
          onCancel={() => setShowLogoutDlg(false)}
        />
      )}

      {showToast && <Toast message="You have been logged out successfully." />}
    </>
  );
}
