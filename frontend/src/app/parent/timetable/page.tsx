'use client';

import { useEffect, useState } from 'react';
import TopBar from '@/components/TopBar';
import { api } from '@/lib/api';
import { useDashboard } from '@/lib/DashboardContext';
import styles from './timetable.module.css';

type Period = { period_id: number; period_no: number; period_label: string; start_time: string; end_time: string; is_teaching: boolean };
type Slot = { period_no: number; subject_name: string; teacher_name: string | null };
type Timetable = {
  student: { full_name: string; class_name: string }; section: string;
  academic_year: string | null; academic_years: string[]; schedule_types: string[];
  periods: Period[]; days: { day_of_week: number; day_name: string; slots: Slot[] }[];
  has_slots: boolean; message: string | null;
};
const time = (value: string) => value?.slice(0, 5) || '';

export default function TimetablePage() {
  const { studentId, setStudentId, parentId, language, setLanguage } = useDashboard();
  const [result, setResult] = useState<{ studentId: number; data: Timetable } | null>(null);
  const [year, setYear] = useState('');
  const [schedule, setSchedule] = useState('full');
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const data = result?.studentId === studentId ? result.data : null;

  useEffect(() => {
    if (!parentId || !studentId) return;
    const controller = new AbortController();
    setLoading(true);
    setError('');
    setResult(null);
    api.get<Timetable>(`/timetable/${studentId}`, {
      params: { schedule_type: schedule, ...(year ? { academic_year: year } : {}) },
      signal: controller.signal,
    }).then(response => {
      if (!controller.signal.aborted) setResult({ studentId, data: response.data });
    }).catch(err => {
      if (!controller.signal.aborted) setError(typeof err.response?.data?.detail === 'string'
        ? err.response.data.detail : 'Unable to load the timetable. Please try again.');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [parentId, studentId, year, schedule, revision]);

  return <>
    <TopBar studentId={studentId} setStudentId={(id: number) => { setYear(''); setStudentId(id); }} parentId={parentId}
      language={language} setLanguage={setLanguage} isLoading={loading} />
    <main className={styles.page}>
      <h1>Student Timetable</h1>
      <p>View the weekly schedule for your selected child.</p>
      {data && <h2>{data.student.full_name} · {data.student.class_name} {data.section}</h2>}
      <div className={styles.controls}>
        <label>Academic year<select value={year || data?.academic_year || ''} onChange={e => setYear(e.target.value)}>
          {!data?.academic_years.length && <option value="">No academic years available</option>}
          {data?.academic_years.map(value => <option key={value} value={value}>{value}</option>)}
        </select></label>
        <label>Schedule<select value={schedule} onChange={e => setSchedule(e.target.value)}>
          <option value="full">Full day</option><option value="half">Half day</option>
        </select></label>
        <button disabled={loading || !studentId || !parentId} onClick={() => setRevision(n => n + 1)}>Refresh</button>
      </div>
      {!parentId ? <p role="status">Please sign in to view your child&apos;s timetable.</p>
        : !studentId ? <p role="status">Select a child above to view their timetable.</p>
        : loading ? <p role="status">Loading timetable…</p>
        : error ? <p className={styles.error} role="alert">{error}</p>
        : data && <>
          {!data.has_slots && <p role="status">{data.message}</p>}
          {data.periods.length > 0 ? <div className={styles.scroll} tabIndex={0} aria-label="Weekly timetable, scroll horizontally for more periods">
            <table><caption>{data.academic_year} · {schedule === 'full' ? 'Full day' : 'Half day'} schedule</caption>
              <thead><tr><th scope="col">Day</th>{data.periods.map(period => <th key={period.period_id} scope="col">
                {period.period_label}<small>{time(period.start_time)}–{time(period.end_time)}</small>
              </th>)}</tr></thead>
              <tbody>{data.days.map(day => <tr key={day.day_of_week}><th scope="row">{day.day_name}</th>
                {data.periods.map(period => {
                  const slot = day.slots.find(item => item.period_no === period.period_no);
                  return <td key={period.period_id} className={!period.is_teaching ? styles.break : undefined}>
                    {!period.is_teaching ? period.period_label : slot ? <><strong>{slot.subject_name}</strong><small>{slot.teacher_name || 'Teacher not assigned'}</small></> : <span className={styles.free}>Free period</span>}
                  </td>;
                })}</tr>)}</tbody>
            </table>
          </div> : <p>No period timings are available for this schedule.</p>}
        </>}
    </main>
  </>;
}
