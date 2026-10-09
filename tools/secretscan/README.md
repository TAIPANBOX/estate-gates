# secretscan

A gate that refuses a secret on its way into a repository and never prints one.
Since 2026-10-09 it runs in this repository's CI (invariant 23). Other
repositories wire it themselves, section 5.

## 1. Why another scanner

The estate audit of 2026-10-08 found three shapes that the one existing check
(typryx's `scripts/no-secrets.sh`, vendor prefixes only) cannot see:

| Shape | Example (masked) | Why a prefix rule misses it |
|---|---|---|
| F3: a bare value after a secret-named key | `API_KEY="8b43****9b(len 64)"` | 64 hex characters carry no vendor prefix |
| F6: a passphrase written into prose | ``SSID key: `4wzt****rp(len 14)` `` | it is a sentence, not an assignment |
| keys with no vendor prefix at all | `client_secret: <40 base62>` | nothing to anchor on but the name |

So there are three rule families, and one allowlist to keep the false positives
from turning the gate off.

## 2. Rules

1. **Vendor formats.** Anthropic, OpenRouter, OpenAI project and service keys,
   AWS access key ids, GitHub tokens, Google API keys, Slack, Stripe live keys,
   Tailscale, Telegram bot tokens, Hugging Face, PEM private key headers, and
   credentials inside a URL. The shape alone is the evidence.
2. **Assignment.** `NAME = VALUE` in the forms the estate writes (shell and
   `.env`, YAML, JSON, Go, Rust, Python, TOML, `docker -e`). The name is read as
   words, so `API_KEY`, `apiKey`, `client_secret` and `SERVICE_TOKEN` count and
   `tokenfuse_core`, `est_input_tokens`, `withCredentials` do not. A name that is
   about a secret (`*_SCOPES`, `*_REF`, `*_FILE`, ...) or names a mock does not
   count. The value must look like key material: 32+ hex characters, or 20+
   characters with entropy of at least 3.5 bits and two character classes. A
   reference (`$VAR`, `${VAR:?}`, `$(...)`, `os.Getenv`, `{{ }}`), a path, a
   format string, a flag or a file name is not a value.
3. **Passphrase in text.** A password word (`password`, `passphrase`, `psk`,
   `SSID key`, `Wi-Fi password`, `пароль`, ...) followed on the same line by a
   quoted token of 8 to 64 characters that mixes letters with digits or
   symbols; and OpenWrt's `option key '...'`.

Placeholders are skipped everywhere: `example`, `changeme`, `dummy`, `fake`,
`mock`, `demo`, `test` as a word, `never-leak`, `synthetic`, `<...>`, one
repeated character, `12345678`. A line carrying `secretscan:allow` is skipped.

## 3. Output and exit codes

```
path:line: rule abcd****yz(len N) fp=<16 hex>
```

Four leading and two trailing characters, the length, and a fingerprint (the
first 16 hex of SHA-256). **Nothing ever prints a value**, and a test plants a
value and requires that it does not reach stdout or stderr.

| Exit | Meaning |
|---|---|
| 0 | clean, with the number of files or lines read |
| 1 | findings |
| 2 | usage or git error |
| 3 | measured nothing: `tree` or `history` read no content, which is not a pass |

## 4. Allowlist

`.secretscan-allow` at the repository root, one entry per line:

```
d7e4e536aea985ea  docs/rfc/*.md  # RFC test vector, published by the RFC
```

It names a fingerprint and a path glob (`**/` allowed), never a value, so the
file can be public. **The reason is mandatory**: an entry without one is a
load error, because an exception nobody can re-derive is how a gate goes soft.
`tree` and `history` report an entry that matched nothing, so stale entries do
not accumulate; `push` does not, since a push carries a few lines and every
other entry is unused there by definition.

## 5. Where it runs

- **pre-push hook**, every repository, private ones included:
  `secretscan push` reads git's pre-push stdin and scans only the lines being
  pushed; a new branch is scanned against what the remote already has.
- **the hourly memory sync** that pushes `~/.claude` memory to
  `TAIPANBOX/claude-memory`: `secretscan diff <last-pushed>..HEAD` before the
  push.
- **public CI**: `secretscan tree` as a step. Free on public repositories;
  on a private one it would be metered, so the hook is the place there.

## 6. Measured on 2026-10-09

- **Tests**: 8 functions, coverage 85.5% of statements. Every rule and filter
  was broken on purpose and a test went red for each (15 mutants: no
  assignment rule, no prose rule, a mask that leaks, the glob ignored, an empty
  tree passing, the placeholder check off, the reference check off, the name
  words off, the value-shape filter off, default URL credentials off, the
  prose identifier filter off, the about-a-secret suffixes off, the mock words
  off, the user-equals-password check off, and the SSID-key wording off).
- **Real findings**: `tree origin/main` on TAIPANBOX/noesis exits 1 with the
  three Postiz literals (F3) that noesis#1 then removed; `history` on
  TAIPANBOX/YouTube finds the same key in six scripts of its history; `history`
  on TAIPANBOX/homelab finds the F6 passphrase in a session note.
- **Noise**: `tree` at HEAD over 19 estate repositories: 15 clean, 34 findings
  in 4, every one a fixture of a detector or crypto suite (tokenfuse's DLP and
  injection tests, qryx's PEM detector tests, genaryx and verdryx test JWTs and
  PEM headers). Those four would each carry an allowlist. The first version of
  the rules, before names were read as words, produced about 240 on the same
  set, 176 of them in tokenfuse alone.

## 7. What it does not do

- It cannot tell a live key from a revoked one, and it never tries: it does not
  call any service with anything it finds.
- A secret split across lines, base64-wrapped, or built at run time from parts
  is invisible to it. So is a short password with no password word near it.
- Entropy thresholds are a judgement: a 19-character random value assigned to a
  secret name passes. Raising the floor trades misses for noise, and the
  measured noise above is the reason the floor sits where it does.
- It scans text: a key inside a binary, an archive or an image is skipped.
