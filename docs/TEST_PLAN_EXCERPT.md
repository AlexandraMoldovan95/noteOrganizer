# How it's tested

An excerpt from the manual test plan, a spreadsheet,
[`qa/NoteOrganizer_TestPlan.xlsx`](../qa/NoteOrganizer_TestPlan.xlsx): **996 cases** on 27 November
2026. I walk it
by hand on the packaged `.exe` before a release - a case I pass is one I've seen pass, and a
pass that is the scripts' says so.

## How the plan is used

- **Every case says what automation already covers.** Where the *Automation status* column names
  the script that walks the case end to end, a hand check is a choice, not a duty; where it says
  "Automated in part", it names what the checks are known not to reach, as a guide rather than a
  full list, and I walk the case whole; or it says plainly that nothing can judge it.
- **What only a person can judge is marked.** Some cases ask whether something reads well or
  looks right, the questions a script never asks.
- **Field checks become cases.** Anything left to check on the `.exe` after a change is added to
  the plan there and then, not left in a conversation.

## The plan in numbers

Counted on 27 November 2026: 996 cases, 996 walked and passed, 0 not yet
walked. Of the passes, 701 are mine, by hand, among them every case that
needs my eye, cases 1100 to 1102, added on 24 November for two fixes from
my own field test and a new way to delete and clear rows and columns, and
three walked on the app installed from the Microsoft Store: case 686, the
review button opening the app's page, on 1.0.0; case 704, every note kept
through an uninstall and a reinstall on 1.0.0 and through the Store's
update to 1.0.1; and case 1103, 1.0.1 offered, installed and opened on
Windows 11 23H2, the PC 1.0.0 had refused. 295 are the scripted suites',
run for the final audit on the source of 0.102.556 and marked
*Claude (automated, final audit)*: a pass for what the suites walk, not a
walk by hand like mine, with what they leave to the hand named in Actual
Result.

### By priority

| Priority | Cases |
|---|---:|
| High | 265 |
| Medium | 459 |
| Low | 272 |

### The six largest areas

| Area | Cases |
|---|---:|
| Backup & Sharing | 108 |
| Editor | 103 |
| Notes | 96 |
| Recurrence | 88 |
| Tables | 74 |
| Settings | 71 |

## The test case template, filled out four times

Every case uses the same template: area, priority, preconditions, numbered
steps, expected result, status, and what automation covers. **The four below are a small sample
of that full list** - not the only ones, just quick to picture without seeing the app:

- **A safety check** - Case 9, cancelling a delete.
- **An everyday action** - Case 38, marking a checklist item done.
- **A performance check at scale** - Case 15, the Trash panel with 100+ deleted notes.
- **A visual check, since automated** - Case 43, a checkbox's contrast in Light mode.

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

**Automation:** Automated in part (`qa1`) - answers No to the confirmation in code, then checks
both the note list and the Trash. A mutant that ignored the confirmation was caught by this check.
Left to the hand: the question answered by a person.

### Case 38 - Mark an item done

- **Area / Sub-feature:** Checklist · Check item
- **Priority:** Medium
- **Status:** Pass

**Preconditions:** A note is open with a checklist holding at least one unchecked item.

**Test Steps:**

1. Click the checkbox next to an item.

**Expected Result:** The item text gets a strikethrough and dims; the progress count updates.

**Automation:** Automated in part (`qa1` reads the item kept done in the store). Left to the hand:
the strikethrough, the dimming and the progress count.

### Case 15 - Trash panel opens quickly with 100+ deleted notes

- **Area / Sub-feature:** Notes · Trash scale
- **Priority:** High
- **Status:** Pass

**Preconditions:** Recently deleted holds 100 or more notes.

**Test Steps:**

1. Open Settings → Recently deleted.
2. Click 'Show N more (M not shown)'.

**Expected Result:** Step 1: the panel opens promptly with a first batch, not a long freeze.
Step 2: the next batch appears, added to what's already shown.

**Automation:** Automated in part (`qa3`). Left to the hand: the words "Show N more (M not shown)".

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

**Automation:** Automated (`qa4`) - on every theme this box's mark is judged against its well
by its pixels, and every palette's well is checked light. The case was
written as manual first, when nothing crashed, nothing threw, and a checkbox was just invisible -
a bug no script noticed until one was written for it.

---

These four are a sample. The other cases follow the same template and live in the full
spreadsheet, walked by hand before every release.
