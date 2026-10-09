// Package main is secretscan: a pre-push and CI gate that refuses a secret on
// its way into a repository, and says what it found without ever printing it.
//
// It exists because the 2026-10-08 estate audit found three shapes that the
// one existing check (typryx's no-secrets.sh, provider prefixes only) could not
// see: a bare 64-hex value after an API_KEY= assignment, a Wi-Fi passphrase in
// the prose of a markdown note, and keys that carry no vendor prefix at all.
// Prefix rules catch the vendors; the assignment and prose rules catch the
// rest; the allowlist keeps the false positives from turning the gate off.
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"math"
	"regexp"
	"strings"
)

// Finding is one value that looks like a secret. Value is kept only so the
// caller can fingerprint it; nothing in this program ever prints it.
type Finding struct {
	Path  string
	Line  int
	Rule  string
	value string
}

// Masked shows four leading and two trailing characters and the length.
func (f Finding) Masked() string { return mask(f.value) }

// Fingerprint is what an allowlist entry names: never the value itself.
func (f Finding) Fingerprint() string { return fingerprint(f.value) }

func mask(v string) string {
	r := []rune(v)
	if len(r) < 10 {
		return "****(len " + itoa(len(r)) + ")"
	}
	return string(r[:4]) + "****" + string(r[len(r)-2:]) + "(len " + itoa(len(r)) + ")"
}

func fingerprint(v string) string {
	sum := sha256.Sum256([]byte(v))
	return hex.EncodeToString(sum[:8])
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var b [20]byte
	i := len(b)
	for n > 0 {
		i--
		b[i] = byte('0' + n%10)
		n /= 10
	}
	return string(b[i:])
}

// prefixRule is a vendor format: the shape alone is the evidence.
type prefixRule struct {
	name string
	re   *regexp.Regexp
	// group is the submatch holding the secret, 0 for the whole match.
	group int
}

var prefixRules = []prefixRule{
	{"anthropic-key", regexp.MustCompile(`sk-ant-[a-z]{2,8}\d{2}-[A-Za-z0-9_-]{20,}`), 0},
	{"openrouter-key", regexp.MustCompile(`sk-or-v1-[0-9a-f]{32,}`), 0},
	{"openai-key", regexp.MustCompile(`\bsk-(?:proj|svcacct|admin)-[A-Za-z0-9_-]{20,}`), 0},
	{"aws-access-key-id", regexp.MustCompile(`\b(?:AKIA|ASIA)[0-9A-Z]{16}\b`), 0},
	{"github-token", regexp.MustCompile(`\bgh[pousr]_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{60,}`), 0},
	{"google-api-key", regexp.MustCompile(`\bAIza[0-9A-Za-z_-]{35}\b`), 0},
	{"slack-token", regexp.MustCompile(`\bxox[abposr]-[A-Za-z0-9-]{10,}`), 0},
	{"stripe-live-key", regexp.MustCompile(`\b[rs]k_live_[A-Za-z0-9]{20,}`), 0},
	{"tailscale-key", regexp.MustCompile(`\btskey-[a-z]+-[A-Za-z0-9]{6,}-[A-Za-z0-9]{10,}`), 0},
	{"telegram-bot-token", regexp.MustCompile(`\b\d{8,10}:AA[A-Za-z0-9_-]{33}\b`), 0},
	{"huggingface-token", regexp.MustCompile(`\bhf_[A-Za-z0-9]{34,}\b`), 0},
	{"private-key-block", regexp.MustCompile(`-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED |PGP )?PRIVATE KEY(?: BLOCK)?-----`), 0},
	{"url-credentials", regexp.MustCompile(`\b[a-z][a-z0-9+.-]*://([^/\s:@'"<>]{1,64}):([^/\s@'"<>]{6,128})@[^\s/'"<>]+`), 2},
}

