# Test plan — an excerpt

The manual test plan is a spreadsheet,
[`qa/NoteOrganizer_TestPlan.xlsx`](../qa/NoteOrganizer_TestPlan.xlsx): 533 cases, each with its
steps, the expected result and a status. The owner walks it by hand on the packaged `.exe` before
a release; the status column is hers to set, and a case passes only when she has seen it pass.
This page shows thirteen of them in plain text, so the plan can be read without downloading a
binary file. The spreadsheet is the source; this excerpt was taken at 0.89.371.

## How the plan is used

- **Every case says what automation already covers.** The column *Automation status* names the
  check that walks the case end to end, so a hand check is a choice rather than a duty — or says
  plainly that no script can judge it.
- **What only a person can judge is marked.** Cases titled *NEEDS YOUR EYE* ask whether something
  reads well or looks right — the questions a script never asks. One case asks for a real
  colour-blind reader, because a simulation is not one (case 625 below).
- **Field checks become cases.** Anything left to check on the `.exe` after a change is added to
  the plan there and then, not left in a conversation.

| | Count |
|---|---:|
| Cases | 533 |
| Priority High / Medium / Low | 164 / 262 / 107 |
| Largest areas | Editor 62 · Notes 60 · Calendar 48 · Tables 48 · Recurrence 40 · Backup & Sharing 37 |

## Thirteen cases

### 9. Cancel a delete

*Notes → Delete · priority High · status: **Pass***

**Before you start:** At least one note exists.

**Steps:**

   1. Open a note.
   2. Click 'Delete'.
   3. Click 'No' on the confirmation.

**Expected:** The note is NOT deleted and remains in the list.

**Automation:** Automated (qa1) - answering No to the confirmation, then looking in BOTH the note list and the Trash. Mutant: the confirmation ignored, check went red.


### 59. Monthly note on day 31 with 'use last day'

*Recurrence → Monthly · priority High · status: **Pass***

**Before you start:** A note is open with a start date set.

**Steps:**

   1. Choose Repeat → Monthly.
   2. Set the day to 31.
   3. Choose the clamp policy ('use last day').
   4. Look at a month shorter than 31 days on the Calendar tab.
   5. Back in the note, choose the skip policy ('skip that month').
   6. Look at the same short month again.

**Expected:** Step 4: in the shorter month, the note falls on that month's last day. Step 6: in the short month, the note simply does not appear.

**Automation:** Automated (test_recurrence) - manual only if something looks off Also covers former case 60 (Monthly note with 'skip that month' policy): Automated (test_recurrence) - manual only if something looks off


### 92. Import a backup that overlaps with existing notes

*Backup & Sharing → Import duplicate check · priority High · status: **Pass***

**Before you start:** A backup .zip exists that contains some notes you already have.

**Steps:**

   1. Settings → Import notes: choose that .zip.

**Expected:** Notes the backup holds exactly as you have them: one question, 'Already here, unchanged' -- Skip (the default) adds nothing, 'Add copies anyway' adds them as separate notes. Notes that only LOOK like yours: you are prompted to skip them, 'Import all anyway', or cancel. Nothing is silently duplicated.

**Automation:** Automated (qa3) - manual only if something looks off


### 98. Import a code containing notes you already have

*Backup & Sharing → Import code duplicates · priority High · status: **Pass***

**Before you start:** A share code is ready to paste that overlaps with existing notes (it holds notes you already have).

**Steps:**

   1. Paste the code into 'Import code' in the sidebar.

**Expected:** A note the code holds exactly as you have it: you are asked 'Already here, unchanged' -- Skip (the default) or add a copy. A note that only looks like one of yours: you are prompted about the duplicate before anything is added.

**Automation:** Automated (qa3) - manual only if something looks off


### 114. Editing a template changes new notes, never the ones made earlier

*Combinations → Template checklist + later edit · priority High · status: **Pass***

**Before you start:** A template with a checklist exists.

**Steps:**

   1. Use the template to create a note (note A), and save it.
   2. Open Settings → Templates.
   3. Click edit (pencil) on the template.
   4. Change its note title, its body and its checklist.
   5. Click 'Save'.
   6. Use the template again (note B).
   7. Open note A.

**Expected:** Step 5: the template is updated. Step 6: note B gets the NEW title, body and checklist. Step 7: note A is unaffected by the later edit: its title, body and checklist are as they were.

**Automation:** Automated (qa1) - the earlier note untouched by a later template edit, and the next note getting the new checklist. Also covers former case 34 (Edit an existing template): Automated (qa9) - manual only if something looks off


### 118. Start an export while a note has unsaved changes

*Combinations → Export mid-edit · priority High · status: **Pass***

**Before you start:** A note is open.

