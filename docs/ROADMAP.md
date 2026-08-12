# Roadmap

Planned work and open ideas, roughly ordered by how soon they're likely to happen. Nothing here is a promise or a deadline — this is a working list for a project developed in spare time by a small team of two.

## Known bugs to investigate

Found by hand, not yet worked on. Grouped by area.

**Note list**
- Dragging the scrollbar with only a few notes in the list causes visible flicker and adds unexplained spacing between the top bar and the first note's title. Doesn't happen with a longer list — worth checking whether this is related to the scrollregion calculation only being "exercised" enough to self-correct once there's enough content to actually need scrolling.
- Grouping by category: after expanding the last (previously collapsed) group, editing a note inside it (which autosaves), then collapsing that group again, the note list's scroll position sometimes jumps back to the top instead of staying near where that group was. Hard to reproduce consistently — needs a closer look at what specifically triggers it.

**Settings**
- The "← Back to Notes" button should stay visible at all times (sticky/pinned), not scroll out of view when scrolled further down the Settings page.
- Layout: each section's title is left-aligned, but the action buttons are centered — inconsistent, makes the page harder to scan at a glance ("eye slalom"). Worth a proper design pass, not just a quick alignment fix — see "Settings redesign" below, this is likely folded into that.
- Statistics: hovering looks clickable (the button highlights), but clicking does nothing. Needs its own discussion — see "Statistics: keep, enhance, or relocate?" below.

**Multi-select**
- The bulk "Category" button's text isn't fully visible — the last letter of "Category" is slightly cramped, and the label to its left isn't visible at all. Likely just needs more width or a smaller font in that specific button.

**Sort/filter controls**
- The "Recently updated" label is cut off in the dropdown button itself (before it's even opened) — the last "d" isn't visible. Probably needs a small width adjustment or tighter font.

## Settings redesign (bigger discussion, own design pass)

The current single-column Settings page makes for a lot of scrolling and doesn't clearly separate "which section am I in" from "what are this section's controls." Considering a restructure closer to how Chrome (and similar apps) lay out settings: a narrow column on the left listing every section, and the actual controls for whichever section is selected on the right, with empty space beyond that rather than everything stretched full-width. Not yet decided whether Settings should become an inline popup/modal (opened from the editor or calendar, floating over the app) or stay as a page of its own — worth a dedicated conversation before building anything, since it affects more than just this list of small alignment fixes above.

## Statistics: keep, enhance, or relocate?

Currently looks interactive (hover highlight) but isn't clickable, which is misleading. Options to weigh in a separate discussion: make it genuinely interactive to match how it already looks, give it a visual refresh to feel more worth having, or move it down near "About" on the reasoning that it's a low-traffic feature not worth prime placement. No decision made yet — noted here so it isn't lost, not to be worked on until discussed on its own.

## Versioning

Keep the version number below `1.0.0` until the app actually has a real public launch, so that number stays meaningful (a clean `1.0.0` for the real first release, not used up early). Worth revisiting how updates between now and then get grouped into versions, rather than the current ad-hoc pacing.

## Under consideration

- **Rich text formatting** (bold / italic / underline / basic font choices) in the note body. This is a real architectural change — the editor is currently a plain `tk.Text` widget with no formatting model — so it needs its own design pass rather than being slotted in alongside smaller fixes.
- **A simple table feature** for structured content within a note.
- **An in-note calculator widget.**
- **Note list virtualization.** The main note list currently builds a full widget per note on every refresh. Trash and the Share panel already cap what they render up front (see [ARCHITECTURE.md](ARCHITECTURE.md)); doing the same for the main list — or true windowed rendering, building only the cards currently scrolled into view — would help further at very large note counts (many hundreds to thousands).
- **Reorganize the codebase into multiple files/modules**, once the single-file layout starts costing more in navigation than it saves in simplicity.

## Exploratory / long-term

- **An Android version.** Nothing decided yet on approach — a full rewrite with a mobile-first toolkit, or a port of the existing logic onto something like Kivy or BeeWare, are both on the table. This is a big enough undertaking that it needs its own scoping pass before any real work starts.
- **Whether to move off plain Tkinter entirely**, decided together with the Android question above rather than separately — the two are linked, since a cross-platform-friendly choice could mean rewriting the UI layer once for both desktop and mobile instead of twice. Candidates worth weighing when that scoping pass happens:
  - **PyQt / PySide (Qt for Python)** — far more capable widgets out of the box (native rich text editing, real tables, more polished look), at the cost of a much steeper learning curve, a heavier package, and (for PyQt specifically) a more restrictive license than this project has used so far.
  - **CustomTkinter** — a modern-looking skin built on top of Tkinter itself, meaning the bulk of the current codebase would still apply; the smallest migration cost of the options here, but also the smallest capability jump.
  - **Kivy** — built with touch/mobile in mind, so it's already on the table for the Android question specifically; would mean rebuilding the desktop UI too if adopted, not just extending it.
  - Doing nothing and staying on plain Tkinter remains a legitimate option — noted here so the decision is made deliberately, not by default.

## Explicitly not planned right now

- Tags as a separate feature from categories — removed in 0.3.0 after concluding categories cover the need on their own; revisiting this isn't currently planned.
- Cloud sync / accounts — the app is intentionally offline-only.
