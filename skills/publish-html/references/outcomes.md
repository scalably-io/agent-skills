# Publish outcomes: how to tell a deploy actually succeeded

Each of the three publish options prints its own success signal. Read the
signal, don't infer success from "the command didn't error."

## Netlify

`netlify deploy --prod --dir <dir>` prints the live production URL to
stdout on success, after the CLI's own build/upload/propagation steps
finish. Pass `--json` to get the deploy metadata as machine-readable JSON
instead, for scripting. A non-zero exit code (auth failure, build failure,
bad `--dir`) means nothing was published; don't paste a guessed URL.

## Surge

`surge <dir>` (or `surge <dir> <domain>` for an explicit subdomain) prints
`Success! - Published to <domain>` only once every edge node has confirmed
it is serving the new revision; Surge's own docs describe this as files
uploading once, then propagating to every edge node while the command
runs, each node individually confirming what it now serves. Until that
exact `Success!` line appears, treat the deploy as unconfirmed: an
interrupted `surge` command can leave some nodes serving the old revision
and some the new one.

## GitHub Pages

`git subtree push --prefix <dir> origin gh-pages` (or an equivalent push to
the branch/folder your repo's Pages source points at) only pushes the
commit; it does not, by itself, confirm the page is live. GitHub Pages
builds asynchronously after the push; check the repo's Pages build status
(Settings → Pages, or `gh api repos/<owner>/<repo>/pages/builds/latest`)
or simply fetch the published URL yourself and look for the new content
before telling the user it's live.

## The general rule

Regardless of which option you used: don't tell the user a URL is live
until you've seen that option's own success signal (above), or, failing
that, fetched the URL yourself and confirmed it serves the new content.
"The command exited 0" and "the URL looks reachable from memory" are both
insufficient on their own.
