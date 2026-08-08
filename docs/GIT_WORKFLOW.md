# Git Workflow — my cheat sheet

Not a general Git tutorial — just the exact commands I actually use on this project, organized by "what am I trying to do right now."

---

## Scenario A: Small fix, straight to `main`

Use this for most day-to-day changes — a bug fix, a doc update, anything that doesn't need a trial run.

```powershell
# 1. Put the new/updated file(s) in place (replace the old ones)

# 2. See what changed
git status

# 3. Stage everything, commit, send it
git add .
git commit -m "fix: short description of what changed"
git push
```

**Commit message prefixes I use:**
| Prefix | When |
|---|---|
| `fix:` | Bug fix |
| `feat:` | New feature |
| `perf:` | Performance improvement |
| `docs:` | Documentation only |
| `refactor:` | Code restructuring, no behavior change |
| `chore:` | Housekeeping (deps, config, cleanup) |

If a commit resolves a GitHub Issue, add `(Fixes #N)` at the end of the message — closes the issue automatically on push.

---

## Scenario B: Trying something out, want to test before it's "real"

Use this when I'm not sure yet if I'll like the result (e.g. a UI change), or want a proper PR-review exercise.

```powershell
# 1. Create a branch and switch to it, in one step
git checkout -b feature/short-name

# 2. Confirm I'm on it (look for the *)
git branch

# 3. Put the new file(s) in place, rebuild, TEST IT LOCALLY
#    (rebuild never touches Git — it's just for me to look at)

# 4. Happy with it? Commit + push (first push on a new branch needs one extra flag):
git add .
git commit -m "feat: short description"
git push
#    ^ if this errors about "no upstream branch", copy-paste the exact
#      command it suggests (git push --set-upstream origin <branch-name>)

# 5. Go to GitHub -> open the "Create pull request" link it gave me
#    -> fill in title/description -> Create pull request

# 6. Review the diff on the PR page, then click "Merge pull request" -> Confirm

# 7. Back in terminal, bring main up to date locally:
git checkout main
git pull

# 8. Clean up the now-merged local branch (optional, but tidy):
git branch -d feature/short-name
```

**Not happy with the result on step 4?** Don't commit. Ask for an adjusted file, replace it again, rebuild again, repeat until it looks right — nothing is "saved" in Git until I actually commit.

---

## Quick reference — what am I looking at?

```powershell
git status              # what's changed, staged vs not
git branch               # which branch am I on (marked with *)
git log --oneline -5     # last 5 commits, one line each
```

## Two commits in one change (code + docs together)

If I'm updating a `.md` file to match a code change, and I forgot to include it before pushing:

```powershell
git add .
git commit -m "docs: catch-up description"
git push
```

That's it — a second, small commit is completely normal and fine. Doesn't need to be perfect in one shot.

## Things I don't need to worry about

- `build/` and `dist/` — never tracked by Git (`.gitignore` handles it), no matter how many times I rebuild
- `notes_data.json` / `settings.json` / `attachments/` — same, personal data never gets committed
- Deleting a branch on GitHub after merge — doesn't touch the code, it's already safely in `main`
