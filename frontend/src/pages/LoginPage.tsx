import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError } from "../api/client";
import { useSession } from "../auth/SessionProvider";
import { TextField } from "../components/form";
import { Banner, Button } from "../components/primitives";

export function LoginPage() {
  const { signIn } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password);
    } catch (caught) {
      // The API deliberately does not say whether the address exists; the
      // message shown here is the one it returned.
      setError(
        caught instanceof ApiError ? caught.message : "Could not sign in. Check your connection and try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="signin">
      <form className="signin__card" onSubmit={handleSubmit} noValidate>
        <div className="signin__brand">
          <span className="nav__mark" aria-hidden="true">
            ZS
          </span>
          <div>
            <h1>Sign in</h1>
            <p className="page-header__sub">Ztech Sales</p>
          </div>
        </div>

        {error ? <Banner tone="error">{error}</Banner> : null}

        <TextField
          label="Email address"
          type="email"
          name="email"
          autoComplete="username"
          required
          autoFocus
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <TextField
          label="Password"
          type="password"
          name="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />

        <Button type="submit" variant="primary" busy={busy} disabled={!email || !password}>
          Sign in
        </Button>
      </form>
    </div>
  );
}
