package main

import (
	"bytes"
	"math/big"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

// Every input is hand-written here. A rule that cannot be stated as a row in
// one of these tables is not yet a rule the tool holds.

func TestParseLCOV(t *testing.T) {
	const root = "/work/repo"
	tests := []struct {
		name    string
		in      string
		want    Coverage
		wantErr bool
	}{
		{name: "empty input is zero records, not an error", in: "", want: Coverage{}},
		{
			name: "covered and uncovered lines; other records are ignored",
			in:   "TN:\nSF:a.go\nFN:1,main\nFNDA:1,main\nDA:1,1\nDA:2,0\nDA:3,4\nLF:3\nLH:2\nend_of_record\n",
			want: Coverage{"a.go": {1: 1, 2: 0, 3: 4}},
		},
		{
			name: "absolute paths under the root become relative",
			in:   "SF:/work/repo/pkg/b.go\nDA:7,0\nend_of_record\nSF:/elsewhere/c.go\nDA:1,1\nend_of_record\n",
			want: Coverage{"pkg/b.go": {7: 0}, "/elsewhere/c.go": {1: 1}},
		},
		{
			name: "one file in two records adds its hits",
			in:   "SF:a.go\nDA:1,0\nend_of_record\nSF:a.go\nDA:1,2\nend_of_record\n",
			want: Coverage{"a.go": {1: 2}},
		},
		{
			name: "a named file with no executable lines is still named",
			in:   "SF:empty.go\nLF:0\nend_of_record\n",
			want: Coverage{"empty.go": {}},
		},
		{name: "a record cut short is an error", in: "SF:a.go\nDA:1,1\n", wantErr: true},
		{name: "a DA line with a non-number is an error", in: "SF:a.go\nDA:x,1\nend_of_record\n", wantErr: true},
		{name: "a DA line with no hit count is an error", in: "SF:a.go\nDA:1\nend_of_record\n", wantErr: true},
		{name: "a DA line outside any record is an error", in: "DA:1,1\n", wantErr: true},
		{name: "line zero is an error", in: "SF:a.go\nDA:0,1\nend_of_record\n", wantErr: true},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got, err := ParseLCOV(strings.NewReader(tc.in), root)
			if (err != nil) != tc.wantErr {
				t.Fatalf("error = %v, want error %v", err, tc.wantErr)
			}
			if !tc.wantErr && !reflect.DeepEqual(got, tc.want) {
				t.Fatalf("coverage = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestParseGoCover(t *testing.T) {
	const mod = "github.com/TAIPANBOX/example"
	tests := []struct {
		name    string
		in      string
		want    Coverage
		wantErr bool
	}{
		{
			// A block marks its first and last line. Line 4 sits inside a
			// covered block but starts and ends no block, so it is not
			// executable and must not appear.
			name: "a block marks its first and last line, and nothing between",
			in: strings.Join([]string{
				"mode: set",
				mod + "/pkg/a.go:3.14,5.3 2 1",
				mod + "/pkg/a.go:5.3,8.3 1 0",
				mod + "/pkg/a.go:8.3,9.2 0 0",
				mod + "/cmd/b.go:4.2,4.20 1 0",
				mod + "/pkg/z.go:1.1,2.2 0 0",
				"example.org/other/c.go:1.1,2.2 1 0",
				"",
			}, "\n"),
			want: Coverage{
				"pkg/a.go": {3: 1, 5: 1, 8: 0},
				"cmd/b.go": {4: 0},
				"pkg/z.go": {},
			},
		},
		{name: "an empty profile is zero records", in: "mode: set\n", want: Coverage{}},
		{name: "a block without an end position is an error", in: "mode: set\n" + mod + "/pkg/a.go:3.14 2 1\n", wantErr: true},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got, err := ParseGoCover(strings.NewReader(tc.in), mod)
			if (err != nil) != tc.wantErr {
				t.Fatalf("error = %v, want error %v", err, tc.wantErr)
			}
			if !tc.wantErr && !reflect.DeepEqual(got, tc.want) {
				t.Fatalf("coverage = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestModuleOf(t *testing.T) {
	ok := map[string]string{
		"module github.com/x/y\n\ngo 1.27.2\n": "github.com/x/y",
		"module \"github.com/x/y\"\n":          "github.com/x/y",
	}
	for in, want := range ok {
		got, err := moduleOf(in)
		if err != nil || got != want {
			t.Errorf("moduleOf(%q) = %q, %v; want %q", in, got, err, want)
		}
	}
	if _, err := moduleOf("go 1.27.2\n"); err == nil {
		t.Errorf("a go.mod with no module line was accepted")
	}
}

// fileHeader is the header git prints for one changed file.
func fileHeader(p string) string {
	return "diff --git a/" + p + " b/" + p + "\nindex 1111111..2222222 100644\n--- a/" + p + "\n+++ b/" + p + "\n"
}

func TestParseDiff(t *testing.T) {
	tests := []struct {
		name    string
		in      string
		want    Diff
		wantErr bool
	}{
		{
			name: "added lines are numbered in the new file",
			in:   fileHeader("a.go") + "@@ -3,0 +4,2 @@\n+x\n+y\n",
			want: Diff{Files: []string{"a.go"}, Added: map[string][]int{"a.go": {4, 5}}},
		},
		{
			name: "deleted lines add nothing and do not move the new-file numbering",
			in:   fileHeader("a.go") + "@@ -10,2 +9,0 @@\n-old1\n-old2\n",
			want: Diff{Files: []string{"a.go"}, Added: map[string][]int{}},
		},
		{
			name: "a hunk header without counts means one line each side",
			in:   fileHeader("a.go") + "@@ -5 +5 @@\n-old\n+new\n",
			want: Diff{Files: []string{"a.go"}, Added: map[string][]int{"a.go": {5}}},
		},
		{
			// The added content is "++ x", so the line starts with "+++". Inside
			// a hunk it is content, not a file header.
			name: "a body line that begins with three pluses is content",
			in:   fileHeader("a.go") + "@@ -1 +1,2 @@\n-old\n+++ x\n+y\n",
			want: Diff{Files: []string{"a.go"}, Added: map[string][]int{"a.go": {1, 2}}},
		},
		{
			name: "the no-newline marker is not a line",
			in:   fileHeader("a.go") + "@@ -1 +1 @@\n-old\n+new\n\\ No newline at end of file\n",
			want: Diff{Files: []string{"a.go"}, Added: map[string][]int{"a.go": {1}}},
		},
		{
			name: "two files in one diff",
			in:   fileHeader("a.go") + "@@ -0,0 +1 @@\n+one\n" + fileHeader("pkg/b.go") + "@@ -2 +2,2 @@\n-x\n+y\n+z\n",
			want: Diff{Files: []string{"a.go", "pkg/b.go"}, Added: map[string][]int{"a.go": {1}, "pkg/b.go": {2, 3}}},
		},
		{
			name: "a renamed file with changes is judged under its new name",
			in: "diff --git a/old.go b/new.go\nsimilarity index 90%\nrename from old.go\nrename to new.go\n" +
				"index 1111111..2222222 100644\n--- a/old.go\n+++ b/new.go\n@@ -4 +4 @@\n-a\n+b\n",
			want: Diff{Files: []string{"new.go"}, Added: map[string][]int{"new.go": {4}}},
		},
		{
			name: "a pure rename has no lines to judge",
			in:   "diff --git a/old.go b/new.go\nsimilarity index 100%\nrename from old.go\nrename to new.go\n",
			want: Diff{Files: []string{"new.go"}, Added: map[string][]int{}},
		},
		{
			name: "a deleted file adds nothing",
			in: "diff --git a/gone.go b/gone.go\ndeleted file mode 100644\nindex 1111111..0000000\n" +
				"--- a/gone.go\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-x\n-y\n",
			want: Diff{Files: []string{"gone.go"}, Added: map[string][]int{}},
		},
		{
			name: "a binary file has no lines to judge",
			in:   "diff --git a/i.png b/i.png\nindex 1111111..2222222 100644\nBinary files a/i.png and b/i.png differ\n",
			want: Diff{Files: []string{"i.png"}, Added: map[string][]int{}},
		},
		{
			name: "a quoted path is unquoted",
			in: "diff --git \"a/sp ace.go\" \"b/sp ace.go\"\nindex 1111111..2222222 100644\n" +
				"--- \"a/sp ace.go\"\n+++ \"b/sp ace.go\"\n@@ -1 +1 @@\n-a\n+b\n",
			want: Diff{Files: []string{"sp ace.go"}, Added: map[string][]int{"sp ace.go": {1}}},
		},
		{
			name:    "a hunk body line that is neither added, removed nor context is an error",
			in:      fileHeader("a.go") + "@@ -1 +1 @@\n-old\nnonsense\n",
			wantErr: true,
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got, err := ParseDiff(strings.NewReader(tc.in))
			if (err != nil) != tc.wantErr {
				t.Fatalf("error = %v, want error %v", err, tc.wantErr)
			}
			if !tc.wantErr && !reflect.DeepEqual(got, tc.want) {
				t.Fatalf("diff = %+v, want %+v", got, tc.want)
			}
		})
	}
}

// hits gives line i+1 the i-th count.
func hits(v ...int64) map[int]int64 {
	m := make(map[int]int64, len(v))
	for i, h := range v {
		m[i+1] = h
	}
	return m
}

// rng is the lines 1..n.
func rng(n int) []int {
	r := make([]int, n)
	for i := range r {
		r[i] = i + 1
	}
	return r
}

func oneFile(file string, lines []int) Diff {
	return Diff{Files: []string{file}, Added: map[string][]int{file: lines}}
}

func rat(s string) *big.Rat {
	r, ok := new(big.Rat).SetString(s)
	if !ok {
		panic("bad rational in test: " + s)
	}
	return r
}

func TestParseBaseline(t *testing.T) {
	ok := map[string]string{"10\n": "10", "  59.5 ": "59.5", "100": "100", "0": "0"}
	for in, want := range ok {
		got, err := parseBaseline(in)
		if err != nil || got.Cmp(rat(want)) != 0 {
			t.Errorf("parseBaseline(%q) = %v, %v; want %s", in, got, err, want)
		}
	}
	for _, in := range []string{"", "abc", "-1", "100.5"} {
		if _, err := parseBaseline(in); err == nil {
			t.Errorf("parseBaseline(%q) was accepted", in)
		}
	}
}

func TestJudge(t *testing.T) {
	tests := []struct {
		name      string
		cov       Coverage
		diff      Diff
		threshold int
		baseline  string
		verdict   string
		mention   []string
	}{
		{
			name:      "every added line covered",
			cov:       Coverage{"a.go": hits(1, 1, 1, 1, 1, 1, 1, 1, 1, 1)},
			diff:      oneFile("a.go", rng(10)),
			threshold: 90,
			verdict:   "pass",
			mention:   []string{"covered 10 of 10"},
		},
		{
			name:      "no added line covered",
			cov:       Coverage{"a.go": hits(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)},
			diff:      oneFile("a.go", rng(10)),
			threshold: 90,
			verdict:   "fail",
			mention:   []string{"covered 0 of 10"},
		},
		{
			name:      "nine of ten is exactly the default floor and passes",
			cov:       Coverage{"a.go": hits(1, 1, 1, 1, 1, 1, 1, 1, 1, 0)},
			diff:      oneFile("a.go", rng(10)),
			threshold: 90,
			verdict:   "pass",
		},
		{
			name:      "eight of ten is below the floor and fails",
			cov:       Coverage{"a.go": hits(1, 1, 1, 1, 1, 1, 1, 1, 0, 0)},
			diff:      oneFile("a.go", rng(10)),
			threshold: 90,
			verdict:   "fail",
			mention:   []string{"covered 8 of 10"},
		},
		{
			name:      "nine of ten fails a floor of one hundred",
			cov:       Coverage{"a.go": hits(1, 1, 1, 1, 1, 1, 1, 1, 1, 0)},
			diff:      oneFile("a.go", rng(10)),
			threshold: 100,
			verdict:   "fail",
			mention:   []string{"covered 9 of 10"},
		},
		{
			name:      "mixed lines name each uncovered line",
			cov:       Coverage{"a.go": hits(1, 0, 1, 0)},
			diff:      oneFile("a.go", rng(4)),
			threshold: 90,
			verdict:   "fail",
			mention:   []string{"a.go:2", "a.go:4"},
		},
		{
			name: "a file the coverage file does not name is excluded and said so",
			cov:  Coverage{"a.go": hits(1)},
			diff: Diff{
				Files: []string{"a.go", "docs/x.md"},
				Added: map[string][]int{"a.go": {1}, "docs/x.md": {1, 2, 3}},
			},
			threshold: 90,
			verdict:   "pass",
			mention:   []string{"docs/x.md"},
		},
		{
			name:      "a renamed file is not judged under its old name",
			cov:       Coverage{"old.go": hits(1)},
			diff:      oneFile("new.go", []int{1}),
			threshold: 90,
			verdict:   "nothing",
			mention:   []string{"names no file of the diff", "new.go"},
		},
		{
			name:      "a renamed file is judged under its new name",
			cov:       Coverage{"new.go": hits(1)},
			diff:      oneFile("new.go", []int{1}),
			threshold: 90,
			verdict:   "pass",
		},
		{
			name:      "an empty coverage file measures nothing",
			cov:       Coverage{},
			diff:      oneFile("a.go", []int{1}),
			threshold: 90,
			verdict:   "nothing",
			mention:   []string{"no executable line"},
		},
		{
			name:      "a coverage file with no executable lines measures nothing",
			cov:       Coverage{"a.go": {}},
			diff:      oneFile("a.go", []int{1}),
			threshold: 90,
			verdict:   "nothing",
			mention:   []string{"no executable line"},
		},
		{
			name:      "added lines the coverage file does not list as executable measure nothing",
			cov:       Coverage{"a.go": {5: 1}},
			diff:      oneFile("a.go", []int{1}),
			threshold: 90,
			verdict:   "nothing",
			mention:   []string{"none of them executable"},
		},
		{
			name:      "a diff that adds no lines measures nothing",
			cov:       Coverage{"a.go": hits(1)},
			diff:      Diff{Files: []string{"a.go"}, Added: map[string][]int{}},
			threshold: 90,
			verdict:   "nothing",
			mention:   []string{"adds no lines"},
		},
		{
			name:      "whole repository at the baseline passes",
			cov:       Coverage{"a.go": hits(1, 1, 1, 0, 0)},
			diff:      oneFile("a.go", []int{1}),
			threshold: 90,
			baseline:  "60",
			verdict:   "pass",
		},
		{
			name:      "whole repository below the baseline fails",
			cov:       Coverage{"a.go": hits(1, 1, 1, 0, 0)},
			diff:      oneFile("a.go", []int{1}),
			threshold: 90,
			baseline:  "61",
			verdict:   "fail",
			mention:   []string{"below the baseline"},
		},
		{
			name:      "a decimal baseline is compared exactly",
			cov:       Coverage{"a.go": hits(1, 1, 1, 0, 0)},
			diff:      oneFile("a.go", []int{1}),
			threshold: 90,
			baseline:  "60.01",
			verdict:   "fail",
			mention:   []string{"below the baseline"},
		},
		{
			name:      "a diff below the floor and a repository below the baseline both fail",
			cov:       Coverage{"a.go": hits(1, 0, 0, 0, 0)},
			diff:      oneFile("a.go", []int{2, 3}),
			threshold: 90,
			baseline:  "50",
			verdict:   "fail",
			mention:   []string{"covered 0 of 2", "below the baseline"},
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			base := tc.baseline
			if base == "" {
				base = "0"
			}
			r := Judge(tc.cov, tc.diff, tc.threshold, rat(base))
			if got := r.Verdict(); got != tc.verdict {
				t.Errorf("verdict = %q, want %q", got, tc.verdict)
			}
			var out bytes.Buffer
			r.Render(&out)
			for _, m := range tc.mention {
				if !strings.Contains(out.String(), m) {
					t.Errorf("report does not contain %q:\n%s", m, out.String())
				}
			}
		})
	}
}

func runTool(args ...string) (int, string, string) {
	var out, errOut bytes.Buffer
	code := run(args, &out, &errOut)
	return code, out.String(), errOut.String()
}

func writeFile(t *testing.T, dir, name, content string) {
	t.Helper()
	if err := os.WriteFile(filepath.Join(dir, name), []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

func gitIn(t *testing.T, dir string, args ...string) string {
	t.Helper()
	cmd := exec.Command("git", append([]string{"-C", dir,
		"-c", "user.name=test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false"}, args...)...)
	cmd.Env = gitEnv()
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("git %v: %v\n%s", args, err, out)
	}
	return strings.TrimSpace(string(out))
}

// newRepo commits a three-line file, then changes it to four lines: "two" is
// deleted, "NEW" is added at line 2 and "NEW2" at line 4. It returns the base
// commit, and writes a baseline of 10 percent.
func newRepo(t *testing.T) (dir, base string) {
	t.Helper()
	dir = t.TempDir()
	gitIn(t, dir, "init", "-q")
	writeFile(t, dir, "a.go", "one\ntwo\nthree\n")
	gitIn(t, dir, "add", "a.go")
	gitIn(t, dir, "commit", "-q", "-m", "base")
	base = gitIn(t, dir, "rev-parse", "HEAD")
	writeFile(t, dir, "a.go", "one\nNEW\nthree\nNEW2\n")
	gitIn(t, dir, "commit", "-q", "-am", "change")
	writeFile(t, dir, ".coverage-baseline", "10\n")
	return dir, base
}

func TestRunAgainstAGitDiff(t *testing.T) {
	const passing = "SF:a.go\nDA:1,1\nDA:2,3\nDA:3,1\nDA:4,1\nend_of_record\n"
	tests := []struct {
		name    string
		lcov    string
		want    int
		mention string
	}{
		{name: "added lines covered passes", lcov: passing, want: 0, mention: "verdict: pass"},
		{
			name: "an uncovered added line fails and is named",
			lcov: "SF:a.go\nDA:1,1\nDA:2,3\nDA:3,1\nDA:4,0\nend_of_record\n",
			want: 1, mention: "a.go:4",
		},
		{name: "an empty coverage file measures nothing", lcov: "", want: 3, mention: "measured nothing"},
		{
			name: "a coverage file that names none of the diff measures nothing",
			lcov: "SF:other.go\nDA:1,1\nend_of_record\n",
			want: 3, mention: "names no file of the diff",
		},
		{name: "a malformed coverage file is an input error", lcov: "SF:a.go\nDA:x,1\nend_of_record\n", want: 2},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			dir, base := newRepo(t)
			writeFile(t, dir, "lcov.info", tc.lcov)
			code, stdout, stderr := runTool("-C", dir, "-base", base, "-coverage", "lcov.info")
			if code != tc.want {
				t.Fatalf("exit %d, want %d\nstdout:\n%s\nstderr:\n%s", code, tc.want, stdout, stderr)
			}
			if tc.mention != "" && !strings.Contains(stdout+stderr, tc.mention) {
				t.Errorf("output does not contain %q:\n%s%s", tc.mention, stdout, stderr)
			}
		})
	}

	t.Run("a missing baseline file is an input error", func(t *testing.T) {
		dir, base := newRepo(t)
		writeFile(t, dir, "lcov.info", passing)
		if err := os.Remove(filepath.Join(dir, ".coverage-baseline")); err != nil {
			t.Fatal(err)
		}
		if code, _, _ := runTool("-C", dir, "-base", base, "-coverage", "lcov.info"); code != 2 {
			t.Errorf("exit %d, want 2", code)
		}
	})
	t.Run("an unknown base revision is an input error", func(t *testing.T) {
		dir, _ := newRepo(t)
		writeFile(t, dir, "lcov.info", passing)
		if code, _, _ := runTool("-C", dir, "-base", "no-such-rev", "-coverage", "lcov.info"); code != 2 {
			t.Errorf("exit %d, want 2", code)
		}
	})
	t.Run("a missing coverage file is an input error", func(t *testing.T) {
		dir, base := newRepo(t)
		if code, _, _ := runTool("-C", dir, "-base", base, "-coverage", "absent.info"); code != 2 {
			t.Errorf("exit %d, want 2", code)
		}
	})
}
