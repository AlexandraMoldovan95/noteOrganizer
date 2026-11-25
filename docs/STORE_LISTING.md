# Microsoft Store listing

What people read on the app's page in the Microsoft Store, and every value typed into Partner
Center for it, kept here so the listing says what the app does, no more and no less, and
changes with it. Each field is in a block, ready to paste as it is. The listing is in English,
like the app.

Prepared on 2026-11-25 for the first release, 1.0.0, not yet submitted. Every claim was checked
against the [user guide](USER_GUIDE.md), the [README](../README.md) and the
[privacy policy](PRIVACY.md) at 0.103.558.

Three things keep it true:

- **At every release**, "What's new" says exactly what changed, and the screenshots are
  retaken on the version released.
- **A change that makes a sentence here untrue** changes the sentence in the same branch.
- **It never names the project's site.** The site is kept apart from the apps' users (the
  owner's rule, 2026-10-21, [why](../site/README.md#kept-apart-from-the-apps)); the site's
  build refuses to run while this file holds the site's address.

How a release reaches the Store, and what is proved before it does, is in the
[Windows release guide](RELEASE_WINDOWS.md#microsoft-store-msix).

## Contents

- [Store listing](#store-listing)
- [Properties](#properties)
- [Age rating](#age-rating)
- [Pricing and availability](#pricing-and-availability)
- [Notes for certification](#notes-for-certification)
- [Decided](#decided)
- [To check once the listing is live](#to-check-once-the-listing-is-live)

## Store listing

Partner Center → the product → Store listings → English.

### Product name

Reserved in Partner Center; the listing uses the reservation.

```
Note Organizer
```

### Short description

Up to 1,000 characters, shown in full up to about 270.

```
Offline notes for Windows: rich text, tables, checklists, notes that repeat, and a calendar that shows them. No account, no cloud, no ads. Your notes stay in a folder on your own computer, and uninstalling the app leaves them there.
```

### Description

Up to 10,000 characters of plain text.

```
Note Organizer is a notes app that keeps everything on your own computer. There is no account to make, no cloud, no advertising and no tracking, and the app itself connects to nothing: it opens a page in your browser only when you ask it to.

WRITE NOTES THE WAY YOU WANT THEM
• Bold, italic, underline, colours, highlights, eight fonts, sizes, lists and alignment.
• Tables you edit right in the note: insert, clear or delete rows and columns, merge cells, and copy cells to and from Excel.
• A checklist in any note, with its progress on the note's card.
• Attach files and pictures to a note; pictures open large inside the app.
• A calculator beside the note, which drops the whole sum into it.
• Spelling checked with Windows' own dictionaries.

NOTES THAT REPEAT, AND A CALENDAR
• Notes that repeat every day or every few days, on chosen weekdays, on chosen days of the month, or every year, forever or until an end you set.
• Change one day on its own or the whole series, and move a single day to another date.
• A calendar that shows every note on its day, with colours and markers for the days that matter.
• A History of everything that was ever on the calendar, with its own search.

FIND AND ORGANISE
• Search, sort, group by category, pin to the top, or arrange the list by hand.
• Find inside the open note with Ctrl+F.
• Templates for the notes you write again and again.
• Find and clean up duplicate notes.
• A Trash to restore from (Settings → Recently deleted).

YOUR NOTES ARE YOUR FILES
• Your notebook is a folder of plain files in your user folder, beside Documents. Updating or uninstalling the app leaves it where it is.
• A full backup is a single .zip file with every note, attachment, template, setting and the Trash. Import it on another computer to move your notebook there.
• Export a note as a web page, to open in a browser or in Word or to print as a PDF, or as plain text.
• A share code copies a note as text, to paste into another copy of Note Organizer, its table, checklist and formatting included; attached files travel only in a full backup.

COMFORTABLE TO USE
• Eight themes, light and dark.
• Sharp text on a screen Windows enlarges (Settings → Appearance).
• Keyboard shortcuts for the common actions, and a note list you can walk with the arrow keys.
• A question about something you cannot take back gives the safe answer to both Enter and Escape.

GOOD TO KNOW
• Note Organizer works on one computer at a time. It does not sync: notes move to another computer by backup or share code.
• Your notes are kept in plain files, not encrypted; your Windows account protects them.
• A screen reader cannot read most of the window.
• It needs Windows 11, version 24H2 or later.

To report a problem or share an idea, write a review here in the Store. I read every one and answer here, publicly.
```

### Product features

Up to 20, each up to 200 characters; the Store shows them as a list beside the description.

```
Works offline: no account, no cloud, no ads, no tracking
Rich text: bold, italic, colours, highlights, fonts, sizes, lists and alignment
Tables edited right in the note, copied to and from Excel
A checklist in any note, its progress shown on the note's card
Notes that repeat daily, weekly, monthly or yearly
A calendar that shows every note on its day
Change one day of a repeating note, or move it to another date
Search, sort, group by category, pin, or arrange the list by hand
Templates for the notes you write often
A Trash to restore deleted notes from
Attach files and pictures to a note
A built-in calculator that writes the sum into your note
Spelling checked with Windows' own dictionaries
A full backup in one .zip file, to move your notebook to another computer
Export a note as a web page or plain text
Eight light and dark themes
Your notes stay in a folder on your computer, even if you uninstall the app
```

### What's new in this version

Up to 1,500 characters; at every release, exactly what changed.

```
The first release of Note Organizer in the Microsoft Store.
```

### Search terms

Up to 7 terms and 21 different words in all; customers never see them.

```
offline notes
note taking
checklist
notes with tables
recurring notes
notes calendar
private notes
```

### Copyright and trademark info

Up to 200 characters.

```
© 2026 Alexandra Moldovan. Note Organizer is free software under the MIT License.
```

### Developed by

Up to 255 characters; optional.

```
Alexandra Moldovan
```

### Additional license terms

Left empty: the Store's standard terms apply. The app's own license and those of what ships with
it open from **Settings → About** in the app.

### Screenshots

Desktop pictures: PNG, at least 1366×768, up to 10, at least four recommended. They are retaken
on the version released by `tools/doc_screenshots.py`, the script that takes the repository's
pictures ([how](screenshots/README.md)), so they show what people install. The set, in order,
with the caption each one carries:

| # | Picture | Caption |
|---|---|---|
| 1 | `main-window` (dark) | Your notes, with a table right in the note |
| 2 | `main-window-light` | Eight themes, light and dark |
| 3 | `calendar-view` | Every note on its day, repeating ones included |
| 4 | `recurrence-setup` | Notes that repeat, on your schedule |
| 5 | `checklist` | A checklist in any note |
| 6 | `search-and-sort` | Search, sort, group and pin |
| 7 | `templates-panel` | Templates for the notes you write often |
| 8 | `settings-overview` | Backup, Trash and settings on one page |

`checklist.png` (1426×622) and `recurrence-setup.png` (1407×909) are crops in the repository,
the first lower than the Store's 768; the Store's set takes the whole window for both.

## Properties

Partner Center → the product → Properties.

| Field | Value | Why |
|---|---|---|
| Category | Productivity | |
| Privacy policy URL | `https://sites.google.com/view/noteorganizer-privacy` | `PRIVACY_URL`, the page **Settings → About** opens; [required](RELEASE_WINDOWS.md#what-the-listing-needs) |
| Website | *empty* | [Kept apart](../site/README.md#kept-apart-from-the-apps) |
| Support contact info | `noteorganizer.app@gmail.com` | The project's own address, never a personal one |
| This product accesses, collects or transmits personal information | No | The app connects to nothing and collects nothing |
| This app has been tested to meet accessibility guidelines | Not ticked | [Decided](#decided) |
| Customers can install this app to alternate drives or removable storage | Ticked (the default) | The notebook is in the profile folder, wherever the app is installed |
| Windows can include this app's data in automatic backups to OneDrive | The default | The notes are not in the app's data but in the profile's `Note Organizer` folder |
| System requirements, minimum | Keyboard, mouse; memory 2 GB | Proved in Windows Sandbox with 2 GB ([the look proof](RELEASE_WINDOWS.md#packing-it-and-proving-it-in-windows-sandbox)) |

## Age rating

The IARC questionnaire, asked one question at a time. The expected result is the lowest rating
(3+, Everyone).

| Question | Answer | Why |
|---|---|---|
| Category of the product | Productivity or utility: not a game, not social or communication | |
| Violence, fear, sexual content, language, drugs, gambling | No, to each | |
| Users interact or exchange content with other users | No | A share code is text the person copies and pastes; nothing goes online |
| Shares the user's location | No | |
| Digital purchases | No | |
| Unrestricted internet access, such as a browser in the app | No | The app opens two fixed pages in the system's browser: the privacy policy and, once there is one, its Store page |
| Advertising | No | |

## Pricing and availability

| Setting | Value | Why |
|---|---|---|
| Markets | Every market but China | `sites.google.com`, where the privacy policy lives, is blocked in mainland China ([what the listing needs](RELEASE_WINDOWS.md#what-the-listing-needs)) |
| Price | Free, no trial | |
| Visibility, first submission | Private audience: the page only for the people listed | The [rollout's](RELEASE_WINDOWS.md#rolling-out-and-stopping-a-release) first step; public once the package installed from the Store has been tried |
| Publish date | As soon as certified | Private, so nobody else sees it yet |

## Notes for certification

Submission options → Notes for certification.

```
Note Organizer is a desktop app (Python with Tkinter, packaged with PyInstaller) for writing notes offline. It needs no account, no sign-in and no network connection, and it connects to nothing.

It keeps its notebook in a folder named "Note Organizer" in the user's profile folder, outside the package, so that uninstalling the app leaves the person's notes; the privacy policy says so. A new install opens on a welcome note that explains each part of the app.

The App Certification Kit reports two non-failing results: the optional "Blocked executables" test finds CreateProcessW in the PyInstaller launcher, Python and Tcl, ShellExecuteW in Python, and names of system programs inside Tcl's scripts and, as chance letters, inside binary files. The app starts no program by name; it only opens a file, a folder or a web page with the program Windows chooses. The DPI awareness warning is expected: the app declares system awareness itself at start, when its Sharp text setting is on.
```

The two results are explained at length in the release guide's
[certification kit](RELEASE_WINDOWS.md#the-certification-kit-wack).

## Decided

The owner's choices, 2026-11-25:

- **The publisher's name is Alexandra Moldovan**, typed once when the account is made. An
  Individual account publishes under a person's name (Store Policy 10.14), and it is the name
  the privacy policy, the license and the copyright line already use.
- **The description does not mention the source code on GitHub.** The repository's README links
  the project's site, which the apps' users are kept apart from; the copyright line says the app
  is free software under the MIT License, without a link.
- **The accessibility box stays unticked.** It is optional: a promise that the app was tested
  with a screen reader, high contrast and Magnifier, which earns an Accessible tag. A screen
  reader cannot read most of the window: Tk 8.6, which the app is drawn with, describes almost
  none of its controls to Windows ([Known limitations](../README.md#known-limitations)). Tk 9.1
  reads to screen readers on Windows, but Python 3.13 ships Tk 8.6.15, and the app's drawn
  tables and hand-built windows would each need describing too.

## To check once the listing is live

- **Who answers a review.** The privacy policy says replies come "as Note Organizer". If the
  Store shows them under the publisher's name instead, the policy's sentence changes first, by
  the [privacy page's steps](RELEASE_WINDOWS.md#the-privacy-page-at-every-release).
- **The review link and the uninstall**, on the package installed from the Store: both are in
  [what the listing needs](RELEASE_WINDOWS.md#what-the-listing-needs).