**Steps:**

   1. Type in the note (don't save).
   2. Immediately trigger Export.
   3. Look at the note once the export is done.

**Expected:** Export doesn't lose or corrupt the in-progress edit; the note autosaves as expected around it.

**Automation:** Automated (qa6) - what is on disk during the edit is the saved text, and the edit is not lost afterwards. Mutant: the autosave flush disabled, check went red. NOTE: this covers the autosave around an export, not a full export run.


### 122. App survives a note with missing/null fields

*Data integrity → Corrupt note fields · priority High · status: **Pass***

**Before you start:** Only on the separate Windows account made for the usability test -- never on your own notebook. The app is closed.

**Steps:**

   1. Manually null out a field of one note in notes_data.json.
   2. Save the file.
   3. Open the app.
   4. Open that note.

**Expected:** Step 3: the app doesn't crash. Step 4: that note displays with safe defaults.

**Automation:** Automated (qa5 + test_data_safety) - manual only if something looks off


### 125. Rapidly switch between many notes

*Data integrity → Rapid note switching · priority High · status: **Pass***

**Before you start:** The notebook holds 10 or more notes.

**Steps:**

   1. Click through 10+ different notes quickly in succession.

**Expected:** No data loss, no crash, no note shows another note's content, no visible flicker/freeze.

**Automation:** Automated (qa6) - twelve notes opened one after another, each checked against its own text, then all twelve re-read off the disk. Mutant: the editor left holding the previous body, check went red.


### 149. Tab walk and Enter for a new cell line

*Tables → Keyboard · priority High · status: **Pass***

**Before you start:** A note is open with a table.

**Steps:**

   1. Fill cells, moving between them with Tab.
   2. Press Tab on the last cell.
   3. Click into a cell with text.
   4. Press Enter (or Shift+Enter).
   5. Type more.

**Expected:** Step 2: Tab adds a row at the end. Step 5: a second line appears INSIDE the cell and the whole row grows on the spot; the row below stays visible the entire time (leave the cell with Tab, Escape, or a click elsewhere).

**Automation:** Automated (qa1) - manual only if something looks off Also covers former case 185 (Enter makes a new line inside the cell): Automated in part (qa1) - the rest is worth eyes


### 288. The calendar is current after changing notes in Settings

*Calendar → Freshness · priority High · status: **Pass***

**Before you start:** Recently deleted holds a note with a date on it.

**Steps:**

   1. Go to the Calendar tab and leave it selected.
   2. Open Settings.
   3. In Recently deleted, restore the note with a date on it.
   4. Press 'Back to Notes'.
   5. Look at the calendar.

**Expected:** The restored note is on its day straight away. The calendar is no longer rebuilt while it is off screen — which is most of the time, and was a quarter of what a delete cost — so it is caught up on each of the four routes back to it. Leaving Settings is the route with no tab change, and so the one that had nothing to catch it up.

**Automation:** Automated: qa6 walks this exact route and qa1 covers the deferral and its catch-up. Three mutants, each dying on its own check.


### 43. 'Group by category' checkbox in Light mode

*Themes → Checkbox styling · priority High · status: **Pass***

**Before you start:** The app is open.

**Steps:**

   1. Switch to Light mode.
   2. Look at the 'Group by category' checkbox in the sidebar.

**Expected:** The checkbox background is white with a black check mark, not black-on-black.

**Automation:** Manual only


### 625. NEEDS A REAL READER -- can someone with red-green colour blindness tell the buttons apart?

*Settings → Appearance · priority Low · status: **Pass***

**Before you start:** Someone who has protanopia or deuteranopia (red-green colour blindness), willing to look for two minutes. Fresh Mint is the theme to try first.

**Steps:**

   1. Open a note in Fresh Mint, then in Warm Cream.
   2. Ask: which button saves, which deletes, and which one is red?
   3. Open Settings → Recently deleted and ask the same about Restore and Delete.

**Expected:** A judgement call by a real reader: they find Save and Delete without hesitating. Save is the one filled button; Delete is quiet with red words -- for a protanope those words are close to ordinary text in Fresh Mint, so the word 'Delete' and the bin icon have to carry it. In the Trash, the filled Delete should stand out from Restore.

**Automation:** NOT automatable -- simulated, Save and Delete differ by at least dE2000 20.7 in every theme, but the quiet Delete's red words are only 6.8 from ordinary words for a protanope in Fresh Mint. A simulation is not a person: this asks one.


### 626. NEEDS YOUR EYE -- the current match is boxed, and the box looks right

*Notes → Find in note · priority Medium · status: **Pass***

**Before you start:** A note with the same word three times, e.g. 'flour for bread / more flour / flour again'.

**Steps:**

   1. Press Ctrl+F and type the word.
   2. Press Enter a few times to step through.
   3. Switch to a dark theme (Settings → Appearance) and back to the note; press Ctrl+F again.

**Expected:** The current match is filled AND has a thin dark box around it; the other matches are only tinted, with no box. The box moves as you step. Your judgement: does the box look neat, or too heavy / too tight around the letters?

**Automation:** Automated: qa1 checks the box when find opens and after a theme switch (mutant CB01 killed); photographed on Soft Lavender, Forest Green and Warm Cream, and simulated for colour blindness. NOT automatable: whether the box looks right.

