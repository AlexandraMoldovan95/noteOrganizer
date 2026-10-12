# Test plan — an excerpt

The manual test plan is a spreadsheet,
[`qa/NoteOrganizer_TestPlan.xlsx`](../qa/NoteOrganizer_TestPlan.xlsx): **533 cases**, each with
its steps, the expected result and a status. The owner walks it by hand on the packaged `.exe`
before a release, and a case passes only when she has seen it pass. This excerpt was taken at
version 0.89.371.

## How the plan is used

- **Every case says what automation already covers.** A hand check is a choice, not a duty — the
  *Automation status* column names the script that walks the case end to end, or says plainly
  that nothing can judge it.
- **What only a person can judge is marked.** Some cases ask whether something reads well or
  looks right, the questions a script never asks.
- **Field checks become cases.** Anything left to check on the `.exe` after a change is added to
  the plan there and then, not left in a conversation.

## The plan in numbers

| | |
|---|---:|
| Cases | 533 |
| Priority High / Medium / Low | 164 / 262 / 107 |
| Largest areas | Editor 62 · Notes 60 · Calendar 48 · Tables 48 · Recurrence 40 · Backup & Sharing 37 |

## The template, filled out four times

Every one of the 533 cases uses the same fields: area, priority, preconditions, numbered steps,
expected result, status, and what automation covers. Four are shown below, picked because they
are quick to picture without seeing the app: a safety check, an everyday action, a performance
check at scale, and a check only a real person can make.

### Case 9 — Cancel a delete

**Area / Sub-feature:** Notes · Delete · **Priority:** High · **Status:** Pass

**Preconditions:** At least one note exists.

**Test Steps:**

1. Open a note.
2. Click 'Delete'.
3. Click 'No' on the confirmation.

**Expected Result:** The note is NOT deleted and remains in the list.

**Automation:** Automated (`qa1`) — answers No to the confirmation, then checks both the note
list and the Trash. A mutant that ignored the confirmation was caught by this check.

### Case 38 — Mark a checklist item done

**Area / Sub-feature:** Checklist · Check item · **Priority:** Medium · **Status:** Pass

**Preconditions:** A note is open with a checklist holding at least one unchecked item.

**Test Steps:**

1. Click the checkbox next to an item.

**Expected Result:** The item text gets a strikethrough and dims; the progress count updates.

**Automation:** Automated (`qa1`).

### Case 15 — Trash panel opens quickly with 100+ deleted notes

**Area / Sub-feature:** Notes · Trash scale · **Priority:** High · **Status:** Pass

**Preconditions:** Recently deleted holds 100 or more notes.

**Test Steps:**

1. Open Settings → Recently deleted.
2. Click 'Show more'.

**Expected Result:** Step 1: the panel opens promptly with a first batch, not a long freeze.
Step 2: the next batch appears, added to what's already shown.

**Automation:** Automated (`qa3`).

### Case 625 — NEEDS A REAL READER: can someone with red-green colour blindness tell the buttons apart?

**Area / Sub-feature:** Settings · Appearance · **Priority:** Low · **Status:** Pass

**Preconditions:** Someone who has protanopia or deuteranopia (red-green colour blindness),
willing to look for two minutes. Fresh Mint is the theme to try first.

**Test Steps:**

1. Open a note in Fresh Mint, then in Warm Cream.
2. Ask: which button saves, which deletes, and which one is red?
3. Open Settings → Recently deleted and ask the same about Restore and Delete.

**Expected Result:** A judgement call by a real reader: they find Save and Delete without
hesitating. Save is the one filled button; Delete is quiet, with red words — for a protanope those
words are close to ordinary text in Fresh Mint, so the word "Delete" and the bin icon have to carry
it. In the Trash, the filled Delete should stand out from Restore.

**Automation:** Not automatable. Simulated, Save and Delete differ by at least ΔE2000 20.7 in every
theme, but the quiet Delete's red words are only 6.8 from ordinary words for a protanope in Fresh
Mint. A simulation is not a person: this case asks one.
