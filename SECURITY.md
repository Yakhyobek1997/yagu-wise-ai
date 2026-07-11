# Security Policy

## Supported versions

Auralynq is pre-1.0 (`0.2.0` at the time of writing). There is no long-term
support matrix yet — security fixes land on the latest release on `main`.
Once a `1.0` release ships, this section will name a real supported-version
window instead.

## Reporting a vulnerability

Please **do not open a public GitHub issue** for a suspected security
vulnerability. Instead, use
[GitHub Security Advisories](https://github.com/MHHamdan/Auralynq/security/advisories/new)
for this repository ("Security" tab → "Report a vulnerability"). This opens
a private draft advisory visible only to the maintainer and you, so details
aren't public before a fix ships.

If private reporting isn't available for any reason, open a regular issue
that says only "possible security issue — please contact me privately" with
no technical details, and the maintainer will follow up.

What to expect:

- An initial response acknowledging the report as soon as reasonably
  possible. This is a single-maintainer open-source project, not a company
  with an SLA — please be patient.
- If accepted: a fix, a coordinated disclosure timeline if needed, and
  credit in the advisory/changelog unless you prefer to stay anonymous.
- If declined (e.g. not reproducible, out of scope, or working as intended):
  an explanation of why.

## Scope notes specific to this project

- Auralynq is designed to run **locally by default** with no API key
  required (`AURALYNQ_SERVE__API_KEY` empty = open) — this is intentional
  for local/demo use, not a vulnerability. It becomes a real concern only if
  you expose an Auralynq instance to an untrusted network without setting
  an API key; see `docs/getting-started/server.md` for the recommended
  posture before doing that.
- Document uploads: see `AURALYNQ_ALLOW_UPLOADS` and the file-type/size
  validation in `auralynq/serving/app.py`'s `/ingest` handler. If you find a
  way to bypass the upload validation (path traversal, unsupported file
  types being processed, size limits not enforced), that's a real
  vulnerability report — please use the private channel above.
- Data privacy: Auralynq processes whatever documents you ingest locally by
  default; nothing is sent to a third party unless you configure a
  commercial LLM/embedding/tracing provider (all optional, all documented in
  `.env.example`). If you find a code path that leaks data to a configured
  provider unexpectedly (e.g. bypassing `AURALYNQ_AIR_GAPPED=true`), that's
  a real vulnerability report.
- Third-party dependencies are attributed with their licenses in
  `THIRD_PARTY.md`; a vulnerability in a dependency itself should be
  reported upstream, but let us know too if it affects how Auralynq uses it.
