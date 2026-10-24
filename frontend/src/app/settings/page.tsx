"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useTranslation } from "react-i18next";
import {
  api,
  ApiRequestError,
  familyApi,
  FamilyMember,
  FamilyMemberFields,
  ActiveFamilyProfile,
  FamilyInvitation,
} from "@/api";

export default function SettingsPage() {
  const { t } = useTranslation();
  const [members, setMembers] = useState<FamilyMember[]>([]);
  const [active, setActive] = useState<ActiveFamilyProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [requiresSignIn, setRequiresSignIn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [invitations, setInvitations] = useState<FamilyInvitation[]>([]);
  const [invitePhone, setInvitePhone] = useState("");
  const [inviteRelationship, setInviteRelationship] = useState("");

  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [newPin, setNewPin] = useState("");
  const [dob, setDob] = useState("");
  const [sex, setSex] = useState("");
  const [bloodGroup, setBloodGroup] = useState("");

  const [selected, setSelected] = useState<FamilyMember | null>(null);
  const [pin, setPin] = useState("");
  const [accountPassword, setAccountPassword] = useState("");
  const [resetPin, setResetPin] = useState("");
  const [editName, setEditName] = useState("");

  const refresh = useCallback(async () => {
    const [list, current, pendingInvitations] = await Promise.all([
      familyApi.list(),
      familyApi.active(),
      familyApi.invitations(),
    ]);
    setMembers(list.members);
    setActive(current);
    setInvitations(pendingInvitations);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        await api.authMe();
        const [list, current, pendingInvitations] = await Promise.all([
          familyApi.list(),
          familyApi.active(),
          familyApi.invitations(),
        ]);
        if (!cancelled) {
          setMembers(list.members);
          setActive(current);
          setInvitations(pendingInvitations);
        }
      } catch (err) {
        if (!cancelled) {
          if (err instanceof ApiRequestError && err.status === 401) {
            setRequiresSignIn(true);
          } else {
            setError(
              err instanceof Error
                ? err.message
                : "Unable to load family settings."
            );
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  function clearNotices() {
    setError("");
    setMessage("");
  }

  async function handleCreateInvitation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearNotices();

    const phone = invitePhone.trim();
    const digits = phone.replace(/\D/g, "");
    if (!phone.startsWith("+") || digits.length < 8 || digits.length > 15) {
      setError("Enter an international phone number beginning with + and containing 8 to 15 digits.");
      return;
    }

    setBusy(true);
    try {
      const result = await familyApi.createInvitation({
        phone_number: phone,
        relationship_label: inviteRelationship.trim() || undefined,
      });
      setInvitePhone("");
      setInviteRelationship("");
      setInvitations((current) => [
        result,
        ...current.filter((invitation) => invitation.id !== result.id),
      ]);
      setMessage(
        result.message ||
          "Invitation saved as pending. No SMS was sent; phone verification is not enabled yet."
      );
      try {
        await refresh();
      } catch (refreshError) {
        setError(
          refreshError instanceof Error
            ? `Invitation was saved, but the list could not be refreshed: ${refreshError.message}`
            : "Invitation was saved, but the list could not be refreshed."
        );
      }
    } catch (err) {
      const saveError =
        err instanceof Error ? err.message : "Could not save the invitation.";
      if (err instanceof ApiRequestError && (err.status === 502 || err.status === 503)) {
        try {
          await refresh();
        } catch {
          setError(`${saveError} The saved invitation could not be reloaded.`);
          return;
        }
      }
      setError(saveError);
    } finally {
      setBusy(false);
    }
  }

  async function handleSendInvitation(invitation: FamilyInvitation) {
    clearNotices();
    setBusy(true);
    try {
      const result = await familyApi.sendInvitation(invitation.id);
      setInvitations((current) => current.map((item) =>
        item.id === result.id ? result : item
      ));
      setMessage(result.message || "Invitation SMS sent.");
      try {
        await refresh();
      } catch (refreshError) {
        setError(
          refreshError instanceof Error
            ? `SMS sent, but the invitation list could not be refreshed: ${refreshError.message}`
            : "SMS sent, but the invitation list could not be refreshed."
        );
      }
    } catch (err) {
      const sendError =
        err instanceof Error ? err.message : "Could not send the invitation.";
      if (err instanceof ApiRequestError && (err.status === 502 || err.status === 503)) {
        try {
          await refresh();
        } catch {
          setError(`${sendError} The saved invitation could not be reloaded.`);
          return;
        }
      }
      setError(sendError);
    } finally {
      setBusy(false);
    }
  }

  async function handleCancelInvitation(invitation: FamilyInvitation) {
    clearNotices();
    setBusy(true);
    try {
      await familyApi.cancelInvitation(invitation.id);
      await refresh();
      setMessage("Invitation cancelled.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not cancel the invitation.");
    } finally {
      setBusy(false);
    }
  }
  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearNotices();

    if (!name.trim()) {
      setError("Enter the family member's name.");
      return;
    }
    if (!/^\d{6}$/.test(newPin)) {
      setError("The PIN must contain exactly six digits.");
      return;
    }

    setBusy(true);
    try {
      const fields: FamilyMemberFields = {
        name: name.trim(),
        dob: dob || null,
        sex: sex || null,
        blood_group: bloodGroup || null,
      };

      const created = await familyApi.add({ ...fields, pin: newPin });
      setMembers((current) =>
        [...current, created].sort((left, right) => left.name.localeCompare(right.name))
      );

      setName("");
      setNewPin("");
      setDob("");
      setSex("");
      setBloodGroup("");
      setShowCreate(false);
      setMessage("Family profile created. The member must enter their PIN to open it.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the profile.");
    } finally {
      setBusy(false);
    }
  }

  async function handleUnlock(member: FamilyMember) {
    clearNotices();

    if (!/^\d{6}$/.test(pin)) {
      setError("Enter the six-digit PIN.");
      return;
    }

    setBusy(true);
    try {
      await familyApi.unlock(member.oid, pin);
      await refresh();
      setPin("");
      setSelected(null);
      setMessage(`${member.name}'s profile is now active.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not unlock this profile.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSwitchToOwner() {
    clearNotices();
    setBusy(true);
    try {
      await familyApi.switchToOwner();
      await refresh();
      setSelected(null);
      setPin("");
      setMessage("You are now using the main account profile.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not switch profiles.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSetPin(member: FamilyMember) {
    clearNotices();

    if (!/^\d{6}$/.test(pin)) {
      setError("Choose a PIN containing exactly six digits.");
      return;
    }

    setBusy(true);
    try {
      await familyApi.setPin(member.oid, pin);
      await refresh();
      setPin("");
      setSelected(null);
      setMessage(`A PIN has been set for ${member.name}. Enter it to unlock the profile.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not set the PIN.");
    } finally {
      setBusy(false);
    }
  }

  async function handleResetPin(member: FamilyMember) {
    clearNotices();

    if (!accountPassword) {
      setError("Enter your main account password.");
      return;
    }
    if (!/^\d{6}$/.test(resetPin)) {
      setError("The new PIN must contain exactly six digits.");
      return;
    }

    setBusy(true);
    try {
      await familyApi.resetPin(member.oid, accountPassword, resetPin);
      await refresh();
      setAccountPassword("");
      setResetPin("");
      setSelected(null);
      setMessage(`The PIN for ${member.name} has been reset.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reset the PIN.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveName(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !editName.trim()) {
      setError("Enter a name.");
      return;
    }

    clearNotices();
    setBusy(true);
    try {
      await familyApi.update(selected.oid, { name: editName.trim() });
      await refresh();
      setSelected(null);
      setMessage("Family profile details updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update the profile.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove(member: FamilyMember) {
    const confirmed = window.confirm(
      `Remove ${member.name} from this account? Their existing medical records will not be deleted.`
    );
    if (!confirmed) return;

    clearNotices();
    setBusy(true);
    try {
      await familyApi.remove(member.oid);
      await refresh();
      setSelected(null);
      setMessage(`${member.name} has been unlinked from this account.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove the profile.");
    } finally {
      setBusy(false);
    }
  }

  const isActiveMember = (member: FamilyMember) =>
    active?.type === "family" && active.active_profile.oid === member.oid;

  if (loading) {
    return <div className="card p-6 text-sm text-muted">Loading settings...</div>;
  }

  if (requiresSignIn) {
    return (
      <main className="card mx-auto mt-10 max-w-xl space-y-4 p-6">
        <h1 className="text-xl font-semibold">Sign in to manage family profiles</h1>
        <p className="text-sm leading-6 text-muted">
          Family profiles are securely linked to a registered account. Sign in or create an account before adding a family member.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link href="/login" className="btn btn-primary">Sign in</Link>
          <Link href="/register" className="btn btn-ghost">Create account</Link>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-5xl space-y-6">
      <header>
        <p className="eyebrow">Account</p>
        <h1 className="h-display mt-1 text-3xl font-semibold">{t("nav.familyAccess")}</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
          Manage family profiles and their access PINs. Each family member's
          medical information is kept separate.
        </p>
      </header>

      {error && (
        <p role="alert" className="rounded-xl border border-crit/30 bg-crit-soft px-4 py-3 text-sm text-crit">
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="rounded-xl border border-line bg-surface-2 px-4 py-3 text-sm">
          {message}
        </p>
      )}

      <section className="card space-y-4 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Active profile</h2>
            <p className="mt-1 text-sm text-muted">
              {active?.type === "family"
                ? `Currently using ${active.active_profile.name}'s profile.`
                : "Currently using the main account profile."}
            </p>
          </div>
          {active?.type === "family" && (
            <button
              type="button"
              disabled={busy}
              onClick={() => void handleSwitchToOwner()}
              className="btn btn-primary"
            >
              Switch to main account
            </button>
          )}
        </div>
      </section>

      <section className="card space-y-4 p-5">
        <div>
          <h2 className="text-lg font-semibold">Family invitations</h2>
          <p className="mt-1 text-sm text-muted">
            Send a one-time text link. The recipient must sign in or create an account to accept it.
          </p>
        </div>

        <form onSubmit={handleCreateInvitation} className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm">
            Phone number *
            <input
              required
              type="tel"
              autoComplete="tel"
              value={invitePhone}
              onChange={(event) => setInvitePhone(event.target.value)}
              className="input mt-1 w-full"
              placeholder="+91 98765 43210"
            />
          </label>
          <label className="text-sm">
            Relationship (optional)
            <input
              value={inviteRelationship}
              onChange={(event) => setInviteRelationship(event.target.value)}
              maxLength={40}
              className="input mt-1 w-full"
              placeholder="e.g. Parent, spouse"
            />
          </label>
          <div className="sm:col-span-2">
            <button type="submit" disabled={busy} className="btn btn-primary">
              {busy ? "Please wait..." : "Send invitation"}
            </button>
          </div>
        </form>

        <div className="space-y-3">
          <h3 className="text-sm font-semibold">Saved invitations</h3>
          {invitations.length === 0 ? (
            <p className="text-sm text-muted">No invitations yet.</p>
          ) : (
            invitations.map((invitation) => (
              <div
                key={invitation.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line p-3"
              >
                <div className="min-w-0">
                  <p className="font-medium">{invitation.phone_number}</p>
                  <p className="text-sm text-muted">
                    {invitation.relationship_label || "Family member"} · {invitation.status} · SMS {invitation.delivery_status.replace(/_/g, " ")}
                  </p>
                  <p className="text-xs text-muted">
                    Expires: {new Date(invitation.expires_at).toLocaleDateString()}
                  </p>
                </div>
                {invitation.status === "pending" && (
                  <div className="flex gap-2">
                    {invitation.delivery_status !== "sent" && (
                      <button
                        type="button"
                        disabled={busy || invitation.delivery_status === "sending"}
                        onClick={() => void handleSendInvitation(invitation)}
                        className="btn"
                      >
                        Retry SMS
                      </button>
                    )}
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void handleCancelInvitation(invitation)}
                      className="btn"
                    >
                      Cancel invitation
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </section>
      <section className="card space-y-4 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Family profiles</h2>
            <p className="mt-1 text-sm text-muted">
              Select a member and enter their PIN to open their health profile.
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              clearNotices();
              setShowCreate((value) => !value);
            }}
            className="btn btn-primary"
          >
            {showCreate ? "Cancel" : "Add family member"}
          </button>
        </div>

        {showCreate && (
          <form onSubmit={handleCreate} className="grid gap-3 rounded-xl border border-line p-4 sm:grid-cols-2">
            <label className="text-sm">
              Full name *
              <input
                required
                value={name}
                onChange={(event) => setName(event.target.value)}
                className="input mt-1 w-full"
                placeholder="Family member name"
              />
            </label>
            <label className="text-sm">
              Six-digit PIN *
              <input
                required
                inputMode="numeric"
                maxLength={6}
                pattern="[0-9]{6}"
                type="password"
                autoComplete="new-password"
                value={newPin}
                onChange={(event) => setNewPin(event.target.value.replace(/\D/g, "").slice(0, 6))}
                className="input mt-1 w-full"
                placeholder="Enter six digits"
              />
            </label>
            <label className="text-sm">
              Date of birth
              <input
                type="date"
                value={dob}
                onChange={(event) => setDob(event.target.value)}
                className="input mt-1 w-full"
              />
            </label>
            <label className="text-sm">
              Gender
              <select value={sex} onChange={(event) => setSex(event.target.value)} className="input mt-1 w-full">
                <option value="">Not specified</option>
                <option value="female">Female</option>
                <option value="male">Male</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label className="text-sm sm:col-span-2">
              Blood group
              <input
                value={bloodGroup}
                onChange={(event) => setBloodGroup(event.target.value)}
                className="input mt-1 w-full"
                placeholder="e.g. O+"
              />
            </label>
            <div className="sm:col-span-2">
              <button type="submit" disabled={busy} className="btn btn-primary">
                {busy ? "Creating..." : "Create protected profile"}
              </button>
            </div>
          </form>
        )}

        {members.length === 0 ? (
          <p className="rounded-xl bg-surface-2 p-4 text-sm text-muted">
            No family profiles have been added yet.
          </p>
        ) : (
          <div className="space-y-3">
            {members.map((member) => (
              <article key={member.oid} className="rounded-xl border border-line p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="font-semibold">{member.name}</h3>
                    <p className="mt-1 text-xs text-muted">
                      {member.has_pin ? "PIN protection enabled" : "PIN setup required"}
                      {isActiveMember(member) ? " · Currently active" : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {!isActiveMember(member) && (
                      <button
                        type="button"
                        onClick={() => {
                          clearNotices();
                          setSelected(member);
                          setPin("");
                          setAccountPassword("");
                          setResetPin("");
                        }}
                        className="btn btn-primary"
                      >
                        {member.has_pin ? "Unlock profile" : "Set up PIN"}
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        clearNotices();
                        setSelected(member);
                        setEditName(member.name);
                        setPin("");
                        setAccountPassword("");
                        setResetPin("");
                      }}
                      className="btn btn-ghost"
                    >
                      Manage
                    </button>
                  </div>
                </div>

                {selected?.oid === member.oid && (
                  <div className="mt-4 space-y-4 border-t border-line pt-4">
                    {!member.has_pin && (
                      <form
                        onSubmit={(event) => {
                          event.preventDefault();
                          void handleSetPin(member);
                        }}
                        className="space-y-3"
                      >
                        <h4 className="font-medium">Set up this member's PIN</h4>
                        <input
                          type="password"
                          inputMode="numeric"
                          maxLength={6}
                          autoComplete="new-password"
                          value={pin}
                          onChange={(event) => setPin(event.target.value.replace(/\D/g, "").slice(0, 6))}
                          className="input w-full sm:max-w-xs"
                          placeholder="New six-digit PIN"
                        />
                        <button disabled={busy} className="btn btn-primary" type="submit">
                          Set PIN
                        </button>
                      </form>
                    )}

                    {member.has_pin && !isActiveMember(member) && (
                      <form
                        onSubmit={(event) => {
                          event.preventDefault();
                          void handleUnlock(member);
                        }}
                        className="space-y-3"
                      >
                        <h4 className="font-medium">Unlock {member.name}'s profile</h4>
                        <input
                          type="password"
                          inputMode="numeric"
                          maxLength={6}
                          autoComplete="current-password"
                          value={pin}
                          onChange={(event) => setPin(event.target.value.replace(/\D/g, "").slice(0, 6))}
                          className="input w-full sm:max-w-xs"
                          placeholder="Enter six-digit PIN"
                        />
                        <button disabled={busy} className="btn btn-primary" type="submit">
                          {busy ? "Checking..." : "Unlock"}
                        </button>
                      </form>
                    )}

                    <form onSubmit={handleSaveName} className="space-y-3">
                      <h4 className="font-medium">Edit profile name</h4>
                      <input
                        value={editName}
                        onChange={(event) => setEditName(event.target.value)}
                        className="input w-full sm:max-w-xs"
                      />
                      <button disabled={busy} className="btn btn-ghost" type="submit">
                        Save name
                      </button>
                    </form>

                    {member.has_pin && (
                      <form
                        onSubmit={(event) => {
                          event.preventDefault();
                          void handleResetPin(member);
                        }}
                        className="space-y-3 rounded-xl bg-surface-2 p-3"
                      >
                        <h4 className="font-medium">Reset forgotten PIN</h4>
                        <p className="text-xs text-muted">
                          Confirm your main account password to choose a new PIN.
                        </p>
                        <input
                          type="password"
                          autoComplete="current-password"
                          value={accountPassword}
                          onChange={(event) => setAccountPassword(event.target.value)}
                          className="input w-full"
                          placeholder="Main account password"
                        />
                        <input
                          type="password"
                          inputMode="numeric"
                          maxLength={6}
                          autoComplete="new-password"
                          value={resetPin}
                          onChange={(event) => setResetPin(event.target.value.replace(/\D/g, "").slice(0, 6))}
                          className="input w-full"
                          placeholder="New six-digit PIN"
                        />
                        <button disabled={busy} className="btn btn-primary" type="submit">
                          Reset PIN
                        </button>
                      </form>
                    )}

                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void handleRemove(member)}
                        className="btn btn-ghost text-crit"
                      >
                        Remove from account
                      </button>
                      <button
                        type="button"
                        onClick={() => setSelected(null)}
                        className="btn btn-ghost"
                      >
                        Close
                      </button>
                    </div>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
