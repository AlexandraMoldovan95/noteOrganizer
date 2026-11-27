# Microsoft Store listing

What people read on the app's page in the Microsoft Store, and every value typed into Partner
Center for it, kept here so the listing says what the app does, no more and no less, and
changes with it. Each field is in a block, ready to paste as it is. The listing is in English,
like the app.

Version 1.0.0 was submitted for certification on 2026-11-25, to a private audience first, and
made public on 2026-11-27; 1.0.1 follows, offered on every Windows 11. Every claim was checked
against the [user guide](USER_GUIDE.md), the [README](../README.md) and the
[privacy policy](PRIVACY.md) at 0.103.558. What follows is what the submissions hold, page by
page, in the order Partner Center asks for it.

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

- [Product identity](#product-identity)
- [Store listing](#store-listing)
- [Properties](#properties)
- [Age rating](#age-rating)
- [Pricing and availability](#pricing-and-availability)
- [Packages](#packages)
- [Submission options](#submission-options)
- [Notes for certification](#notes-for-certification)
- [Decided](#decided)
- [To check once the listing is live](#to-check-once-the-listing-is-live)

## Product identity

What Partner Center assigned when the name was reserved, on 2026-11-25, under an Individual
account. The package carries the first three (`tools/msix/build_msix.py` has them as its
default), and **Settings → About → Feedback** opens the review link (`STORE_REVIEW_URL` in
`noteorganizer/core/diagnostics.py`). A reservation that is not published within three months
is removed: the app is published before 2027-02-25.

| Value | |
|---|---|
| `Package/Identity/Name` | `AlexandraMoldovan.NoteOrganizer` |
| `Package/Identity/Publisher` | `CN=64AA2E20-9F7F-4AD8-B932-ABAFCE65CBA2` |
| `Package/Properties/PublisherDisplayName` | `Alexandra Moldovan` |
| Package family name | `AlexandraMoldovan.NoteOrganizer_j1h13h1gyzgr8` |
| Store ID | `9NBS2548QTXF` |
| The Store's page | `https://apps.microsoft.com/detail/9NBS2548QTXF` |
| Its review link | `ms-windows-store://review/?ProductId=9NBS2548QTXF` |

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
• It runs on every version of Windows 11, not on Windows 10.

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

Up to 1,500 characters. Left empty at the first submission, as Partner Center's own hint asks
("Leave blank if this is the first submission for this product"), and at the second, which only
made 1.0.0 public; from the next release on, exactly what changed. For 1.0.1:

```
Note Organizer now installs on every version of Windows 11. Until now the Store offered it only from version 24H2.
```

### Search terms

Partner Center calls them Keywords, under Additional information: each typed and followed by
Enter. Up to 7 terms, 40 characters each and 21 different words in all; customers never see
them. The keywords the field offers to suggest with AI are not taken: they could name what the
app does not do.

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
on the version released by the `store` scene of `tools/doc_screenshots.py`, the script that
takes the repository's pictures ([how](screenshots/README.md)), so they show what people
install. Each is the whole window: some of the guide's pictures are crops, lower than the
Store's 768. They are uploaded from `dist/store/`, beside the package, and not kept in the
repository. The set, in order, with the caption each one carries:

| # | Picture | Caption |
|---|---|---|
| 1 | `store-1-main` (dark) | Your notes, with a table right in the note |
| 2 | `store-2-light` | Eight themes, light and dark |
| 3 | `store-3-calendar` | Every note on its day, repeating ones included |
| 4 | `store-4-repeat` | Notes that repeat, on your schedule |
| 5 | `store-5-checklist` | A checklist in any note |
| 6 | `store-6-search` | Search, sort, group and pin |
| 7 | `store-7-templates` | Templates for the notes you write often |
| 8 | `store-8-settings` | Backup, Trash and settings on one page |

### Left empty

Store logos (the 9:16 poster art and 1:1 box art, required only on Xbox), the Store display
images (the Store uses the package's own icons without them), trailers and the 16:9 hero art
that goes with them, the Xbox images, and the short and voice titles.

## Properties

Partner Center → the product → Properties.

| Field | Value | Why |
|---|---|---|
| Category | Productivity, no subcategory (it has none), no secondary category | |
| Does this product access, collect, or transmit personal information? | Yes | Store Policy 10.5.1 counts every Win32 product as accessing personal information, so it always needs a privacy policy, and the field for one comes with Yes. The app sends nothing, but it keeps a person's notes on their own computer; the policy says so |
| Privacy policy URL | `https://sites.google.com/view/noteorganizer-privacy` | `PRIVACY_URL`, the page **Settings → About** opens; [required](RELEASE_WINDOWS.md#what-the-listing-needs) |
| Website | *empty* | [Kept apart](../site/README.md#kept-apart-from-the-apps) |
| Support contact info | `noteorganizer.app@gmail.com` | The project's own address, never a personal one |
| Phone number, address | *empty* | Optional, and shown on the public page when given |
| Display mode (PC, HoloLens) | Not ticked | For Mixed Reality apps; the boundary setup under it is ignored then |
| Allows purchases outside the Store's commerce system | Not ticked | It sells nothing |
| Tested to meet accessibility guidelines | Not ticked | [Decided](#decided) |
| Customers can install to alternate drives or removable storage | Ticked (the default) | The notebook is in the profile folder, wherever the app is installed |
| Windows can include this product's data in automatic backups to OneDrive | Ticked (the default) | The notes are not in the app's data but in the profile's `Note Organizer` folder |
| Customers can record and broadcast clips | Not ticked | For games only, as Partner Center's warning under it says |
| Supports pen and ink input | Not ticked | It has nothing of its own for a pen |
| Incorporates generative AI features | Not ticked | The app has none; that an AI agent helped build it is not what the question asks |
| System requirements, minimum | Keyboard, mouse; memory 2 GB; the rest not specified, processor and graphics empty | Proved in Windows Sandbox with 2 GB ([the look proof](RELEASE_WINDOWS.md#packing-it-and-proving-it-in-windows-sandbox)); the Store reads the processor from the package (x64) |
| System requirements, recommended | *empty* | |

## Age rating

The IARC questionnaire (version 10.4), as Partner Center asked it, with the owner's agreement to
IARC's terms of use given there.

| Question | Answer | Why |
|---|---|---|
| App type | All other app types | Not a game, not social or communication |
| Ratings-relevant content (sex, violence, language) in the package | No | |
| Users interact or exchange content with other users | No | A share code is text the person copies and pastes; nothing goes online |
| Online content not in the download, reached from the app | No | It opens two fixed pages in the system's browser: the privacy policy and its Store page |
| Promotes or sells age-restricted products or activities | No | |
| Shares the user's precise location | No | |
| Digital purchases | No | |
| Cash rewards, gift cards, play-to-earn, cryptocurrency, NFTs | No | |
| A web browser or search engine | No | |
| Primarily a news or educational product | No | |
| Ratings from a ratings board, or physical media | No | |

The ratings it gave, the lowest everywhere: IARC 3+, PEGI 3, ESRB Everyone, USK 0, and "all
ages" in Brazil, Chile and Russia, with no interactive elements.

## Pricing and availability

| Setting | Value | Why |
|---|---|---|
| Markets | All worldwide markets but China | `sites.google.com`, where the privacy policy lives, is blocked in mainland China ([what the listing needs](RELEASE_WINDOWS.md#what-the-listing-needs)); China also asks for papers the app has no need of |
| Future markets | Ticked: any market Microsoft adds, at the base price | Free, so free there too |
| Base price | Free: shown as 0 in whichever currency is chosen | |
| Free trial, sale pricing | None | |
| Organizational licensing | The default | |
| Audience, first submission | Private: a known user group, "test Note Organizer", of personal Microsoft accounts (the owner's and one tester's) | The [rollout's](RELEASE_WINDOWS.md#rolling-out-and-stopping-a-release) first step: the package the Store signed, tried before anyone else sees it. Microsoft asks for no testers; a work or school account cannot see a private app |
| "Make this product public on" | Not ticked, no date | It goes public by a new submission, once tried, never by itself |
| Discoverability | Available and discoverable | While private, it applies only to the group |
| Schedule, publishing hold | As soon as certified | Private, so nobody else sees it yet |

While it is private, the group installs it from its own link,
`https://apps.microsoft.com/detail/restricted/9NBS2548QTXF`, signed in to the Microsoft Store
app with the account in the group, on a Windows the package accepts; the ordinary page and search
do not show it. Once public, it cannot go back to a private audience; 1.0.0 went public on
2026-11-27, by a second submission that changed the audience alone.

## Packages

One package per release, from `dist/msix/`, never the one a build higher beside it (the
Sandbox's update test): `NoteOrganizer_1.0.0.0.msix` for 1.0.0, validated as version 1.0.0.0,
x64, `Windows.Desktop` from 10.0.26100.0; `NoteOrganizer_1.0.1.0.msix` for 1.0.1, from
10.0.22000.0, every Windows 11 ([which Windows](RELEASE_WINDOWS.md#which-windows)). Device
family: Windows 10/11 Desktop only, and "Let Microsoft decide whether to make this app
available to any future device families" unticked: what was never tried is not declared.

Its one warning is expected: `runFullTrust`, the restricted capability every packaged desktop
app of this kind declares, needs approval, asked for under Submission options.

## Submission options

Publishing hold: as soon as it passes certification. Restricted capabilities, "Why do you need
the runFullTrust capability, and how will it be used in your product?":

```
Note Organizer is a desktop (Win32) app written in Python with Tkinter and packaged with PyInstaller, then as MSIX. runFullTrust is what lets a desktop app of this kind run as it does outside the Store. It uses no other restricted capability, connects to nothing, and keeps the user's notes in a folder in their own profile.
```

## Notes for certification

Not under Submission options any more: Partner Center keeps them on a page of their own, the
product's Supplemental info → Additional Testing Information, saved with Save description.
No credentials: the app has no account.

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
  tables and hand-built windows would each need describing too: planned for after the stores
  ([roadmap](ROADMAP.md#under-consideration)).

## To check once the listing is live

First on the private audience, on the package installed from the Store through the group's
link, before a new submission makes it public:

- **The install**: no unknown-publisher warning, Note Organizer in Start, **Settings → About**
  saying 1.0.0, the notes in the profile's `Note Organizer` folder.
- **The page**: its words, the eight pictures and the publisher's name as given here.
- **Write a review** opens that page, ready for a review (test plan case 686, its hand part).
- **Uninstall and reinstall** keep the notes, a backup made first (case 704); its update step
  waits for the first newer version.

Then, once public:

- **Who answers a review.** The privacy policy says replies come "as Note Organizer". If the
  Store shows them under the publisher's name instead, the policy's sentence changes first, by
  the [privacy page's steps](RELEASE_WINDOWS.md#the-privacy-page-at-every-release).
- **Markets**: the page opened from a market other than the owner's, to see it offered there.
  Why the review link and the uninstall are checked at all is in
  [what the listing needs](RELEASE_WINDOWS.md#what-the-listing-needs).