// assignRe is NAME = VALUE in the shapes the estate writes: shell and .env,
// YAML, JSON, Go, Rust, Python, TOML, docker -e. The name must say secret.
var assignRe = regexp.MustCompile(`(?i)([A-Za-z0-9_.-]*(?:api[_-]?key|apikey|secret|token|passw(?:or)?d|passphrase|psk|private[_-]?key|access[_-]?key|credential|auth[_-]?key|bearer)[A-Za-z0-9_.-]*)["']?\s*(?::=|=>|=|:)\s*(["'` + "`" + `]?)([^\s"'` + "`" + `,;)]+)`)

// proseRe is a password word followed, on the same line, by a quoted token:
// the shape of a passphrase written into a note. It also reads OpenWrt's UCI
// `option key '...'`, which is where a router's Wi-Fi passphrase lives.
var proseRe = regexp.MustCompile(`(?i)(?:\b(?:password|passphrase|passcode|psk|wpa[23]?[ -]?key|(?:ssid|wi-?fi|wlan|wireless|network)[ -]?(?:key|pass(?:word|phrase)?))\b|пароль)[^\n"'` + "`" + `«]{0,40}["'` + "`" + `«]([^"'` + "`" + `»\s]{8,64})["'` + "`" + `»]`)
var uciKeyRe = regexp.MustCompile(`^\s*option\s+key\s+['"]([^'"]{8,63})['"]`)

var placeholderRe = regexp.MustCompile(`(?i)example|placeholder|changeme|change[_-]me|dummy|fake|sample|demo|mock|redacted|your[_-]|xxxx|todo|insert|replace|never[_-]?leak|synthetic|canary|not[_-]?a[_-]?real|(?:^|[^a-z])test(?:[^a-z]|$)|<[^>]*>|\.\.\.|…`)

var referenceRe = regexp.MustCompile(`^(?:\$|%|\{\{|<|@|&|\*)|\(|\bos\.|\benv\b|getenv|environ|process\.env|secretKeyRef|valueFrom|\$\{`)

