# Bug reports

*What my manual testing found, and how a bug is reported here. - Alexandra Moldovan*

The testing itself lives in the [test plan](../qa/NoteOrganizer_TestPlan.xlsx), an Excel workbook
of **951 test cases** (on 13 November 2026). Each case has its steps and the result it expects, and once run it carries
what actually happened, the build, the date and who tested it. 306 of them also point to the
GitHub issue or pull request they check. Every pass and every retest is recorded there.

My first full manual pass over it - more than 500 cases, on the packaged app - and the two
re-tests after it found **20 bugs**, all now fixed. My notes from the same passes also led to
four new features: a table that moves with its caption, the "With files" filter, arrows to reorder
a checklist, and a search in the Share panel.

This page lists those twenty bugs, one line each. Three of them are written out in full, as
examples of the format we use for a bug report; the rest are recorded in the test plan, in the
cases that found them. The bugs, the steps and what I saw are mine; the agent helped me put them
into this format. How I test, and one bug followed from the screen to its cause, are in
[In my words](IN_MY_WORDS.md#how-i-test).

## Contents

- [All twenty](#all-twenty)
- [Three examples, in full](#three-examples-in-full)
- [BR-1: "Note updated" appears when only the theme changes](#br-1-note-updated-appears-when-only-the-theme-changes)
- [BR-2: The app stops responding after pasting 50,000+ words](#br-2-the-app-stops-responding-after-pasting-50000-words)
- [BR-3: Importing a backup with notes I already have offers no "import anyway"](#br-3-importing-a-backup-with-notes-i-already-have-offers-no-import-anyway)

## All twenty

The first sixteen came from the full pass on version 0.84.341, the last four from the re-tests of
the version that fixed them.

| # | What I found | Fixed in |
|---|---|---|
| 1 | On the dark themes, ticks in Share notes and Settings → Duplicates didn't show, though they were taken ([the story](IN_MY_WORDS.md#how-i-test)) | 0.84.357 |
| 2 | Changing the theme said "Note updated", though no note had changed ([BR-1](#br-1-note-updated-appears-when-only-the-theme-changes)) | 0.84.357 |
| 3 | A highlight given inside a table cell appeared only after the cell was opened again | 0.84.357 |
| 4 | Previews in Duplicates and Recently deleted showed a table as rows of vertical lines | 0.84.357 |
| 5 | Table cells copied and pasted as a second table lost their colours and styles | 0.84.357 |
| 6 | Table cells copied into Word lost every colour | 0.84.357 |
| 7 | A word's size and font were lost when copied into Word or into another note | 0.84.357 |
| 8 | An emoji or text put into a checkbox cell left the box behind as "[ ]" | 0.84.357 |
| 9 | Enter in a numbered list threw the note's scroll back to the top | 0.84.357 |
| 10 | An emoji in an empty title landed after the grey hint, and the note was saved as "Note title...😀" | 0.84.357 |
| 11 | The cursor kept blinking in the calendar History search after a click elsewhere in the app | 0.84.357 |
| 12 | Pasting a text of 50,000+ words froze the app ([BR-2](#br-2-the-app-stops-responding-after-pasting-50000-words)) | 0.84.357 |
| 13 | "Show more" in Recently deleted made the list flicker | 0.84.357 |
| 14 | Importing a backup with notes I already had offered no "import anyway" ([BR-3](#br-3-importing-a-backup-with-notes-i-already-have-offers-no-import-anyway)) | 0.84.357 |
| 15 | Bold and italic from a web page lost their formatting when pasted | 0.84.357 |
| 16 | The share-code warning about attached files didn't say clearly what to do | 0.84.357 |
| 17 | An open checkbox cell still showed its "[ ]" brackets | 0.88.361 |
| 18 | In a narrow window, a long checklist item's bin was squeezed out, so the item couldn't be removed | 0.88.361 |
| 19 | The find bar's border turned grey while typing in it | 0.88.361 |
| 20 | On a light theme, the find box couldn't be read when nothing was found | 0.88.361 |

What each fix changed is in the [changelog](../CHANGELOG.md), under
[0.84.357](../CHANGELOG.md#084357--2026-10-07) and [0.88.361](../CHANGELOG.md#088361--2026-10-08).

## Three examples, in full

Three of the twenty, written out as examples of how we report a bug: where it was found, the steps
to see it, what should happen and what did, how bad it is and how soon it should be fixed. The
other seventeen are recorded in the test plan, against the cases that found them, with the number
of their issue on GitHub.

| Report | Severity | Priority |
|---|---|---|
| [BR-1: "Note updated" appears when only the theme changes](#br-1-note-updated-appears-when-only-the-theme-changes) | Minor | Low |
| [BR-2: The app stops responding after pasting 50,000+ words](#br-2-the-app-stops-responding-after-pasting-50000-words) | Major | Medium |
| [BR-3: Importing a backup with notes I already have offers no "import anyway"](#br-3-importing-a-backup-with-notes-i-already-have-offers-no-import-anyway) | Major | Medium |

**Severity** is how badly the bug hurts the person using the app; **priority** is how soon it
should be fixed. They are not the same thing: BR-2 hurts a lot, but only with a very large text.

## BR-1: "Note updated" appears when only the theme changes

| Field | Detail |
|---|---|
| **Build** | 0.84.341 (the packaged `.exe`), Windows 11 |
| **Test plan** | case 45, bug #244 |
| **Steps** | 1. Open a note. 2. Change the theme, from any of the three places: the editor, the switch at the bottom left, or Settings → Appearance. |
| **Expected** | The theme changes, with no message: no note changed. |
| **Actual** | A green "Note updated" banner appears every time. |
| **Severity** | Minor: nothing is lost, but the message is wrong. |
| **Priority** | Low |
| **Frequency** | Every time. I reproduced it several times in the same session before reporting it. |
| **Fixed in** | [0.84.357](../CHANGELOG.md#084357--2026-10-07): a theme switch no longer saves anything, and "Note updated" shows only when something was saved. |

## BR-2: The app stops responding after pasting 50,000+ words

| Field | Detail |
|---|---|
| **Build** | 0.84.341 (the packaged `.exe`), Windows 11 |
| **Test plan** | case 19, bug #245 |
| **Precondition** | A text of 50,000+ words is copied; a note is open. |
| **Steps** | 1. Paste the text into the note. |
| **Expected** | The text is pasted, and the note saves without freezing. |
| **Actual** | The app froze ("Not responding") and had to be closed by force. After reopening it, the clipboard no longer held the text, and only 1,351 words were pasted. |
| **Severity** | Major: the app hangs and the text is lost. |
| **Priority** | Medium: it needs a very large text. |
| **Frequency** | Seen once; reported, then retested after the fix. |
| **Fixed in** | [0.84.357](../CHANGELOG.md#084357--2026-10-07): copying a long note no longer freezes the app. A single paragraph that long is still slow, because of how Tkinter lays text out; it is recorded under [Known limitations](ROADMAP.md#known-limitations), and I decided against a warning. |

## BR-3: Importing a backup with notes I already have offers no "import anyway"

| Field | Detail |
|---|---|
| **Build** | 0.84.341 (the packaged `.exe`), Windows 11 |
| **Test plan** | case 92, bug #246 |
| **Precondition** | A backup `.zip` holding notes that are already in the app. |
| **Steps** | 1. Settings → Backup → Import, and choose the `.zip`. |
| **Expected** | I am asked what to do with the notes I already have: skip them, import them anyway, or cancel. |
| **Actual** | No choice, only a message that nothing was imported. A share code with the same notes does the same (case 98). Workaround: delete those notes, then import again. |
| **Severity** | Major: an expected option is missing. |
| **Priority** | Medium |
| **Frequency** | Seen once; reported, then retested after the fix. |
| **Fixed in** | [0.84.357](../CHANGELOG.md#084357--2026-10-07): the import now asks once: **Skip** (the default) or **Add copies anyway**. |
