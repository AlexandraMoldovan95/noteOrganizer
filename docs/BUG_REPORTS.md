# Bug reports

*What my manual testing found, and how a bug is reported here. - Alexandra Moldovan*

The testing itself lives in the [test plan](../qa/NoteOrganizer_TestPlan.xlsx), an Excel workbook
of **995 test cases** (on 24 November 2026). Each case has its steps and the result it expects, and once run it carries
what actually happened, the build, the date and who tested it. 320 of them also point to the
GitHub issue or pull request they check. Every pass and every retest is recorded there.

My manual testing found many bugs along the way, and every one of them is recorded there. My
notes from my first full pass over it - more than 500 cases, on the packaged app - and the
re-tests after it also led to four new features: a table that moves with its caption, the "With
files" filter, arrows to reorder a checklist, and a search in the Share panel.

This page gives some of those bugs, one line each, as examples. Three are written out in full,
as examples of the format we use for a bug report; the others are recorded in the test plan, in
the cases that found them. The bugs, the steps and what I saw are mine; the agent helped me put them
into this format. How I test, and one bug followed from the screen to its cause, are in
[In my words](IN_MY_WORDS.md#how-i-test).

## Contents

- [Some examples](#some-examples)
- [Three examples, in full](#three-examples-in-full)
- [BR-1: "Note updated" appears when only the theme changes](#br-1-note-updated-appears-when-only-the-theme-changes)
- [BR-2: The app stops responding after pasting 50,000+ words](#br-2-the-app-stops-responding-after-pasting-50000-words)
- [BR-3: Importing a backup with notes I already have offers no "import anyway"](#br-3-importing-a-backup-with-notes-i-already-have-offers-no-import-anyway)
- [On the phone](#on-the-phone)

## Some examples

These came from my first full pass, on version 0.84.341, and from the re-tests of the version
that fixed what it found.

| What I found | Fixed in |
|---|---|
| On the dark themes, ticks in Share notes and Settings → Duplicates didn't show, though they were taken ([the story](IN_MY_WORDS.md#how-i-test)) | 0.84.357 |
| Changing the theme said "Note updated", though no note had changed ([BR-1](#br-1-note-updated-appears-when-only-the-theme-changes)) | 0.84.357 |
| A highlight given inside a table cell appeared only after the cell was opened again | 0.84.357 |
| Previews in Duplicates and Recently deleted showed a table as rows of vertical lines | 0.84.357 |
| Table cells copied and pasted as a second table lost their colours and styles | 0.84.357 |
| Table cells copied into Word lost every colour | 0.84.357 |
| A word's size and font were lost when copied into Word or into another note | 0.84.357 |
| An emoji or text put into a checkbox cell left the box behind as "[ ]" | 0.84.357 |
| Enter in a numbered list threw the note's scroll back to the top | 0.84.357 |
| An emoji in an empty title landed after the grey hint, and the note was saved as "Note title...😀" | 0.84.357 |
| The cursor kept blinking in the calendar History search after a click elsewhere in the app | 0.84.357 |
| Pasting a text of 50,000+ words froze the app ([BR-2](#br-2-the-app-stops-responding-after-pasting-50000-words)) | 0.84.357 |
| "Show more" in Recently deleted made the list flicker | 0.84.357 |
| Importing a backup with notes I already had offered no "import anyway" ([BR-3](#br-3-importing-a-backup-with-notes-i-already-have-offers-no-import-anyway)) | 0.84.357 |
| Bold and italic from a web page lost their formatting when pasted | 0.84.357 |
| The share-code warning about attached files didn't say clearly what to do | 0.84.357 |
| An open checkbox cell still showed its "[ ]" brackets | 0.88.361 |
| In a narrow window, a long checklist item's bin was squeezed out, so the item couldn't be removed | 0.88.361 |
| The find bar's border turned grey while typing in it | 0.88.361 |
| On a light theme, the find box couldn't be read when nothing was found | 0.88.361 |

What each fix changed is in the [changelog](../CHANGELOG.md), under
[0.84.357](../CHANGELOG.md#084357--2026-10-07) and [0.88.361](../CHANGELOG.md#088361--2026-10-08).

## Three examples, in full

Three of them, written out as examples of how we report a bug: where it was found, the steps to
see it, what should happen and what did, how bad it is and how soon it should be fixed. The
others are recorded in the test plan, against the cases that found them, with the number of
their issue on GitHub.

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
| **Fixed in** | [0.84.357](../CHANGELOG.md#084357--2026-10-07): the import now asks once: **Skip it** or **Skip the N** (the default), or **Add a copy anyway** or **Add copies anyway**. |

## On the phone

Using the Android app on my own phone, I found more. Three of them, the first written out in full.

### BR-P1: Text typed at the end of a long note is hidden under the keyboard

I was testing the app with long texts, editing the end of one to add more to it, and I realised I
couldn't see what I was writing: the new words appeared under the phone's keyboard. To see them I
had to put the keyboard down, and then I could no longer type. That would not help anyone manage
what is in a note; the text had to stay above the keyboard, so it can be edited with ease.

| Field | Detail |
|---|---|
| **Build** | The build on my phone on 23 October 2026, after release 0.10.1. Samsung S24 Ultra, Android 16, Samsung's keyboard. |
| **Precondition** | A note whose text is longer than one screen, so its end is reached only by scrolling. |
| **Steps** | 1. Open the app and open that note. 2. Scroll to the end of the text. 3. Tap after the last word, so the keyboard opens. 4. Press Enter and type a few words. |
| **Expected** | What I am typing stays in sight, above the keyboard. |
| **Actual** | The new words appear under the keyboard, and the screen does not scroll up. I can only see them by closing the keyboard, and then I can no longer type. |
| **Severity** | Major: nothing is lost, but I cannot see what I write. |
| **Priority** | High: adding to the end of a note is an everyday action. |
| **Frequency** | Every time, on any note long enough. |
| **Fixed in** | 0.11.0 on the phone: the note now follows the cursor as you write. The comments, a table's cell and a template's text had the same fault, and were fixed with it. |

### Two more

- **A note with a table had a broken preview in the list.** I noticed it while scrolling through
  my test notes: their cards showed lines of bars where the table was. To fix it, and to keep
  things consistent, I decided that where a note has a table, its preview says only that it has
  one, beside the note's words. It is easy to build and to show, and it takes away the risk of
  other bugs. Previews like this were already used in the calendar and, on the desktop, in
  Settings → Duplicates and Recently deleted, so we made it the same everywhere the app needed it.
- **The table was hard to use on a phone.** A tap on a cell opened a list of options, and its
  words were typed in a box of their own, away from the table. There is no mouse on a phone, so I
  wanted the table to be as easy to edit as possible: its cells are written in place now, its rows
  dragged taller or shorter by their edge, and its columns made wider or narrower.
