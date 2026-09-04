# Git Workflow — my cheat sheet

The owner's working command reference for this repo; the fuller working agreement (branch rules,
approvals, safety) is [CLAUDE.md's Git & GitHub workflow](../CLAUDE.md#git--github-workflow).

Not a general Git tutorial — just the exact commands I actually use on this project, organized by "what am I trying to do right now."

---

## Scenario A: Trivial docs-only fix, straight to `main`

Only for typo-level, docs-only changes — a spelling fix, a broken link, a one-line wording tweak —
where there's genuinely nothing to test and no need for a trial run. Anything that touches code,
and any docs change bigger than that, goes through Scenario B — that's the project's branch-always
rule (see [CLAUDE.md](../CLAUDE.md#git--github-workflow)).

Put the updated file(s) in place, check what changed, then stage, commit, and send it:

```powershell
git status
git add .
git commit -m "docs: short description of what changed"
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

## Scenario B: A branch and a PR — the normal path for code

Use this for any code change, and for anything I want to test before it's "real" (e.g. a UI
change) or want a proper PR-review exercise on.

Create a branch and switch to it in one step, then confirm I'm on it (look for the `*`). Name it
with one of the project's prefixes — `fix/` `feat/` `refactor/` `test/` `docs/` — per
[CLAUDE.md's Git workflow](../CLAUDE.md#git--github-workflow).

```powershell
git checkout -b feat/short-name
git branch
```

Put the new file(s) in place, rebuild, and **test it locally** — a rebuild never touches Git, it's
just for me to look at.

Happy with it? Commit, run the two-second static gates, then push. `py tools/pre_push_check.py` is
the same set of checks CI runs first — names resolve, class surface unchanged, every `.py`
compiles — and two PRs went red learning that the hard way. The full suite is `tools/run_tests.py`.

```powershell
git add .
git commit -m "feat: short description"
py tools/pre_push_check.py
git push
```

If the push errors about "no upstream branch", copy-paste the exact command it suggests
(`git push --set-upstream origin <branch-name>`).

On GitHub: open the "Create pull request" link the push printed, fill in the title/description,
and click **Create pull request**. Review the diff on the PR page, then click
**Merge pull request** → **Confirm**.

Back in the terminal, bring `main` up to date locally and clean up the now-merged local branch
(optional, but tidy):

```powershell
git checkout main
git pull
git branch -d feat/short-name
```

**Not happy with the result before committing?** Don't commit. Ask for an adjusted file, replace
it again, rebuild again, repeat until it looks right — nothing is "saved" in Git until I actually
commit.

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
