"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../../api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api.authLogin({ email: email.trim(), password });
      router.replace("/health");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to sign in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[75vh] max-w-md items-center px-4 py-10">
      <section className="card w-full space-y-6 p-6 sm:p-8">
        <div className="space-y-2">
          <p className="eyebrow">WELCOME BACK</p>
          <h1 className="text-3xl font-semibold text-ink">Sign in to CuraMind</h1>
          <p className="text-sm leading-6 text-muted">
            Access your saved health profile, medical records and family information.
          </p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <label className="block space-y-1.5">
            <span className="text-sm font-medium text-ink">Email address</span>
            <input
              className="input w-full"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
          </label>

          <label className="block space-y-1.5">
            <span className="text-sm font-medium text-ink">Password</span>
            <input
              className="input w-full"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
            />
          </label>

          {error && <p role="alert" className="text-sm text-red-600">{error}</p>}

          <button className="btn btn-primary w-full" type="submit" disabled={busy}>
            {busy ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="text-center text-sm text-muted">
          New to CuraMind?{" "}
          <Link href="/register" className="font-semibold text-brand-strong underline">
            Create an account
          </Link>
        </p>
        <p className="text-center text-sm">
          <Link href="/" className="text-muted underline">Back to home</Link>
        </p>
      </section>
    </div>
  );
}
