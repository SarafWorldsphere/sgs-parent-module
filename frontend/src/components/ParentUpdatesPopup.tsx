'use client';

import { useEffect, useRef } from 'react';
import styles from './ParentUpdatesPopup.module.css';

export type ParentUpdate = { id: string; type: string; title: string; message: string; date: string };

export default function ParentUpdatesPopup({ updates, selected, onOpen, onClose, onDismiss }: {
  updates: ParentUpdate[]; selected: ParentUpdate | null;
  onOpen: (item: ParentUpdate) => void; onClose: () => void; onDismiss: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (selected && !dialog.current?.open) dialog.current?.showModal();
    if (!selected && dialog.current?.open) dialog.current.close();
  }, [selected]);
  const duration = Math.max(75, Math.round(updates.reduce((n, item) => n + item.title.length + item.message.length, 0) * .24));

  return <>
    {updates.length > 0 && <section className={styles.ticker} aria-label="Latest parent updates">
      <strong className={styles.label}>Latest Updates</strong>
      <div className={styles.window}>
        <div className={styles.track} style={{ animationDuration: `${duration}s` }}>
          {[0, 1].map(copy => <div className={styles.group} key={copy} aria-hidden={copy === 1 ? true : undefined}>
            {updates.map(item => <button type="button" key={item.id} tabIndex={copy ? -1 : 0} onClick={() => onOpen(item)}>
              <span className={styles.badge}>{item.type === 'announcement' ? 'Notice' : 'Teacher message'}</span>
              <strong>{item.title}</strong><span>{item.message}</span>
            </button>)}
          </div>)}
        </div>
      </div>
      <button className={styles.dismiss} type="button" aria-label="Dismiss latest updates and mark as read" onClick={onDismiss}>×</button>
    </section>}
    <dialog ref={dialog} className={styles.dialog} onCancel={onClose} onClose={onClose} aria-labelledby="parent-update-title">
      {selected && <>
        <h2 id="parent-update-title">{selected.title}</h2>
        <p className={styles.date}>{selected.date ? new Date(selected.date).toLocaleString('en-IN') : ''}</p>
        <p className={styles.message}>{selected.message}</p>
        <button type="button" autoFocus onClick={onClose}>Close</button>
      </>}
    </dialog>
  </>;
}
