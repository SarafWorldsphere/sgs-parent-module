'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import TopBar from '@/components/TopBar';
import { useDashboard } from '@/lib/DashboardContext';
import { fetchNotificationHistory, ParentNotification } from '@/lib/api';
import { NOTIFICATION_READ_EVENT, readNotificationIds, saveNotificationIds } from '@/lib/notificationReadState';
import styles from './notifications.module.css';

export default function NotificationsPage() {
  const { parentId, studentId, setStudentId, language, setLanguage } = useDashboard();
  const scope = `${parentId}:${studentId}`;
  const request = useRef<AbortController | null>(null);
  const [result, setResult] = useState<{ scope: string; items: ParentNotification[]; hasMore: boolean } | null>(null);
  const [readIds, setReadIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('all');
  const items = result?.scope === scope ? result.items : [];
  const isRead = (n: ParentNotification) => n.is_read || readIds.has(n.id);

  async function load(offset = 0) {
    if (!parentId || !studentId) return;
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    setError('');
    try {
      const data = await fetchNotificationHistory(studentId, offset, controller.signal);
      if (!controller.signal.aborted) setResult(old => ({ scope,
        items: offset && old?.scope === scope ? [...old.items, ...data.items] : data.items,
        hasMore: data.has_more }));
    } catch (e: unknown) {
      if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Unable to load notifications.');
    } finally { if (!controller.signal.aborted) setLoading(false); }
  }

  useEffect(() => {
    setResult(null);
    setFilter('all');
    setReadIds(readNotificationIds(parentId, studentId));
    load();
    return () => request.current?.abort();
    // Reload only when the authenticated parent/selected child changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parentId, studentId]);

  useEffect(() => {
    const sync = () => setReadIds(readNotificationIds(parentId, studentId));
    window.addEventListener(NOTIFICATION_READ_EVENT, sync);
    return () => window.removeEventListener(NOTIFICATION_READ_EVENT, sync);
  }, [parentId, studentId]);

  function markRead(ids: string[]) {
    const next = new Set([...readNotificationIds(parentId, studentId), ...ids]);
    setReadIds(next);
    saveNotificationIds(parentId, studentId, next);
  }

  return <>
    <TopBar {...{ parentId, studentId, setStudentId, language, setLanguage }} isLoading={loading} />
    <main className={styles.page}>
      <h1>Notifications</h1>
      <p>Teacher messages and alerts for your selected child, newest first.</p>
      {!parentId ? <p role="status">Please sign in to view notifications.</p>
        : !studentId ? <p role="status">Select a child above to view notifications.</p> : <>
          <div className={styles.toolbar}>
            <label>Show <select value={filter} onChange={e => setFilter(e.target.value)}>
              <option value="all">All</option><option value="unread">Unread</option><option value="read">Read</option>
            </select></label>
            <button disabled={loading} onClick={() => load()}>Refresh</button>
            <button disabled={!items.length || loading} onClick={() => markRead(items.map(n => n.id))}>Mark loaded messages as read</button>
          </div>
          <p className={styles.note}>Read status for direct alerts is saved in this browser.</p>
          {error && <p role="alert" className={styles.error}>{error} <button onClick={() => load()}>Retry</button></p>}
          {loading && <p role="status">Loading notifications…</p>}
          <div className={styles.list}>{items.filter(n => filter === 'all' || (filter === 'read' ? isRead(n) : !isRead(n))).map(n =>
            <article key={n.id} className={styles.card}>
              <div className={styles.row}><h2>{n.title}</h2><span>{isRead(n) ? 'Read' : 'Unread'}</span></div>
              <p className={styles.meta}>{n.notification_type.replaceAll('_', ' ')} · {n.date ? new Date(n.date).toLocaleString('en-IN') : 'Date unavailable'}</p>
              <p className={styles.message}>{n.message}</p>
              <div className={styles.row}>
                {!isRead(n) && <button onClick={() => markRead([n.id])}>Mark as read</button>}
                {n.type === 'ticket_reply' && <Link href={n.link} onClick={() => markRead([n.id])}>Open Communication Center</Link>}
              </div>
            </article>)}</div>
          {!loading && !error && !items.some(n => filter === 'all' || (filter === 'read' ? isRead(n) : !isRead(n))) && <p role="status">No notifications in this view.</p>}
          {result?.scope === scope && result.hasMore && <button disabled={loading} onClick={() => load(items.length)}>Load older notifications</button>}
        </>}
    </main>
  </>;
}
