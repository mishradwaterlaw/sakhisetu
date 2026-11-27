import { useState } from "react";
import { CheckCircle2, UserCheck } from "lucide-react";
import { apiFetch } from "../api";

/** JanAI Café Assisted-Entry View (§3, §12): large touch targets, fewer steps, explicit consent. */
export function CafeView({ shgId, onSubmitted }: { shgId: string; onSubmitted: () => void }) {
  const [memberPhone, setMemberPhone] = useState("+919800000004");
  const [intent, setIntent] = useState("BLOCKER_REPORT");
  const [notes, setNotes] = useState("");
  const [consented, setConsented] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    setResult(null);
    try {
      const res = await apiFetch<{ status: string; trace_id: string }>("/api/webhooks/janai-cafe", {
        method: "POST",
        body: JSON.stringify({
          shg_id: shgId,
          member_phone: memberPhone,
          intent_override: intent,
          notes_text: notes,
          operator_id: "janai_cafe_operator_1",
          member_consented: consented,
        }),
      });
      setResult(`Recorded (${res.status}) • Trace ${res.trace_id}`);
      setNotes("");
      onSubmitted();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to submit");
    }
  }

  return (
    <section className="max-w-xl mx-auto bg-[var(--bg-surface)] border-2 border-[var(--border-neutral)] rounded p-4 space-y-4">
      <div className="flex items-center gap-2 border-b border-slate-200 pb-3">
        <UserCheck className="w-6 h-6 text-teal-800" />
        <div>
          <h2 className="text-lg font-bold text-slate-900">JanAI Café — Assisted Entry</h2>
          <p className="text-xs text-slate-600">For members without a phone. Always confirm member consent first.</p>
        </div>
      </div>

      <div className="space-y-2">
        <label className="block text-sm font-bold text-slate-800">1. Member Phone / ID</label>
        <input
          value={memberPhone}
          onChange={(e) => setMemberPhone(e.target.value)}
          className="w-full px-4 py-3 text-base border-2 border-slate-300 rounded-lg focus:border-teal-700 outline-none"
        />
      </div>

      <div className="space-y-2">
        <label className="block text-sm font-bold text-slate-800">2. What is the member reporting?</label>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {[
            { id: "NEW_ORDER", label: "New Order" },
            { id: "BLOCKER_REPORT", label: "Problem / Blocker" },
            { id: "FINISHED_WORK", label: "Finished Work" },
          ].map((opt) => (
            <button
              key={opt.id}
              type="button"
              onClick={() => setIntent(opt.id)}
              className={`py-3.5 px-3 rounded-lg border-2 text-sm font-bold transition ${
                intent === opt.id
                  ? "bg-teal-900 text-white border-teal-900"
                  : "bg-stone-50 text-slate-800 border-slate-300"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <label className="block text-sm font-bold text-slate-800">3. Details spoken by member</label>
        <textarea
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="e.g., Finished 15 cotton tote bags or sewing machine needle broke"
          className="w-full px-4 py-3 text-base border-2 border-slate-300 rounded-lg focus:border-teal-700 outline-none"
        />
      </div>

      <label className="flex items-start gap-3 p-3.5 bg-amber-50 border-2 border-amber-300 rounded-lg cursor-pointer">
        <input
          type="checkbox"
          checked={consented}
          onChange={(e) => setConsented(e.target.checked)}
          className="w-5 h-5 mt-0.5 accent-teal-900"
        />
        <span className="text-sm font-semibold text-amber-950">
          Member is physically present and gave explicit consent to log this entry on her behalf.
        </span>
      </label>

      {error && <div className="p-3 bg-rose-50 border border-rose-300 text-rose-900 rounded-lg text-sm font-semibold">{error}</div>}
      {result && (
        <div className="p-3 bg-emerald-50 border border-emerald-300 text-emerald-900 rounded-lg text-sm font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          <span>{result}</span>
        </div>
      )}

      <button
        type="button"
        onClick={submit}
        className="w-full py-3.5 bg-[#0F172A] hover:bg-[#1E293B] text-[#F8FAFC] type-scale-md rounded"
      >
        Submit Consented Entry
      </button>
    </section>
  );
}
