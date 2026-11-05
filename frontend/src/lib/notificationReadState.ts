export const NOTIFICATION_READ_EVENT = 'sgs:notification-read';
export function readNotificationIds(parentId: number, studentId: number): Set<string> {
  try { return new Set(JSON.parse(localStorage.getItem(`sgs_parent_${parentId}_student_${studentId}_notifications`) || '[]')); }
  catch { return new Set(); }
}
export function saveNotificationIds(parentId: number, studentId: number, ids: Set<string>) {
  try { localStorage.setItem(`sgs_parent_${parentId}_student_${studentId}_notifications`, JSON.stringify([...ids])); }
  catch { /* The current view still works if browser storage is unavailable. */ }
  window.dispatchEvent(new CustomEvent(NOTIFICATION_READ_EVENT, { detail: { parentId, studentId } }));
}
