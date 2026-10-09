package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

// Every fixture value is built at run time, so this file never holds a
// contiguous secret-shaped literal and the tool can scan its own repository.

func hexOf(seed string) string {
	s := sha256.Sum256([]byte(seed))
	return hex.EncodeToString(s[:])
}

// b62 turns a seed into n base62 characters, mixed case and digits.
func b62(seed string, n int) string {
	const al = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
	var out []byte
	for i := 0; len(out) < n; i++ {
		for _, c := range sha256.Sum256([]byte(seed + string(rune('a'+i)))) {
			out = append(out, al[int(c)%len(al)])
		}
	}
	return string(out[:n])
}

func rules(fs []Finding) []string {
	var out []string
	for _, f := range fs {
		out = append(out, f.Rule)
	}
	return out
}

func TestRulesFireOnTheShapesTheAuditFound(t *testing.T) {
	q := "\""
	bt := "`"
	cases := []struct {
		name, line, rule string
	}{
		{"bare hex after API_KEY= (audit F3)", "POSTIZ_" + "API_KEY=" + q + hexOf("f3") + q, "assignment:postiz_api_key"},
		{"export without quotes", "export SERVICE_" + "TOKEN=" + b62("tok", 40), "assignment:service_token"},
		{"yaml", "  client_" + "secret: " + b62("yaml", 32), "assignment:client_secret"},
		{"json", q + "api" + "Key" + q + ": " + q + b62("json", 36) + q, "assignment:apikey"},
		{"passphrase in prose (audit F6)", "The lab radio's wifi pass" + "phrase is " + bt + "Kestrel-" + "Orbit-74" + bt + ".", "passphrase-in-text"},
		{"SSID key in a lab note (audit F6 shape)", "  and the SS" + "ID key: " + bt + "3kestrel" + "7harbor" + bt + ", rotated never", "passphrase-in-text"},
		{"UCI wireless key", "\toption " + "key '" + "Gl4ss-" + "Harbor-9" + "'", "passphrase-in-text"},
		{"Ukrainian prose", "па" + "роль від мережі: «" + "Vitr" + "ylo-2026" + "»", "passphrase-in-text"},
		{"anthropic", "key = " + "sk-" + "ant-api03-" + b62("ant", 60), "anthropic-key"},
		{"openrouter", "sk-" + "or-v1-" + hexOf("or"), "openrouter-key"},
		{"aws key id", "id: " + "AK" + "IA" + strings.ToUpper(b62("aws", 16)), "aws-access-key-id"},
		{"github token", "gh" + "p_" + b62("gh", 36), "github-token"},
		{"private key block", "-----BEGIN " + "OPENSSH PRIVATE KEY-----", "private-key-block"},
		{"url credentials", "postgres://app:" + b62("pw", 18) + "@db.internal:5432/x", "url-credentials"},
	}
	for _, c := range cases {
		got := ScanLine("f.txt", 1, c.line)
		found := false
		for _, r := range rules(got) {
			if r == c.rule {
				found = true
			}
		}
		if !found {
			t.Errorf("%s: want rule %s, got %v", c.name, c.rule, rules(got))
		}
	}
}

func TestRulesStayQuietOnWhatIsNotASecret(t *testing.T) {
	q := "\""
	cases := []struct{ name, line string }{
		{"env reference", "API_" + "KEY=${POSTIZ_API_KEY:?set it}"},
		{"shell expansion", "TOKEN=" + q + "$(cat /run/secrets/token)" + q},
		{"getenv", "apiKey := os.Getenv(" + q + "API_KEY" + q + ")"},
		{"field access", "password = self.password_hash"},
		{"type annotation", "pub secrets: BTreeMap<String, String>,"},
		{"aws doc example", "AK" + "IA" + "IOSFODNN7" + "EXAMPLE"},
		{"canary fixture", "const secret = " + q + "fake-test-key-this-must-" + "never-leak-" + hexOf("c")[:6] + q},
		{"placeholder", "API_" + "KEY=" + q + "your-api-key-here-xxxxxxxx" + q},
		{"short value", "token: abc123"},
		{"path", "private_key: /etc/ssl/private/server.key"},
		{"version", "token_version = 1.27.2"},
		{"word in prose", "the pass" + "word is " + "`" + "changeme" + "`"},
		{"low-entropy hex", "CHECK_" + "TOKEN=" + strings.Repeat("ab", 20)},
		{"inline allow", "API_" + "KEY=" + hexOf("allowed") + " # secretscan:allow published test vector"},
		{"url with a variable", "postgres://app:$" + "{DB_PASSWORD}@db:5432/x"},
	}
	for _, c := range cases {
		if got := ScanLine("f.txt", 1, c.line); len(got) != 0 {
			t.Errorf("%s: want nothing, got %v", c.name, rules(got))
		}
	}
}

