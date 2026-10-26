# How it's tested

An excerpt from the manual test plan, a spreadsheet,
[`qa/NoteOrganizer_TestPlan.xlsx`](../qa/NoteOrganizer_TestPlan.xlsx): **589 cases**. I walk it
by hand on the packaged `.exe` before a release - a case passes only when I've seen it pass.

## How the plan is used

- **Every case says what automation already covers.** A hand check is a choice, not a duty - the
  *Automation status* column names the script that walks the case end to end, or says plainly
  that nothing can judge it.
- **What only a person can judge is marked.** Some cases ask whether something reads well or
  looks right, the questions a script never asks.
- **Field checks become cases.** Anything left to check on the `.exe` after a change is added to
  the plan there and then, not left in a conversation.

## The plan in numbers

### By priority

| Priority | Cases |
|---|---:|
| High | 180 |
| Medium | 289 |
| Low | 120 |

### The six largest areas

| Area | Cases |
|---|---:|
| Editor | 70 |
| Notes | 63 |
| Tables | 54 |
| Recurrence | 47 |
| Calendar | 46 |
| Settings | 43 |

## The test case template, filled out four times

Every one of the 589 cases uses the same template: area, priority, preconditions, numbered
steps, expected result, status, and what automation covers. **The four below are a small sample
of that full list** - not the only ones, just quick to picture without seeing the app:

- **A safety check** - Case 9, cancelling a delete.
- **An everyday action** - Case 38, marking a checklist item done.
- **A performance check at scale** - Case 15, the Trash panel with 100+ deleted notes.
- **A manual visual check** - Case 43, a checkbox's contrast in Light mode.

### Case 9 - Cancel a delete

- **Area / Sub-feature:** Notes · Delete
- **Priority:** High
- **Status:** Pass

**Preconditions:** At least one note exists.

**Test Steps:**

1. Open a note.
2. Click 'Delete'.
3. Click 'No' on the confirmation.

**Expected Result:** The note is NOT deleted and remains in the list.

**Automation:** Automated (`qa1`) - answers No to the confirmation, then checks both the note
list and the Trash. A mutant that ignored the confirmation was caught by this check.

### Case 38 - Mark a checklist item done

- **Area / Sub-feature:** Checklist · Check item
- **Priority:** Medium
- **Status:** Pass

**Preconditions:** A note is open with a checklist holding at least one unchecked item.

**Test Steps:**

1. Click the checkbox next to an item.

**Expected Result:** The item text gets a strikethrough and dims; the progress count updates.

**Automation:** Automated (`qa1`).

### Case 15 - Trash panel opens quickly with 100+ deleted notes

- **Area / Sub-feature:** Notes · Trash scale
- **Priority:** High
- **Status:** Pass

**Preconditions:** Recently deleted holds 100 or more notes.

**Test Steps:**

1. Open Settings → Recently deleted.
2. Click 'Show more'.

**Expected Result:** Step 1: the panel opens promptly with a first batch, not a long freeze.
Step 2: the next batch appears, added to what's already shown.

**Automation:** Automated (`qa3`).

### Case 43 - 'Group by category' checkbox in Light mode

- **Area / Sub-feature:** Themes · Checkbox styling
- **Priority:** High
- **Status:** Pass

**Preconditions:** The app is open.

**Test Steps:**

1. Switch to Light mode.
2. Look at the 'Group by category' checkbox in the sidebar.

**Expected Result:** The checkbox background is white with a black check mark, not
black-on-black.

**Automation:** Automated (`qa4`) - every tick box on screen, this one included, is judged on
every theme: its well is not the surface it sits on, and its mark reads on the well. The case was
written as manual first, when nothing crashed, nothing threw, and a checkbox was just invisible -
a bug no script noticed until one was written for it.

---

These four are a sample. The other 585 cases follow the same template and live in the full
spreadsheet, walked by hand before every release.
