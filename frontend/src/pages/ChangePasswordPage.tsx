import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../api/client";
import { useSession } from "../auth/SessionProvider";
import { useToast } from "../components/Toast";
import { TextField } from "../components/form";
import { Banner, Button, Card, PageHeader } from "../components/primitives";

export function ChangePasswordPage() {
  const toast = useToast();
  const navigate = useNavigate();
  const { refresh, session } = useSession();

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});

  const mismatch = confirm.length > 0 && next !== confirm;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (mismatch) return;
    setSaving(true);
    setFormError(null);
    setFieldErrors({});
    try {
      await api.post("/api/auth/password/", { current_password: current, new_password: next });
      toast.success("Your password has been changed.");
      await refresh();
      navigate("/");
    } catch (caught) {
      if (caught instanceof ApiError) {
        setFieldErrors(caught.fieldErrors());
        if (Object.keys(caught.fieldErrors()).length === 0) setFormError(caught.message);
      } else {
        setFormError("Could not change the password. Check your connection and try again.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <PageHeader title="Change password" description={session?.user.email} />

      {session?.must_change_password ? (
        <Banner tone="warning" title="A new password is required">
          This account is still using the password it was created with.
        </Banner>
      ) : null}
      {formError ? <Banner tone="error">{formError}</Banner> : null}

      <Card>
        <TextField
          label="Current password"
          type="password"
          autoComplete="current-password"
          required
          value={current}
          errors={fieldErrors.current_password}
          onChange={(event) => setCurrent(event.target.value)}
        />
        <TextField
          label="New password"
          type="password"
          autoComplete="new-password"
          required
          hint="At least 12 characters, and not a password in common use."
          value={next}
          errors={fieldErrors.new_password}
          onChange={(event) => setNext(event.target.value)}
        />
        <TextField
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          required
          value={confirm}
          errors={mismatch ? ["The two passwords do not match."] : undefined}
          onChange={(event) => setConfirm(event.target.value)}
        />
        <Button
          type="submit"
          variant="primary"
          busy={saving}
          disabled={!current || !next || !confirm || mismatch}
        >
          Change password
        </Button>
      </Card>
    </form>
  );
}