func TestAFindingNeverCarriesItsValueIntoOutput(t *testing.T) {
	v := hexOf("never printed")
	f := ScanLine("f.env", 3, "API_"+"KEY="+v)
	if len(f) != 1 {
		t.Fatalf("want one finding, got %d", len(f))
	}
	shown := f[0].Masked() + " " + f[0].Fingerprint()
	if strings.Contains(shown, v[4:len(v)-2]) {
		t.Fatalf("the masked form leaks the value: %s", shown)
	}
	if !strings.HasPrefix(f[0].Masked(), v[:4]) || !strings.Contains(f[0].Masked(), "(len 64)") {
		t.Fatalf("mask shape changed: %s", f[0].Masked())
	}
}

func TestAllowlistNeedsAReasonAndMatchesByFingerprintAndGlob(t *testing.T) {
	dir := t.TempDir()
	v := hexOf("vector")
	f := ScanLine("docs/rfc/vectors.md", 1, "API_"+"KEY="+v)[0]
	p := filepath.Join(dir, "allow")
	os.WriteFile(p, []byte(f.Fingerprint()+" docs/**\n"), 0o644)
	if _, err := loadAllow(p); err == nil {
		t.Fatal("an entry without a reason was accepted")
	}
	os.WriteFile(p, []byte(f.Fingerprint()+" docs/rfc/*.md # RFC test vector, published\n"+hexOf("x")[:16]+" ** # stale\n"), 0o644)
	a, err := loadAllow(p)
	if err != nil {
		t.Fatal(err)
	}
	if !a.permits(f) {
		t.Fatal("matching fingerprint and glob was not permitted")
	}
	other := f
	other.Path = "src/config.env"
	if a.permits(other) {
		t.Fatal("the same value in another path was permitted")
	}
	if u := a.unused(); len(u) != 1 || u[0].line != 2 {
		t.Fatalf("want the stale entry reported as unused, got %d", len(u))
	}
}

