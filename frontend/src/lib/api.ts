import axios from 'axios';
import { translateWithAI } from './aiService';

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// ── Session token ─────────────────────────────────────────────────────────
// The login portal hands the dashboard a signed token in the redirect URL;
// useDashboardState stores it here. Every request carries it so the backend
// can tell whose data it is serving without trusting anything else the client
// sends. Routes that don't yet check it simply ignore the header.

export const TOKEN_KEY = 'sgs_token';
export const PARENT_NAME_KEY = 'sgs_parent_name';
/** Fired on window whenever the session's parent changes (login, logout). */
export const SESSION_EVENT = 'sgs:session';

export const getSessionToken = (): string | null =>
  typeof window === 'undefined' ? null : localStorage.getItem(TOKEN_KEY);

export const setSessionToken = (token: string | null) => {
  if (typeof window === 'undefined') return;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
};

api.interceptors.request.use((config) => {
  const token = getSessionToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

/** Who does the current token belong to? Throws on a missing/invalid token. */
export const fetchMe = async (): Promise<{ parent_id: number; full_name: string | null; email: string | null }> => {
  const response = await api.get('/auth/me');
  return response.data;
};

export const fetchDashboardData = async (studentId: number) => {
  const response = await api.get(`/dashboard/${studentId}`);
  return response.data;
};

export const fetchParentChildren = async (parentId: number) => {
  const response = await api.get(`/parents/${parentId}/children`);
  return response.data;
};

export const fetchAssignmentsHistory = async (studentId: number) => {
  try {
    const response = await api.get(`/assignments/history/${studentId}`);
    return response.data;
  } catch { return []; }
};

export const fetchAssignmentAnalytics = async (studentId: number) => {
  try {
    const response = await api.get(`/assignments/analytics/${studentId}`);
    return response.data;
  } catch { return { total: 0, submitted: 0, pending: 0, overdue: 0, graded: 0, completion_pct: 0 }; }
};

export const submitAssignment = async (payload: { assignment_id: number; student_id: number; submission_text: string; file_path?: string }) => {
  const response = await api.post('/assignments/submit', payload);
  return response.data;
};

export const fetchQuizHistory = async (studentId: number) => {
  try {
    const response = await api.get(`/quiz/history/${studentId}`);
    return response.data;
  } catch { return []; }
};

export const fetchRemarksHistory = async (studentId: number) => {
  try {
    const response = await api.get(`/remarks/history/${studentId}`);
    return response.data;
  } catch { return []; }
};

export const fetchNoticesHistory = async (studentId: number) => {
  try {
    const response = await api.get(`/notices/history/${studentId}`);
    return response.data;
  } catch { return []; }
};

// DISABLED: fetchCallRequestsHistory — no page imports this after dashboard
// redesign removed the call-request feature. The backend route is also
// commented out. Restore both if a PTM-request history view is added.
//
// export const fetchCallRequestsHistory = async (studentId: number) => {
//   const response = await api.get(`/call-requests/history/${studentId}`);
//   return response.data;
// };

export const translateText = async (text: string, targetLang: string) => {
  if (!text) return { translated_text: text, original_text: text };
  if (targetLang === 'en') return { translated_text: text, original_text: text };

  const result = await translateWithAI({ text, targetLang });
  if (result.success) return result.data;

  // AI translation unavailable — return original text.
  // translateCached will display raw text gracefully rather than crashing.
  return { translated_text: text, original_text: text };
};

// DISABLED: requestCall — POST /request-call backend route is commented out.
// No frontend page imports this function. Restore if PTM-request feature
// is built into the Communication Center or a dedicated PTM page.
//
// export const requestCall = async (parentId: number, studentId: number, message: string) => {
//   const response = await api.post('/request-call', {
//     parent_id: parentId,
//     student_id: studentId,
//     message,
//   });
//   return response.data;
// };

// DISABLED: Old chat-thread system helpers ─────────────────────────────────
// fetchChatThreads, fetchChatMessages, sendChatMessage called the /chat/
// routes backed by ChatThread + ChatMessage tables. That system was replaced
// by the /comm/ Communication Center. The backend routes are also commented
// out. Restore all three if the old thread-based chat is revived.
//
// export const fetchChatThreads = async (parentId: number, studentId: number) => {
//   const response = await api.get(`/chat/threads/${parentId}/${studentId}`);
//   return response.data;
// };
//
// export const fetchChatMessages = async (threadId: number) => {
//   const response = await api.get(`/chat/messages/${threadId}`);
//   return response.data;
// };
//
// export const sendChatMessage = async (threadId: number, senderType: string, senderId: number, message: string) => {
//   const response = await api.post('/chat/messages', {
//     thread_id: threadId,
//     sender_type: senderType,
//     sender_id: senderId,
//     message,
//   });
//   return response.data;
// };
// ──────────────────────────────────────────────────────────────────────────

// DISABLED: fetchAnalytics — /parent/analytics page was removed; GET
// /analytics/{student_id} backend route is also commented out. Restore both
// if a dedicated analytics module is added back to the sidebar.
//
// export const fetchAnalytics = async (studentId: number) => {
//   const response = await api.get(`/analytics/${studentId}`);
//   return response.data;
// };

// DISABLED: fetchCommunicationTimeline — GET /communication/timeline/{student_id}
// had no frontend caller after the dashboard redesign. Backend route is also
// commented out. Restore if a unified timeline view is built.
//
// export const fetchCommunicationTimeline = async (studentId: number) => {
//   const response = await api.get(`/communication/timeline/${studentId}`);
//   return response.data;
// };

export const fetchAssignmentAttachment = async (
  assignmentId: number,
  studentId: number,
): Promise<{ file_name: string; url: string } | null> => {
  try {
    const response = await api.get(`/assignments/${assignmentId}/attachment`, {
      params: { student_id: studentId },
    });
    return response.data;
  } catch {
    return null;
  }
};

export const fetchAssessmentHistory = async (studentId: number) => {
  try {
    const response = await api.get(`/assessments/history/${studentId}`);
    return response.data;
  } catch { return []; }
};

export const fetchAssessmentAnalytics = async (studentId: number) => {
  try {
    const response = await api.get(`/assessments/analytics/${studentId}`);
    return response.data;
  } catch {
    return {
      total_assessments: 0, average_percentage: 0,
      highest_score: 0, lowest_score: 0,
      trend_data: [], subject_data: [], subjects: [],
    };
  }
};

export const fetchNotifications = async (studentId: number) => {
    const response = await api.get(`/notifications/${studentId}`);
    return response.data;
};

export type ParentNotification = {
  id: string; type: string; title: string; teacher_name: string;
  notification_type: string; message: string; date: string; channel: string; link: string; is_read: boolean;
};
export const fetchNotificationHistory = async (studentId: number, offset = 0, signal?: AbortSignal): Promise<{ items: ParentNotification[]; has_more: boolean }> => {
  const response = await api.get(`/notification-history/${studentId}`, { params: { offset, limit: 50 }, signal });
  return response.data;
};

export const fetchUnreadCommCount = async (studentId: number): Promise<number> => {
  try {
    const response = await api.get(`/notifications/unread-count/${studentId}`);
    return response.data?.unread_comm_count ?? 0;
  } catch { return 0; }
};

export const closeConversation = async (convId: number) => {
  try {
    await api.patch(`/comm/conversations/${convId}/status`, null, { params: { status: 'CLOSED' } });
  } catch { /* ignore */ }
};

// DISABLED: Old support-ticket API helpers ─────────────────────────────────
// fetchTickets, createTicket, fetchTicketMessages, createTicketMessage called
// the /tickets/ CRUD routes which had a FastAPI 422 route-ordering bug and
// were replaced by the /comm/ Communication Center. The backend /tickets/
// routes are also commented out. Restore all four if the old ticket system
// is ever needed again (note: fix route ordering before restoring).
//
// export const fetchTickets = async (parentId: number, studentId: number) => {
//   const response = await api.get(`/tickets/${parentId}/${studentId}`);
//   return response.data;
// };
//
// export const createTicket = async (parentId: number, studentId: number, subject: string, category: string, priority: string, message: string) => {
//   const response = await api.post('/tickets', { parent_id: parentId, student_id: studentId, subject, category, priority, message });
//   return response.data;
// };
//
// export const fetchTicketMessages = async (ticketId: number) => {
//   const response = await api.get(`/tickets/${ticketId}/messages`);
//   return response.data;
// };
//
// export const createTicketMessage = async (ticketId: number, senderType: string, senderName: string, message: string) => {
//   const response = await api.post(`/tickets/${ticketId}/messages`, { ticket_id: ticketId, sender_type: senderType, sender_name: senderName, message });
//   return response.data;
// };
// ──────────────────────────────────────────────────────────────────────────

// ── Communication Center APIs (/comm/ prefix – no 422 ambiguity) ─────────

export const fetchConversationRecipients = async (studentId: number) => {
  try {
    const response = await api.get(`/comm/teachers/${studentId}`);
    return response.data;
  } catch { return []; }
};

export const fetchConversations = async (studentId: number, _parentId?: number) => {
  try {
    const response = await api.get(`/comm/conversations/${studentId}`);
    return response.data;
  } catch { return []; }
};

export const createConversation = async (payload: {
  student_id: number;
  parent_id: number;
  subject: string;
  category: string;
  recipient_name: string;
  /** users_masters.user_id of the teacher written to — how the faculty side
   *  finds this conversation. Null only when the picker could not resolve one. */
  recipient_user_id: number | null;
  first_message: string;
}) => {
  const response = await api.post('/comm/conversations', payload);
  return response.data;
};

export const fetchConversationMessages = async (convId: number) => {
  try {
    const response = await api.get(`/comm/conversations/${convId}/messages`);
    return response.data;
  } catch { return []; }
};

export const sendConversationMessage = async (
  convId: number,
  senderType: string,
  senderName: string,
  message: string,
) => {
  const response = await api.post(`/comm/conversations/${convId}/messages`, {
    sender_type: senderType,
    sender_name: senderName,
    message,
  });
  return response.data;
};

// DISABLED: Attendance API helpers ───────────────────────────────────────
// Attendance module has been removed from the parent portal.
// These functions are preserved for reference; restore together with
// the attendance page and backend router if the module is reinstated.
//
// export const fetchAttendanceData = async (studentId: number) => {
//   try {
//     const response = await api.get(`/attendance/${studentId}`);
//     return response.data;
//   } catch { return null; }
// };
//
// export const fetchLeaveRequests = async (studentId: number) => {
//   try {
//     const response = await api.get(`/attendance/leave-requests/${studentId}`);
//     return response.data;
//   } catch { return []; }
// };
//
// export const submitLeaveRequest = async (payload: {
//   student_id: number;
//   parent_id: number;
//   from_date: string;
//   to_date: string;
//   reason: string;
//   parent_note?: string;
// }) => {
//   const response = await api.post('/attendance/leave-request', payload);
//   return response.data;
// };
//
// export const updateLeaveStatus = async (leaveRequestId: number, status: string, reviewedBy: number) => {
//   const response = await api.patch(`/attendance/leave-request/${leaveRequestId}`, { status, reviewed_by: reviewedBy });
//   return response.data;
// };
// ──────────────────────────────────────────────────────────────────────────
