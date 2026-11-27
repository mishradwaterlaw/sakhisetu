import { useEffect, useState } from "react";
import { Volume2, Users, User, AlertTriangle } from "lucide-react";
import { apiFetch } from "../api";

interface MemberSummary {
  id: string;
  name: string;
  preferred_language: string;
}

interface MemberRecord {
  member: { id: string; name: string; preferred_language: string; default_channel: string };
  balance_inr: number;
  ledger_entries: { id: string; payout_batch_id: string; amount_inr: number; description: string; is_disbursed: boolean }[];
  assignments: { id: string; step_name: string; assigned_units: number; passed_units: number; status: string }[];
  private_coaching_notes: { qc_check_id: string; outcome: string; coaching_note: string }[];
  replayable_messages: { id: string; category: string; language: string; fact: string; action: string; request: string }[];
}

/** Member Self-Service & Replayable Read-Back (§1, §7, §12). */
export function MemberView({ members, initialId }: { members: MemberSummary[]; initialId?: string | null }) {
  const [selectedId, setSelectedId] = useState(members.find(m => m.id === initialId)?.id || members[0]?.id || "");
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [record, setRecord] = useState<MemberRecord | null>(null);

  useEffect(() => {
    if (!selectedId && members.length > 0) setSelectedId(members[0].id);
  }, [members, selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    setRecord(null); setError("");
    apiFetch<MemberRecord>(`/api/member/${selectedId}/record`, {
      headers: { "X-Member-Id": selectedId },
    })
      .then(result => { if (active) setRecord(result); })
      .catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [selectedId, revision]);

  function speakReadback(text: string, lang: string) {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utt = new SpeechSynthesisUtterance(text);
    utt.lang = lang === "kn" ? "kn-IN" : lang === "hi" ? "hi-IN" : "en-IN";
    window.speechSynthesis.speak(utt);
  }

  return (
    <section className="member-panel space-y-4">
      <div className="bg-white border border-[var(--border-neutral)] rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Member record</h2>
          <p className="text-xs text-slate-600">Every member can view or hear her own work &amp; pay record anytime.</p>
        </div>
        <select
          aria-label="Select member"
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          className="px-3 py-2 border border-[var(--border-neutral)] rounded-lg font-semibold text-sm bg-white"
        >
          {members.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name} ({m.preferred_language.toUpperCase()})
            </option>
          ))}
        </select>
      </div>

      {error && <div role="alert" className="error-box">{error}<button onClick={() => setRevision(v => v + 1)}>Retry</button></div>}
      {!selectedId && <p className="quiet">No active members in this group.</p>}
      {selectedId && !record && !error && <p aria-busy="true" className="quiet">Loading member record…</p>}
      {record && (
        <>
          <div className="bg-[var(--brand-dark)] text-white rounded-xl p-5 flex items-center justify-between">
            <div>
              <div className="text-xs uppercase tracking-wider text-rose-100">Disbursed balance</div>
              <div className="text-3xl font-extrabold mt-1">₹{record.balance_inr.toFixed(2)}</div>
            </div>
            <button
              type="button"
              onClick={() =>
                speakReadback(
                  `${record.member.name}, your verified balance is ${record.balance_inr} rupees.`,
                  record.member.preferred_language
                )
              }
              className="flex items-center gap-2 bg-white text-[var(--brand-dark)] px-4 py-3 rounded-lg font-bold text-sm"
            >
              <Volume2 className="w-5 h-5" />
              <span>Hear Balance</span>
            </button>
          </div>

          <div className="bg-white border border-slate-300 rounded-xl p-4 space-y-3">
            <h3 className="text-sm font-bold uppercase tracking-wide text-slate-700">
              Replayable Notices &amp; Earnings Read-Backs
            </h3>
            {record.replayable_messages.length === 0 ? (
              <p className="text-sm text-slate-500">No notices recorded yet.</p>
            ) : (
              record.replayable_messages.map((msg) => {
                const isGroup = msg.category.startsWith("GROUP_");
                return (
                  <div
                    key={msg.id}
                    className={`p-3.5 rounded-lg border-2 ${
                      isGroup ? "border-indigo-300 bg-indigo-50" : "border-teal-300 bg-teal-50"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <span className="inline-flex items-center gap-1.5 text-xs font-extrabold uppercase">
                        {isGroup ? <Users className="w-4 h-4 text-indigo-800" /> : <User className="w-4 h-4 text-teal-800" />}
                        <span>{isGroup ? "GROUP DECISION" : "YOUR INDIVIDUAL RECORD"}</span>
                      </span>
                      <button
                        type="button"
                        onClick={() => speakReadback(`${msg.fact} ${msg.action} ${msg.request}`, msg.language)}
                        className="inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded bg-white border border-slate-300"
                      >
                        <Volume2 className="w-3.5 h-3.5" />
                        <span>Replay</span>
                      </button>
                    </div>
                    <p className="text-sm font-semibold text-slate-900">{msg.fact}</p>
                    <p className="text-xs text-slate-700 mt-1">{msg.action}</p>
                    <p className="text-xs font-semibold text-slate-800 mt-1">{msg.request}</p>
                  </div>
                );
              })
            )}
          </div>

          {record.private_coaching_notes.length > 0 && (
            <div className="bg-amber-50 border border-amber-300 rounded-xl p-4 space-y-2">
              <div className="flex items-center gap-2 text-amber-950 font-bold text-sm">
                <AlertTriangle className="w-4 h-4" />
                <span>Private Coaching Notes (Visible Only to You)</span>
              </div>
              {record.private_coaching_notes.map((n) => (
                <p key={n.qc_check_id} className="text-sm text-amber-900">
                  {n.coaching_note}
                </p>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}