var identRe = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_.:-]*$`)

var camelRe = regexp.MustCompile(`([a-z0-9])([A-Z])`)

// secretName reads an assignment's name as words, so `tokenfuse_core`,
// `est_input_tokens` and `withCredentials` are not secrets and `API_KEY`,
// `apiKey`, `client_secret` and `SERVICE_TOKEN` are. The first version
// matched substrings and flagged 176 lines of one repository, most of them
// Rust paths through `tokenfuse_core::`.
func secretName(name string) bool {
	words := strings.FieldsFunc(strings.ToLower(camelRe.ReplaceAllString(name, "${1}_${2}")), func(r rune) bool {
		return !(r >= 'a' && r <= 'z' || r >= '0' && r <= '9')
	})
	if len(words) > 0 {
		// A name ending in one of these is ABOUT a secret: which scopes it
		// grants, where it is referenced from, how it is named.
		switch words[len(words)-1] {
		case "scopes", "scope", "ref", "refs", "name", "names", "file", "path", "id", "ids", "env", "var", "kind", "type", "len", "length", "hash", "fingerprint", "url", "header", "prefix", "policy", "count":
			return false
		}
	}
	for _, w := range words {
		switch w {
		case "mock", "fake", "dummy", "example", "sample", "test", "fixture":
			return false
		}
	}
	for i, w := range words {
		switch w {
		case "apikey", "secret", "token", "password", "passwd", "pwd", "passphrase", "psk", "credential", "bearer":
			return true
		case "key":
			if i > 0 {
				switch words[i-1] {
				case "api", "access", "private", "secret", "auth", "signing", "master", "encryption", "client", "service", "admin", "ingest", "deploy", "license", "app":
					return true
				}
			}
		}
	}
	return false
}

// notAValue is the shape of what follows a secret-named key in code and docs
// without being a secret: a path (`::agent`), a format string (`{res...}`),
// a flag (`-set...`), a file name, an escape sequence.
var notAValueRe = regexp.MustCompile(`^[:{\-]|\\|\.(?:sh|py|go|rs|ts|js|json|ya?ml|toml|md|txt|env|pem|key|crt)$`)

var defaultCreds = map[string]bool{"postgres": true, "password": true, "admin": true, "root": true, "secret": true, "changeme": true, "guest": true, "user": true, "test": true}

// entropy is Shannon entropy in bits per character.
func entropy(s string) float64 {
	if s == "" {
		return 0
	}
	counts := map[rune]int{}
	n := 0
	for _, r := range s {
		counts[r]++
		n++
	}
	var e float64
	for _, c := range counts {
		p := float64(c) / float64(n)
		e -= p * math.Log2(p)
	}
	return e
}

func classes(s string) int {
	var lower, upper, digit, other bool
	for _, r := range s {
		switch {
		case r >= 'a' && r <= 'z':
			lower = true
		case r >= 'A' && r <= 'Z':
			upper = true
		case r >= '0' && r <= '9':
			digit = true
		default:
			other = true
		}
	}
	n := 0
	for _, b := range []bool{lower, upper, digit, other} {
		if b {
			n++
		}
	}
	return n
}

var hexRe = regexp.MustCompile(`^[0-9a-fA-F]+$`)

// looksRandom decides whether an assigned literal is key material rather than
// a word, a path, a version or a URL.
func looksRandom(v string) bool {
	if len(v) < 16 || strings.ContainsAny(v, "/\\") && !strings.ContainsAny(v, "+=") {
		return false
	}
	if hexRe.MatchString(v) {
		return len(v) >= 32 && entropy(v) >= 3.0
	}
	return len(v) >= 20 && entropy(v) >= 3.5 && classes(v) >= 2
}

func placeholder(v string) bool {
	if placeholderRe.MatchString(v) {
		return true
	}
	// One character repeated, or a run like 12345678 / abcdefgh.
	if len(strings.Trim(v, v[:1])) == 0 {
		return true
	}
	return strings.Contains("0123456789abcdefghijklmnopqrstuvwxyz", strings.ToLower(v))
}

// ScanLine returns every secret-looking value on one line.
func ScanLine(path string, lineNo int, line string) []Finding {
	if strings.Contains(line, "secretscan:allow") {
		return nil
	}
	var out []Finding
	seen := map[string]bool{}
	add := func(rule, v string) {
		if v == "" || seen[v] {
			return
		}
		seen[v] = true
		out = append(out, Finding{Path: path, Line: lineNo, Rule: rule, value: v})
	}
	for _, r := range prefixRules {
		for _, m := range r.re.FindAllStringSubmatch(line, -1) {
			v := m[r.group]
			if r.name == "url-credentials" && (placeholder(v) || referenceRe.MatchString(v) || defaultCreds[strings.ToLower(v)] || strings.EqualFold(v, m[1])) {
				continue
			}
			if r.name != "private-key-block" && r.name != "url-credentials" && placeholder(v) {
				continue
			}
			add(r.name, v)
		}
	}
	for _, m := range assignRe.FindAllStringSubmatch(line, -1) {
		v := m[3]
		if !secretName(m[1]) || notAValueRe.MatchString(v) || referenceRe.MatchString(v) || placeholder(v) {
			continue
		}
		if identRe.MatchString(v) && !strings.ContainsAny(v, "0123456789") {
			continue
		}
		if looksRandom(v) {
			add("assignment:"+strings.ToLower(m[1]), v)
		}
	}
	for _, re := range []*regexp.Regexp{proseRe, uciKeyRe} {
		for _, m := range re.FindAllStringSubmatch(line, -1) {
			v := m[1]
			if placeholder(v) || referenceRe.MatchString(v) || notAValueRe.MatchString(v) || strings.Contains(v, "/") {
				continue
			}
			// A passphrase mixes letters with digits or symbols; a run of
			// letters and underscores is an identifier somebody quoted.
			if classes(v) < 2 || entropy(v) < 2.5 || (identRe.MatchString(v) && !strings.ContainsAny(v, "0123456789")) {
				continue
			}
			add("passphrase-in-text", v)
		}
	}
	return out
}

// ScanText scans a whole file's text.
func ScanText(path, text string) []Finding {
	var out []Finding
	for i, line := range strings.Split(text, "\n") {
		if len(line) > 4096 {
			line = line[:4096]
		}
		out = append(out, ScanLine(path, i+1, line)...)
	}
	return out
}
