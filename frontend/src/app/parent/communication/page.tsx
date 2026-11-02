'use client';

import { useState, useEffect, useRef, useCallback, useMemo, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import TopBar from '@/components/TopBar';
import MicBtn from '@/components/MicBtn';
import SpeakBtn from '@/components/SpeakBtn';
import { useDashboard } from '@/lib/DashboardContext';
import { useTranslation, useSpeechInput, useTTS } from '@/lib/multilingual';
import {
  fetchConversations,
  fetchConversationMessages,
  sendConversationMessage,
  createConversation,
  fetchConversationRecipients,
} from '@/lib/api';
import {
  ChatBubbleLeftRightIcon,
  PlusIcon,
  MagnifyingGlassIcon,
  PaperAirplaneIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';

// ── Types ─────────────────────────────────────────────────────────────────

interface Conversation {
  conv_id: number;
  subject: string;
  category: string;
  recipient_name: string;
  status: string;
  created_at: string;
  updated_at: string;
  latest_message: string | null;
  latest_message_time: string | null;
  latest_sender: string | null;
  unread_count: number;
}

interface Message {
  message_id: number;
  conv_id: number;
  sender_type: string;   // PARENT | TEACHER
  sender_name: string;
  message: string;
  created_at: string;
  is_read: boolean;
}

interface Recipient {
  teacher_id: number | null;
  name: string;
  role: string;
}

// ── Constants ─────────────────────────────────────────────────────────────

const CATEGORIES = [
  'Academic',
  'Leave Request',
  'Homework',
  'Behavior',
  'Exam / Test',
  'General Enquiry',
  'PTM Request',
  // 'Transport' and 'Fees' removed — no corresponding backend teacher/dept entries
  // 'Attendance'          removed — attendance module removed from portal
  // 'Leave Clarification' removed — consolidated into Leave Request
];

const CATEGORY_COLOR: Record<string, string> = {
  'Academic':        'bg-blue-100 text-blue-700',
  'Leave Request':   'bg-teal-100 text-teal-700',
  'Homework':        'bg-purple-100 text-purple-700',
  'Behavior':        'bg-orange-100 text-orange-700',
  'Exam / Test':     'bg-red-100 text-red-600',
  'General Enquiry': 'bg-gray-100 text-gray-600',
  'PTM Request':     'bg-pink-100 text-pink-700',
};

const FILTER_TABS = ['All', 'Unread', 'Academic', 'Leave Request', 'General Enquiry'];

// ── Helpers ───────────────────────────────────────────────────────────────

function timeAgo(iso: string | null): string {
  if (!iso) return '';
  try {
    const diff  = Date.now() - new Date(iso).getTime();
    const mins  = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days  = Math.floor(diff / 86400000);
    if (mins < 1)   return 'Just now';
    if (mins < 60)  return `${mins}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7)   return `${days}d ago`;
    return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
  } catch { return ''; }
}

function msgTime(iso: string): string {
  if (!iso) return '';
  try {
    const d   = new Date(iso);
    const now = new Date();
    const sameDay =
      d.getDate() === now.getDate() &&
      d.getMonth() === now.getMonth() &&
      d.getFullYear() === now.getFullYear();
    if (sameDay)
      return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
    return (
      d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) +
      ' · ' +
      d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
    );
  } catch { return ''; }
}

function initials(name: string): string {
  return name
    .split(' ')
    .slice(0, 2)
    .map(w => w[0])
    .join('')
    .toUpperCase();
}

function categoryBadge(cat: string) {
  const cls = CATEGORY_COLOR[cat] ?? 'bg-gray-100 text-gray-600';
  return (
    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${cls}`}>
      {cat}
    </span>
  );
}

// ── Conversation List Item ─────────────────────────────────────────────────

function ConvItem({
  conv,
  selected,
  displaySubject,
  displayPreview,
  onClick,
}: {
  conv: Conversation;
  selected: boolean;
  displaySubject?: string;
  displayPreview?: string;
  onClick: () => void;
}) {
  const isParentLast = conv.latest_sender === 'PARENT';
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-3 rounded-xl transition-all border ${
        selected
          ? 'bg-orange-500/10 border-orange-500/40'
          : 'bg-transparent border-transparent hover:bg-white/10'
      }`}
    >
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center text-white text-xs font-black shrink-0 mt-0.5">
          {initials(conv.recipient_name)}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex justify-between items-center gap-1">
            <p className="text-sm font-semibold text-white truncate">
              {conv.recipient_name}
            </p>
            <span className="text-[10px] text-slate-500 shrink-0">
              {timeAgo(conv.latest_message_time ?? conv.updated_at)}
            </span>
          </div>
          <p className="text-xs text-slate-400 truncate mt-0.5">
            {displaySubject ?? conv.subject}
          </p>
          <div className="flex items-center justify-between mt-1 gap-2">
            <p
              className={`text-[11px] truncate flex-1 ${
                conv.unread_count > 0 ? 'font-semibold text-white' : 'text-slate-500'
              }`}
            >
              {isParentLast ? 'You: ' : ''}
              {displayPreview ?? conv.latest_message ?? 'No messages yet'}
            </p>
            {conv.unread_count > 0 && (
              <span className="w-4 h-4 rounded-full bg-orange-500 text-white text-[9px] font-black flex items-center justify-center shrink-0">
                {conv.unread_count}
              </span>
            )}
          </div>
        </div>
      </div>
    </button>
  );
}

// ── Message Bubble ─────────────────────────────────────────────────────────

function MessageBubble({
  msg,
  displayText,
  speaking,
  fallback = false,
  onSpeak,
}: {
  msg: Message;
  displayText: string;
  speaking: string | null;
  fallback?: boolean;
  onSpeak: () => void;
}) {
  const isParent = msg.sender_type === 'PARENT';
  const ttsKey   = `msg_${msg.message_id}`;
  return (
    <div className={`flex flex-col ${isParent ? 'items-end' : 'items-start'} mb-4`}>
      <div className={`flex items-center gap-1.5 mb-1 ${isParent ? 'flex-row-reverse' : ''}`}>
        <div
          className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-black text-white shrink-0 ${
            isParent ? 'bg-gray-700' : 'bg-orange-500'
          }`}
        >
          {initials(msg.sender_name)}
        </div>
        <span className="text-[11px] font-semibold text-slate-400">{msg.sender_name}</span>
        <span className="text-[10px] text-slate-600">·</span>
        <span className="text-[10px] text-slate-500">{msgTime(msg.created_at)}</span>
        <SpeakBtn
          textKey={ttsKey}
          speaking={speaking}
          fallback={fallback}
          onSpeak={onSpeak}
        />
      </div>

      <div
        className={`max-w-[78%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
          isParent
            ? 'bg-slate-700 text-white rounded-tr-sm'
            : 'bg-orange-500/15 text-orange-100 border border-orange-500/20 rounded-tl-sm'
        }`}
      >
        <p className="whitespace-pre-wrap">{displayText}</p>
      </div>
    </div>
  );
}

