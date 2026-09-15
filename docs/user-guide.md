# User guide

For the people who use Ztech Sales day to day.

This release delivers the foundation: signing in, user accounts, roles, company
settings and the audit trail. Customers, quotations, approvals and reporting
arrive in the increments that follow. Nothing in the interface pretends they are
here yet — if you cannot find a screen for something, it does not exist rather
than being hidden from you.

---

## 1. Signing in

Go to your company's address and sign in with your email and password.

- Accounts are per person. Never share one: every action is recorded against the
  name on the account, and approvals and acceptances have to name a real person.
- If your account was just created you will be asked to change your password the
  first time you sign in.
- After several wrong passwords the account locks for a while. Wait, or ask an
  administrator.
- If you are told your email or password is not correct, the system genuinely
  does not say which. That is deliberate — it stops someone using the sign-in
  form to find out whose accounts exist.

### Changing your password

**Change password**, bottom of the navigation. You need your current password.
New passwords must be at least 12 characters and not one in common use. You stay
signed in afterwards.

---

## 2. Finding your way around

The navigation shows only what you have permission to use. If a colleague sees
**Users** and you do not, that is your roles differing, not a fault.

| Screen | What it is for |
|---|---|
| **Overview** | Who you are signed in as, what you may do, and how this deployment is configured |
| **Users** | The people who can sign in *(needs "View users")* |
| **Roles** | What each role allows *(needs "View roles")* |
| **Company** | Your company's details, currency, time zone and branding *(needs "View settings")* |
| **Audit trail** | Every recorded action *(needs "View audit trail")* |

Everything works from the keyboard. Tab moves between controls, Enter submits a
form, and whatever is focused is always visibly outlined.

---

## 3. The Overview screen

**Your access** shows your roles, how many permissions you hold, when you last
signed in, and whether you hold approval authority.

Approval authority is worth understanding: it is granted by a **role**, never by
being an administrator. An administrator who has not been given the Approver
role cannot approve anything, and that is intentional — the person who runs the
system should not automatically be the person who signs off discounts.

**Deployment status** (administrators only) reports what is actually configured.
If it says outbound email is *not configured*, the application genuinely cannot
send email and will not pretend otherwise. Ask whoever set the environment up.

---

## 4. Users

### Adding someone

**Users → Add user**. You need "Manage users".

- Use their real name and their real work email.
- Setting an **initial password** means they can sign in and will be asked to
  change it immediately. Leaving it blank creates the account without a usable
  password, for when access will be arranged separately.
- Tick the roles they need. **Saving replaces the whole set of roles**, so the
  ticked boxes are exactly what they will have.

### Changing someone

Open them from the list, change what you need, **Save changes**.

Two things you cannot do, on purpose:

- Deactivate your own account, or remove your own administrator access. Without
  this it is possible to lock yourself out of an environment you are the only
  administrator of.
- Leave the environment with nobody who can manage users. Grant somebody else
  administrator access first.

### Removing someone

Accounts are never deleted — history has to keep naming the person who acted.
Untick **Active** instead. That takes effect immediately, including on a session
they already have open: their very next click signs them out.

### "This user was changed by someone else"

Somebody saved changes to this record while you had it open. **Nothing you typed
was saved**, deliberately — overwriting their work silently would be worse.
Reload, look at what changed, and reapply your edit.

---

## 5. Roles

A role is a named bundle of permissions. Changing a role changes what everyone
holding it can do, immediately.

The five built-in roles:

| Role | For |
|---|---|
| **System Administrator** | Configuration, users and roles. **Not** approval authority |
| **Sales Manager** | The whole pipeline, including other people's quotations |
| **Sales Representative** | Their own quotations and customers |
| **Approver** | Deciding discount approvals. Held *in addition to* a sales role |
| **Read Only** | Looking, not touching |

Built-in roles can have their permissions changed but cannot be renamed by code
or deactivated, so an environment always has a known starting point.

### Editing permissions

Open a role. Permissions are grouped by area, each with a plain-English
description. **Select all** and **Clear all** work per group. Save when done.

Give people the least that lets them do their job. It is quick to add a
permission when someone turns out to need it; it is awkward to explain why
someone had access they should not have had.

---

## 6. Company

Your company's legal name, registration numbers, address, contact details,
currency, time zone and branding.

**Currency** determines how money is rounded everywhere. The Omani rial has
three decimal places, so 945.000 is shown with three. This is not cosmetic — it
is how amounts are stored and calculated.

**Time zone** is what date-sensitive rules use. Quotation expiry means expiry on
that date *in your time zone*, not in UTC and not in the time zone of whoever is
looking.

**Brand colours** are applied to the interface and to customer documents.

**Document footer** is printed at the foot of customer documents. **Customers
see it.** Never put internal notes, margin information or approval policy there.

---

## 7. Audit trail

Every recorded action, in order: when, who, what, which record, and what
changed, field by field, with the old and new values.

Filter by action (`user.created`) or by record type (`core.user`).

Audit entries **cannot be edited or deleted** — not by an administrator, not
through the interface, and not through the API. There is no route that does it.
That is what makes the trail worth anything when someone asks what happened.

Passwords never appear in it. They are replaced with `[redacted]` before the
entry is written.

---

## 8. Questions people ask

**Why can't I see a screen my colleague can?**
Your roles differ. Overview shows what you hold; an administrator can compare.

**I was signed out suddenly.**
Either your session expired, or your account was deactivated. Deactivation takes
effect on your next click.

**Why does it say my changes weren't saved?**
Somebody else saved that record while you had it open. Reload and reapply your
change — the message is there so you know to look at what they did rather than
overwrite it.

**Where are quotations?**
Not in this release. See [`progress.md`](progress.md) for what is built and what
is coming.

**Can I approve my own discount?**
No, and that will stay true when approvals ship. It is the point of having them.