func git(t *testing.T, dir string, args ...string) string {
	t.Helper()
	c := exec.Command("git", append([]string{"-C", dir, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"}, args...)...)
	out, err := c.CombinedOutput()
	if err != nil {
		t.Fatalf("git %v: %v\n%s", args, err, out)
	}
	return strings.TrimSpace(string(out))
}

func TestTreeOfAnEmptyRevisionMeasuredNothing(t *testing.T) {
	dir := t.TempDir()
	git(t, dir, "init", "-q")
	git(t, dir, "commit", "-q", "--allow-empty", "-m", "empty")
	var out, errb bytes.Buffer
	if code := run([]string{"-C", dir, "tree"}, nil, &out, &errb); code != exitMeasured {
		t.Fatalf("want exit %d, got %d: %s", exitMeasured, code, errb.String())
	}
}

func TestPushRefusesAddedSecretAndPrintsOnlyTheMask(t *testing.T) {
	dir := t.TempDir()
	git(t, dir, "init", "-q")
	v := hexOf("pushed")
	os.WriteFile(filepath.Join(dir, "deploy.sh"), []byte("#!/bin/sh\nPOSTIZ_"+"API_KEY="+v+"\n"), 0o644)
	git(t, dir, "add", ".")
	git(t, dir, "commit", "-q", "-m", "add")
	sha := git(t, dir, "rev-parse", "HEAD")
	stdin := strings.NewReader("refs/heads/main " + sha + " refs/heads/main " + zeroSHA + "\n")
	var out, errb bytes.Buffer
	code := run([]string{"-C", dir, "push"}, stdin, &out, &errb)
	if code != exitFound {
		t.Fatalf("want exit %d, got %d\n%s%s", exitFound, code, out.String(), errb.String())
	}
	if !strings.Contains(out.String(), "deploy.sh:2: assignment:postiz_api_key") {
		t.Fatalf("finding not reported where expected:\n%s", out.String())
	}
	if strings.Contains(out.String()+errb.String(), v[4:60]) {
		t.Fatal("the value reached the output")
	}

	// A deletion pushes nothing and is clean.
	del := strings.NewReader("(delete) " + zeroSHA + " refs/heads/old " + sha + "\n")
	out.Reset()
	if code := run([]string{"-C", dir, "push"}, del, &out, &errb); code != exitClean {
		t.Fatalf("a deletion was refused: %d", code)
	}

	// Allowlisted by fingerprint, the same push is clean.
	fp := fingerprint(v)
	os.WriteFile(filepath.Join(dir, ".secretscan-allow"), []byte(fp+" deploy.sh # rotated 2026-10-09, kept as a fixture\n"), 0o644)
	stdin = strings.NewReader("refs/heads/main " + sha + " refs/heads/main " + zeroSHA + "\n")
	out.Reset()
	if code := run([]string{"-C", dir, "push"}, stdin, &out, &errb); code != exitClean {
		t.Fatalf("an allowlisted value was refused: %d\n%s", code, out.String())
	}
}

func TestHistoryFindsWhatTheTreeNoLongerHolds(t *testing.T) {
	dir := t.TempDir()
	git(t, dir, "init", "-q")
	v := hexOf("removed later")
	os.WriteFile(filepath.Join(dir, "publish.sh"), []byte("API_"+"KEY="+v+"\n"), 0o644)
	git(t, dir, "add", ".")
	git(t, dir, "commit", "-q", "-m", "literal")
	os.WriteFile(filepath.Join(dir, "publish.sh"), []byte("API_"+"KEY=${API_KEY:?}\n"), 0o644)
	git(t, dir, "commit", "-q", "-am", "from env")
	var out, errb bytes.Buffer
	if code := run([]string{"-C", dir, "tree"}, nil, &out, &errb); code != exitClean {
		t.Fatalf("tree: want clean, got %d\n%s", code, out.String())
	}
	out.Reset()
	if code := run([]string{"-C", dir, "history"}, nil, &out, &errb); code != exitFound {
		t.Fatalf("history: want %d, got %d\n%s", exitFound, code, out.String())
	}
	if !strings.Contains(out.String(), "publish.sh:1: assignment:api_key") {
		t.Fatalf("history finding not reported:\n%s", out.String())
	}
	out.Reset()
	base := git(t, dir, "rev-list", "--max-parents=0", "HEAD")
	if code := run([]string{"-C", dir, "diff", base + "..HEAD"}, nil, &out, &errb); code != exitClean {
		t.Fatalf("diff of the removal: want clean, got %d\n%s", code, out.String())
	}
}

// Each line below fired on a real estate repository on 2026-10-09 and is not
// a secret. They are the measured noise the name and value rules exist for.
func TestTheNoiseMeasuredOnTheEstateStaysQuiet(t *testing.T) {
	q := "\""
	bt := "`"
	cases := []struct{ name, line string }{
		{"a Rust path through tokenfuse_core", "use tokenfuse_core::agent_event::{AgentEvent, EventType};"},
		{"tokens as a count", "est_input_tokens = {self.input_tokens_per_call}"},
		{"withCredentials", "this.withCredentials = init.credentials"},
		{"a quoted flag after password", "pass " + "the password with " + bt + "-set-password" + bt + " instead"},
		{"a quoted file name", "the pass" + "word lives in " + bt + "install.sh" + bt},
		{"a quoted identifier", "pass" + "word handling is in " + bt + "ActiveDirectoryAuth" + bt},
		{"CI service default", "DATABASE_URL: postgres://postgres:" + "postgres@localhost:5432/ci"},
		{"escape in a test string", "bearer: " + q + "correct-horse-battery\\n" + q},
		{"a demo sign-in", "pass" + "word is " + bt + "demo-pass-2026" + bt},
		{"compose key naming an MCP upstream", "TOKENFUSE_MCP_UPSTREAMS: typryx=http://typryx:8095/mcp"},
		{"a key FILE named after a private key", "PRIVATE_" + "KEY=deploy-ed25519-2026.pem"},
		{"metadata about a secret", "TOKENFUSE_MCP_SECRET_" + "SCOPES: github=" + b62("scope", 30)},
		{"a mock value", "secret: " + q + "sk-mock-" + b62("mock", 20) + q},
		{"a mock-named field", "mock_client_key_" + "secret = " + q + "gx_0" + b62("mk", 28) + q},
		{"password equal to the user", "postgres://wardryx:" + "wardryx@db:5432/wardryx"},
		{"a Rust path after a secret name", "let api_" + "key = ::vault2026::Kx9QmZ4tR8wB3nL7v;"},
	}
	for _, c := range cases {
		if got := ScanLine("f", 1, c.line); len(got) != 0 {
			t.Errorf("%s: want nothing, got %v", c.name, rules(got))
		}
	}
}