// ── Start Conversation Modal ────────────────────────────────────────────────

function NewConversationModal({
  studentId,
  parentId,
  language,
  recipients,
  prefilledSubject = '',
  prefilledCategory = 'Academic',
  prefilledRecipient = null,
  onClose,
  onCreate,
}: {
  studentId: number;
  parentId: number;
  language: string;
  recipients: Recipient[];
  prefilledSubject?: string;
  prefilledCategory?: string;
  prefilledRecipient?: Recipient | null;
  onClose: () => void;
  onCreate: (conv: Conversation) => void;
}) {
  const [recipient,   setRecipient]   = useState<Recipient | null>(prefilledRecipient);
  const [category,    setCategory]    = useState(prefilledCategory || 'Academic');
  const [subject,     setSubject]     = useState(prefilledSubject || '');
  const [firstMsg,    setFirstMsg]    = useState('');
  const [leaveFrom,   setLeaveFrom]   = useState('');
  const [leaveTo,     setLeaveTo]     = useState('');
  const [submitting,  setSubmitting]  = useState(false);
  const [error,       setError]       = useState('');

  const { activeField, startFor } = useSpeechInput(language);

  const isLeaveRequest = category === 'Leave Request';

  const buildFirstMessage = (): string => {
    if (!isLeaveRequest) return firstMsg.trim();
    const parts: string[] = [];
    if (leaveFrom && leaveTo) {
      parts.push(`Leave period: ${leaveFrom} to ${leaveTo}.`);
    } else if (leaveFrom) {
      parts.push(`Leave date: ${leaveFrom}.`);
    }
    if (firstMsg.trim()) parts.push(firstMsg.trim());
    return parts.join('\n');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const finalMsg = buildFirstMessage();
    if (!recipient || !subject.trim() || !finalMsg) {
      setError('Please fill all required fields.');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const conv = await createConversation({
        student_id:     studentId,
        parent_id:      parentId,
        subject:        subject.trim(),
        category,
        recipient_name: recipient.name,
        // The picker already resolved a real user id; send it. Without it the
        // conversation can only be matched to a teacher by name, and a name is
        // not identity.
        recipient_user_id: recipient.teacher_id,
        first_message:  finalMsg,
      });
      onCreate(conv);
    } catch {
      setError('Failed to start conversation. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const subjectPlaceholder = isLeaveRequest
    ? 'e.g. Riya Sharma Leave Request'
    : 'e.g. Question about last week\'s Mathematics homework';

  const msgPlaceholder = isLeaveRequest
    ? 'Describe the reason for leave (e.g. Medical appointment, Family function…)'
    : 'Write your message here…';

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
      <div className="bg-slate-800 border border-white/10 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-center px-6 py-4 border-b border-white/10 shrink-0">
          <div>
            <h3 className="font-bold text-white">Start a Conversation</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Reach out to a teacher or school department
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto">
          {/* Select recipient */}
          <div>
            <label className="text-xs font-semibold text-slate-400 block mb-2">
              Who would you like to contact?
            </label>
            <div className="max-h-40 overflow-y-auto space-y-1.5 border border-white/10 rounded-xl p-2">
              {recipients.length === 0 ? (
                <p className="text-sm text-slate-400 text-center py-4">Loading…</p>
              ) : (
                recipients.map((r, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => setRecipient(r)}
                    className={`w-full text-left flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all ${
                      recipient?.name === r.name
                        ? 'bg-orange-500/10 border border-orange-500/40'
                        : 'hover:bg-white/10 border border-transparent'
                    }`}
                  >
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center text-white text-[11px] font-black shrink-0">
                      {initials(r.name)}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-white">{r.name}</p>
                      <p className="text-[11px] text-slate-400">{r.role}</p>
                    </div>
                    {recipient?.name === r.name && (
                      <span className="ml-auto text-orange-500 text-base">✓</span>
                    )}
                  </button>
                ))
              )}
            </div>
          </div>

          {/* Category */}
          <div>
            <label className="text-xs font-semibold text-slate-400 block mb-1.5">
              Category
            </label>
            <select
              value={category}
              onChange={e => setCategory(e.target.value)}
              className="w-full border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white outline-none focus:border-orange-400 bg-slate-700"
            >
              {CATEGORIES.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          {/* Leave date range — shown only for Leave Request */}
          {isLeaveRequest && (
            <div className="bg-teal-50 border border-teal-100 rounded-xl p-4 space-y-3">
              <p className="text-xs font-semibold text-teal-700">
                Leave Period{' '}
                <span className="text-gray-400 font-normal">(optional)</span>
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-400 block mb-1">From Date</label>
                  <input
                    type="date"
                    value={leaveFrom}
                    onChange={e => setLeaveFrom(e.target.value)}
                    className="w-full border border-white/10 rounded-xl px-3 py-2 text-sm text-white outline-none focus:border-teal-400 bg-slate-700"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-400 block mb-1">To Date</label>
                  <input
                    type="date"
                    value={leaveTo}
                    min={leaveFrom}
                    onChange={e => setLeaveTo(e.target.value)}
                    className="w-full border border-white/10 rounded-xl px-3 py-2 text-sm text-white outline-none focus:border-teal-400 bg-slate-700"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Subject */}
          <div>
            <label className="text-xs font-semibold text-slate-400 block mb-1.5">
              {isLeaveRequest ? 'Subject / Reference' : 'Topic / Subject'}{' '}
              <span className="text-red-400">*</span>
            </label>
            <div className="flex items-center gap-2">
              <input
                required
                type="text"
                value={subject}
                onChange={e => setSubject(e.target.value)}
                placeholder={subjectPlaceholder}
                className="flex-1 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white placeholder:text-slate-500 outline-none focus:border-orange-400 bg-slate-700"
              />
              <MicBtn
                fieldKey="modal-subject"
                activeField={activeField}
                onClick={() =>
                  startFor('modal-subject', text =>
                    setSubject(prev => (prev ? `${prev} ${text}` : text))
                  )
                }
              />
            </div>
          </div>

          {/* Message / Leave reason */}
          <div>
            <label className="text-xs font-semibold text-slate-400 block mb-1.5">
              {isLeaveRequest ? 'Leave Reason' : 'Your Message'}{' '}
              <span className="text-red-400">*</span>
            </label>
            <div className="flex items-end gap-2">
              <textarea
                required
                rows={4}
                value={firstMsg}
                onChange={e => setFirstMsg(e.target.value)}
                placeholder={msgPlaceholder}
                className="flex-1 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white placeholder:text-slate-500 outline-none focus:border-orange-400 bg-slate-700 resize-none"
              />
              <MicBtn
                fieldKey="modal-message"
                activeField={activeField}
                onClick={() =>
                  startFor('modal-message', text =>
                    setFirstMsg(prev => (prev ? `${prev} ${text}` : text))
                  )
                }
              />
            </div>
          </div>

          {error && (
            <p className="text-xs text-red-500 bg-red-50 border border-red-100 rounded-xl px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting || !recipient}
            className="w-full bg-orange-500 hover:bg-orange-600 disabled:bg-orange-200 text-white font-bold py-3 rounded-xl text-sm transition-colors"
          >
            {submitting
              ? 'Sending…'
              : isLeaveRequest
              ? 'Submit Leave Request'
              : 'Send Message'}
          </button>
        </form>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────

function CommunicationCenterInner() {
  const { studentId, setStudentId, parentId, parentName, language, setLanguage } = useDashboard();
  const searchParams = useSearchParams();

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoading,     setIsLoading]     = useState(true);
  const [selected,      setSelected]      = useState<Conversation | null>(null);
  const [messages,      setMessages]      = useState<Message[]>([]);
  const [msgLoading,    setMsgLoading]    = useState(false);
  const [reply,         setReply]         = useState('');
  const [sending,       setSending]       = useState(false);

  const [filter,     setFilter]     = useState('All');
  const [search,     setSearch]     = useState('');
  const [showModal,  setShowModal]  = useState(false);
  const [recipients, setRecipients] = useState<Recipient[]>([]);

  // Mobile: show either the list or the thread, not both side-by-side
  const [mobileView, setMobileView] = useState<'list' | 'thread'>('list');

  // Pre-fill values when navigating from assignments or quizzes
  const [prefilledSubject,   setPrefilledSubject]   = useState('');
  const [prefilledCategory,  setPrefilledCategory]  = useState('Academic');
  const [prefilledRecipient, setPrefilledRecipient] = useState<Recipient | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { activeField, startFor }  = useSpeechInput(language);
  const { speaking, speak, fallbackLang } = useTTS();

  // Stable source arrays for translation — only change when IDs change
  const convIdKey = useMemo(() => conversations.map(c => c.conv_id).join(','), [conversations]);
  const convSubjectTexts = useMemo(
    () => conversations.map(c => c.subject),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [convIdKey],
  );
  const convPreviewTexts = useMemo(
    () => conversations.map(c => c.latest_message ?? ''),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [convIdKey],
  );
  const msgIdKey = useMemo(() => messages.map(m => m.message_id).join(','), [messages]);
  const msgTexts = useMemo(
    () => messages.map(m => m.message),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [msgIdKey],
  );

  const { displayed: dispSubjects, translating: translatingConvs } = useTranslation(convSubjectTexts, language);
  const { displayed: dispPreviews }                                 = useTranslation(convPreviewTexts, language);
  const { displayed: msgTranslations, translating: translatingMsgs } = useTranslation(msgTexts, language);

  // Build conv_id → {subject, preview} map from translated parallel arrays
  const convTranslations = useMemo(() => {
    const map: Record<number, { subject: string; preview: string }> = {};
    conversations.forEach((c, i) => {
      map[c.conv_id] = {
        subject: dispSubjects[i] ?? c.subject,
        preview: dispPreviews[i] ?? c.latest_message ?? '',
      };
    });
    return map;
  }, [conversations, dispSubjects, dispPreviews]);

  // Load conversations — guard against firing before real IDs are available
  const loadConversations = useCallback(async () => {
    if (!studentId || !parentId) { setIsLoading(false); return; }
    setIsLoading(true);
    try {
      console.log('[SGS] CommunicationCenter: loading conversations for student', studentId, 'parent', parentId);
      const data = await fetchConversations(studentId, parentId);
      setConversations(data);
    } finally {
      setIsLoading(false);
    }
  }, [studentId, parentId]);

  useEffect(() => {
    setSelected(null);
    setMobileView('list');
    setMessages([]);
    if (studentId && parentId) {
      loadConversations();
    }
  }, [loadConversations, studentId, parentId]);

  // Auto-open a specific conversation from ?conv= URL param (e.g. from remarks page)
  useEffect(() => {
    const convParam = searchParams.get('conv');
    if (!convParam || conversations.length === 0) return;
    const targetId = Number(convParam);
    const target = conversations.find(c => c.conv_id === targetId);
    if (target) { setSelected(target); setMobileView('thread'); }
  }, [conversations, searchParams]);

  // Auto-open new conversation modal from ?new=1&subject=...&category=...&teacher_id=... (from assignments/quiz)
  useEffect(() => {
    const isNew     = searchParams.get('new') === '1';
    const subj      = searchParams.get('subject') ?? '';
    const cat       = searchParams.get('category') ?? 'Academic';
    const teacherId = searchParams.get('teacher_id');
    if (!isNew) return;
    setPrefilledSubject(subj);
    setPrefilledCategory(cat);

    const applyTeacher = (list: Recipient[]) => {
      if (teacherId) {
        const match = list.find(r => r.teacher_id === Number(teacherId));
        setPrefilledRecipient(match ?? null);
      } else {
        setPrefilledRecipient(null);
      }
    };

    if (recipients.length === 0) {
      fetchConversationRecipients(studentId).then(data => {
        setRecipients(data);
        applyTeacher(data);
        setShowModal(true);
      });
    } else {
      applyTeacher(recipients);
      setShowModal(true);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, studentId]);

  useEffect(() => {
    if (showModal && recipients.length === 0) {
      fetchConversationRecipients(studentId).then(setRecipients);
    }
  }, [showModal, studentId, recipients.length]);

  useEffect(() => {
    if (!selected) return;
    const load = async () => {
      setMsgLoading(true);
      try {
        const data = await fetchConversationMessages(selected.conv_id);
        setMessages(data);
      } finally {
        setMsgLoading(false);
      }
    };
    load();
  }, [selected]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reply.trim() || !selected || sending) return;
    setSending(true);
    try {
      const msg = await sendConversationMessage(
        selected.conv_id,
        'PARENT',
        parentName || 'Parent',
        reply.trim(),
      );
      setMessages(prev => [...prev, msg]);
      setReply('');
      setConversations(prev =>
        prev.map(c =>
          c.conv_id === selected.conv_id
            ? {
                ...c,
                latest_message: reply.trim(),
                latest_sender: 'PARENT',
                latest_message_time: new Date().toISOString(),
              }
            : c,
        ),
      );
    } finally {
      setSending(false);
    }
  };

  const handleConversationCreated = (conv: Conversation) => {
    setShowModal(false);
    setRecipients([]);
    // Reload full list so newly created conversation appears with correct metadata
    loadConversations().then(() => setSelected(conv));
  };

  const filtered = useMemo(() => conversations.filter(c => {
    if (filter === 'Unread' && c.unread_count === 0) return false;
    if (filter !== 'All' && filter !== 'Unread' && c.category !== filter) return false;
    const dispSubj = convTranslations[c.conv_id]?.subject ?? c.subject;
    if (
      search &&
      !dispSubj.toLowerCase().includes(search.toLowerCase()) &&
      !c.recipient_name.toLowerCase().includes(search.toLowerCase())
    )
      return false;
    return true;
  }), [conversations, filter, search, convTranslations]);

  return (
    <div className="min-h-full flex flex-col font-sans text-slate-200">
      <TopBar
        studentId={studentId}
        setStudentId={setStudentId}
        parentId={parentId}
        language={language}
        setLanguage={setLanguage}
        isLoading={isLoading}
      />

      {/* Two-panel layout */}
      <div className="flex-1 flex overflow-hidden" style={{ height: 'calc(100vh - 72px)' }}>

        {/* ── LEFT PANEL: Conversation List ── */}
        <div className={`${mobileView === 'thread' ? 'hidden md:flex' : 'flex'} w-full md:w-80 shrink-0 bg-slate-900/50 border-r border-white/10 flex-col overflow-hidden`}>

          {/* Header */}
          <div className="px-4 pt-4 pb-3 border-b border-white/10">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <ChatBubbleLeftRightIcon className="w-5 h-5 text-orange-500" />
                <h2 className="font-bold text-white text-sm">Communication Center</h2>
              </div>
              <button
                onClick={() => setShowModal(true)}
                className="w-7 h-7 rounded-lg bg-orange-500 hover:bg-orange-600 text-white flex items-center justify-center transition-colors"
                title="Start Conversation"
              >
                <PlusIcon className="w-4 h-4" />
              </button>
            </div>

            {/* Search */}
            <div className="relative mb-2.5">
              <MagnifyingGlassIcon className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search conversations…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-white/5 border border-white/10 rounded-xl text-xs text-white placeholder:text-slate-500 outline-none focus:border-orange-400 transition-all"
              />
            </div>

            {/* Filter tabs */}
            <div className="flex gap-1 overflow-x-auto pb-0.5">
              {FILTER_TABS.map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`text-[11px] font-semibold px-2.5 py-1 rounded-lg whitespace-nowrap transition-colors ${
                    filter === f ? 'bg-orange-600 text-white' : 'text-slate-400 hover:bg-white/10'
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          {/* Conversation list */}
          <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
            {isLoading ? (
              <div className="flex justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-400" />
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center px-4">
                <ChatBubbleLeftRightIcon className="w-10 h-10 text-slate-600 mb-3" />
                <p className="text-sm font-semibold text-slate-400">No conversations yet</p>
                <p className="text-xs text-slate-500 mt-1">Start one using the + button above</p>
              </div>
            ) : (
              filtered.map(c => (
                <ConvItem
                  key={c.conv_id}
                  conv={c}
                  selected={selected?.conv_id === c.conv_id}
                  displaySubject={convTranslations[c.conv_id]?.subject}
                  displayPreview={convTranslations[c.conv_id]?.preview || undefined}
                  onClick={() => { setSelected(c); setMobileView('thread'); }}
                />
              ))
            )}
          </div>
        </div>

        {/* ── RIGHT PANEL: Thread ── */}
        <div className={`${mobileView === 'list' ? 'hidden md:flex' : 'flex'} flex-1 flex-col overflow-hidden`}>
          {!selected ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
              <ChatBubbleLeftRightIcon className="w-14 h-14 text-slate-600 mb-4" />
              <h3 className="text-base font-bold text-slate-400">Select a conversation</h3>
              <p className="text-sm text-slate-500 mt-1 max-w-xs">
                Choose a conversation from the left panel to view messages and reply.
              </p>
              <button
                onClick={() => setShowModal(true)}
                className="mt-5 inline-flex items-center gap-2 bg-orange-500 hover:bg-orange-600 text-white text-sm font-bold px-5 py-2.5 rounded-xl transition-colors"
              >
                <PlusIcon className="w-4 h-4" />
                Start a Conversation
              </button>
            </div>
          ) : (
            <>
              {/* Thread header */}
              <div className="px-5 py-4 border-b border-white/10 bg-slate-900/30 shrink-0">
                {/* Back button — mobile only */}
                <button
                  onClick={() => setMobileView('list')}
                  className="md:hidden flex items-center gap-1.5 text-xs font-semibold text-orange-400 hover:text-orange-300 mb-3 transition-colors"
                >
                  <span>←</span> All Conversations
                </button>
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center text-white text-sm font-black shrink-0">
                    {initials(selected.recipient_name)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-bold text-white text-sm">
                        {selected.recipient_name}
                      </h3>
                      {categoryBadge(selected.category)}
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          selected.status === 'OPEN'
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-500'
                        }`}
                      >
                        {selected.status}
                      </span>
                      {translatingMsgs && (
                        <span className="text-[10px] text-orange-400 font-semibold flex items-center gap-1">
                          <span className="w-2.5 h-2.5 rounded-full border border-orange-400 border-t-transparent animate-spin inline-block" />
                          Translating…
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5 truncate">
                      {convTranslations[selected.conv_id]?.subject ?? selected.subject}
                    </p>
                  </div>
                </div>
              </div>

              {/* Messages area */}
              <div className="flex-1 overflow-y-auto px-5 py-4">
                {msgLoading ? (
                  <div className="flex justify-center py-12">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-400" />
                  </div>
                ) : messages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-center">
                    <p className="text-sm text-slate-400">No messages yet.</p>
                    <p className="text-xs text-slate-500 mt-1">Send the first message below.</p>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center gap-3 mb-6">
                      <div className="flex-1 h-px bg-white/10" />
                      <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wide">
                        {new Date(messages[0].created_at).toLocaleDateString('en-IN', {
                          day: '2-digit',
                          month: 'short',
                          year: 'numeric',
                        })}
                      </span>
                      <div className="flex-1 h-px bg-white/10" />
                    </div>
                    {messages.map((m, i) => {
                      const dispText  = msgTranslations[i] ?? m.message;
                      const ttsKey    = `msg_${m.message_id}`;
                      const isFallback = !!fallbackLang && speaking === ttsKey;
                      return (
                        <MessageBubble
                          key={m.message_id}
                          msg={m}
                          displayText={dispText}
                          speaking={speaking}
                          fallback={isFallback}
                          onSpeak={() => speak(dispText, language, ttsKey)}
                        />
                      );
                    })}
                    <div ref={messagesEndRef} />
                  </>
                )}
              </div>

              {/* Reply input with voice button */}
              <div className="px-4 py-3 border-t border-white/10 bg-slate-900/30 shrink-0">
                <form onSubmit={handleSend} className="flex gap-2 items-end">
                  <textarea
                    rows={2}
                    value={reply}
                    onChange={e => setReply(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSend(e as any);
                      }
                    }}
                    placeholder="Write a message to the teacher…"
                    className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder:text-slate-500 outline-none focus:border-orange-400 resize-none transition-all"
                  />
                  <MicBtn
                    fieldKey="reply"
                    activeField={activeField}
                    onClick={() =>
                      startFor('reply', text =>
                        setReply(prev => (prev ? `${prev} ${text}` : text))
                      )
                    }
                  />
                  <button
                    type="submit"
                    disabled={!reply.trim() || sending}
                    className="w-10 h-10 rounded-xl bg-orange-500 hover:bg-orange-600 disabled:bg-orange-200 text-white flex items-center justify-center transition-colors shrink-0"
                  >
                    <PaperAirplaneIcon className="w-4 h-4" />
                  </button>
                </form>
                <p className="text-[10px] text-slate-600 mt-1.5 ml-1">
                  Press Enter to send · Shift+Enter for new line
                </p>
              </div>
            </>
          )}
        </div>
      </div>

      {/* New conversation modal */}
      {showModal && (
        <NewConversationModal
          studentId={studentId}
          parentId={parentId}
          language={language}
          recipients={recipients}
          prefilledSubject={prefilledSubject}
          prefilledCategory={prefilledCategory}
          prefilledRecipient={prefilledRecipient}
          onClose={() => {
            setShowModal(false);
            setRecipients([]);
            setPrefilledSubject('');
            setPrefilledCategory('Academic');
            setPrefilledRecipient(null);
          }}
          onCreate={handleConversationCreated}
        />
      )}
    </div>
  );
}

export default function CommunicationCenterPage() {
  return (
    <Suspense fallback={
      <div className="flex justify-center items-center h-screen">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-orange-500" />
      </div>
    }>
      <CommunicationCenterInner />
    </Suspense>
  );
}
