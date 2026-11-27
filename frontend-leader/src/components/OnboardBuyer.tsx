import { useState, type FormEvent } from "react";
import { UserPlus } from "lucide-react";
import { apiFetch } from "../api";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "./ui/dialog";

export function OnboardBuyer({
  messageId,
  leaderId,
  onComplete,
}: {
  messageId: string;
  leaderId: string;
  onComplete: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await apiFetch(`/api/leader/quarantine/${messageId}/onboard-buyer`, {
        method: "POST",
        headers: { "X-Leader-Id": leaderId },
        body: JSON.stringify({ leader_id: leaderId, name: name.trim(), phone: phone.trim() }),
      });
      setOpen(false);
      onComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not onboard buyer.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="primary">
          <UserPlus size={16} />
          Onboard buyer
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>Onboard buyer</DialogTitle>
        <DialogDescription>
          Confirm the sender’s details to release this message from quarantine.
        </DialogDescription>
        <form className="form-stack" onSubmit={submit}>
          <label className="field">
            Buyer name
            <input required value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field">
            Phone number
            <input type="tel" required value={phone} onChange={(e) => setPhone(e.target.value)} />
          </label>
          {error && (
            <p className="error-box" role="alert">
              {error}
            </p>
          )}
          <Button variant="primary" type="submit" disabled={busy || !name.trim() || !phone.trim()}>
            Confirm buyer
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
