# Publish recovery: what to do when a deploy is ambiguous or fails

## Netlify

- **Auth error** (not logged in / bad token): run `netlify login`, or pass
  `--auth <token>` for a non-interactive environment. Retrying without
  fixing auth fails identically.
- **Build or upload error, no URL printed**: nothing was published; fix
  the reported error and rerun. Safe to retry once the underlying problem
  is fixed.
- **Command succeeded but you're not sure it's the version you meant**:
  Netlify keeps full deploy history per site (visible in the team/site
  dashboard), so you can always confirm (or roll back to) a specific
  prior deploy rather than guessing from the CLI output alone.

## Surge

- **Command hangs or is interrupted before `Success!` prints**: state is
  ambiguous: some edge nodes may have the new revision, some the old one.
  Don't tell the user it's live; rerun `surge <dir> <domain>` to push a
  consistent revision to every node.
- **Need to undo a bad publish**: Surge keeps a revision history per
  domain; this is a real, built-in feature, not something you have to
  engineer yourself:
  ```bash
  surge list <domain>       # see recent revisions
  surge rollback <domain>   # revert to the previous revision
  surge rollfore <domain>   # move forward again if you rolled back too far
  ```
  Prefer this over re-uploading an old local copy from memory; the
  revision history is the authoritative record of what was actually
  served.
- **First publish to a brand-new domain asks for email/password**: that's
  Surge's account setup, not a failure; follow the prompt once per
  machine/account.

## GitHub Pages

- **Push succeeds but the site doesn't reflect it yet**: Pages builds
  asynchronously after the push; wait and recheck the build status or the
  URL itself rather than assuming the push alone means it's live.
- **Need to undo a bad publish**: `git revert` the offending commit on the
  Pages branch and push again; normal git history, no special recovery
  path needed.

## The general rule

An ambiguous or interrupted deploy is a "don't know yet" state, not a
"failed" or "succeeded" state; investigate using that option's own
history/status mechanism (above) before claiming either. Only retry blind
when you've confirmed nothing live actually changed yet.
