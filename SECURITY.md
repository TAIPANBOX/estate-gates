# Security Policy

estate-gates is the only repository in the TAIPANBOX estate allowed to know
about more than one repository at once: it reads every other repository's
public state to compare their claims against each other, and never writes
to any of them, so its trust boundary is read-only access across the whole
estate.

## Reporting a vulnerability

Please report security issues privately, not in public issues or pull
requests: open a GitHub private security advisory at
<https://github.com/TAIPANBOX/estate-gates/security/advisories/new>. Include
the affected version or commit, a description and a minimal reproduction.
We aim to acknowledge within a few days and to fix high-severity issues
before any public disclosure, with coordinated disclosure within 90 days of
the report. There is no bug-bounty programme; reporters are credited in the
advisory unless they prefer otherwise.

## Supported versions

Before this repository's 1.0, only `main` is supported: fixes land on `main`
and are not backported. From its 1.0 tag, the newest minor gets every fix and
the previous minor gets security-relevant fixes for 90 days after the newer
one is tagged.

## Verifying a build

Every change passes the repository's gates before merge: `./selftest.py`,
`./scripts/no-long-dashes.sh --prove`, `./scripts/features-are-bound.sh --prove`
and `./run-gates.py --mode ref --ref origin/main`.
