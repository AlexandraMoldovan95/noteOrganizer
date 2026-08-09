# Roadmap

Planned work and open ideas, roughly ordered by how soon they're likely to happen. Nothing here is a promise or a deadline — this is a working list for a project developed in spare time by a small team of two.

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
