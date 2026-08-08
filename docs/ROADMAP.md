# Roadmap

Planned work and open ideas, roughly ordered by how soon they're likely to happen. Nothing here is a promise or a deadline — this is a working list for a project developed in spare time by a small team of two.

## Near-term

- **Multi-select notes for bulk actions.** Select several notes from the list at once (like an email client) and move them all to trash, or reassign them all to a different category, without opening each one individually.
- **Attachments shown inline.** Currently, opening an attached image opens it in an external viewer. Showing a preview directly in the app (with the option to still open/download it) would be more convenient.
- **Delete a note directly from the calendar.** Right now, removing a note found via the calendar means opening it in the editor first. A direct delete action on the calendar day view would skip that step for the common case.

## Under consideration

- **Rich text formatting** (bold / italic / underline / basic font choices) in the note body. This is a real architectural change — the editor is currently a plain `tk.Text` widget with no formatting model — so it needs its own design pass rather than being slotted in alongside smaller fixes.
- **A simple table feature** for structured content within a note.
- **An in-note calculator widget.**
- **Note list virtualization.** The main note list currently builds a full widget per note on every refresh. Trash and the Share panel already cap what they render up front (see [ARCHITECTURE.md](ARCHITECTURE.md)); doing the same for the main list — or true windowed rendering, building only the cards currently scrolled into view — would help further at very large note counts (many hundreds to thousands).
- **Reorganize the codebase into multiple files/modules**, once the single-file layout starts costing more in navigation than it saves in simplicity.

## Exploratory / long-term

- **An Android version.** Nothing decided yet on approach — a full rewrite with a mobile-first toolkit, or a port of the existing logic onto something like Kivy or BeeWare, are both on the table. This is a big enough undertaking that it needs its own scoping pass before any real work starts.

## Explicitly not planned right now

- Tags as a separate feature from categories — removed in 0.3.0 after concluding categories cover the need on their own; revisiting this isn't currently planned.
- Cloud sync / accounts — the app is intentionally offline-only.
