package main

import (
	"bytes"
	"flag"
	"fmt"
	"io"
	"math/big"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// Exit codes. 3 is measured nothing: a run that read no executable line has not
// passed, and saying OK there is the failure the estate's gates keep finding in
// themselves.
const (
	exitClean    = 0
	exitFound    = 1
	exitUsage    = 2
	exitMeasured = 3
)

const usage = `diffcover: the coverage floor on the lines a change adds, and the whole-repository baseline.

  diffcover -base <rev> -coverage <file> [flags]

  -C dir           repository directory (default .)
  -base rev        the change is base...HEAD
  -diff file       read the unified diff from a file instead of running git
  -coverage file   the coverage file, relative to -C unless absolute
  -format f        lcov (default: cargo llvm-cov, coverage.py) or gocover (go test -coverprofile)
  -threshold n     floor for the added executable lines, a percentage (default 90)
  -baseline file   the whole-repository baseline, one percentage (default <C>/.coverage-baseline)

Exit 0 pass, 1 below the floor or the baseline, 2 usage or input error,
3 measured nothing.
`

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

func run(args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("diffcover", flag.ContinueOnError)
	fs.SetOutput(stderr)
	dir := fs.String("C", ".", "repository directory")
	base := fs.String("base", "", "base revision")
	diffFile := fs.String("diff", "", "unified diff file")
	coveragePath := fs.String("coverage", "", "coverage file")
	format := fs.String("format", "lcov", "lcov or gocover")
	threshold := fs.Int("threshold", 90, "floor percentage for added executable lines")
	baselinePath := fs.String("baseline", "", "baseline file")
	fs.Usage = func() { fmt.Fprint(stderr, usage) }
	if err := fs.Parse(args); err != nil {
		return exitUsage
	}
	if fs.NArg() != 0 || *coveragePath == "" {
		fs.Usage()
		return exitUsage
	}
	if *base == "" && *diffFile == "" {
		fmt.Fprintln(stderr, "diffcover: give -base <rev>, or -diff <file>")
		return exitUsage
	}
	if *format != "lcov" && *format != "gocover" {
		fmt.Fprintf(stderr, "diffcover: -format %q is not lcov or gocover\n", *format)
		return exitUsage
	}
	if *threshold < 0 || *threshold > 100 {
		fmt.Fprintln(stderr, "diffcover: -threshold must be a percentage from 0 to 100")
		return exitUsage
	}

	root, err := filepath.Abs(*dir)
	if err != nil {
		return inputError(stderr, err)
	}
	if *baselinePath == "" {
		*baselinePath = filepath.Join(root, ".coverage-baseline")
	}

	cov, err := readCoverage(resolve(root, *coveragePath), root, *format)
	if err != nil {
		return inputError(stderr, err)
	}

	var diffSource io.Reader
	if *diffFile != "" {
		f, err := os.Open(*diffFile)
		if err != nil {
			return inputError(stderr, err)
		}
		defer f.Close()
		diffSource = f
	} else {
		text, err := gitDiff(root, *base)
		if err != nil {
			return inputError(stderr, err)
		}
		diffSource = strings.NewReader(text)
	}
	d, err := ParseDiff(diffSource)
	if err != nil {
		return inputError(stderr, fmt.Errorf("the diff: %v", err))
	}

	raw, err := os.ReadFile(resolve(root, *baselinePath))
	if err != nil {
		return inputError(stderr, fmt.Errorf("the baseline: %v (write one percentage there)", err))
	}
	baseline, err := parseBaseline(string(raw))
	if err != nil {
		return inputError(stderr, err)
	}

	r := Judge(cov, d, *threshold, baseline)
	r.Render(stdout)
	switch r.Verdict() {
	case "pass":
		return exitClean
	case "fail":
		return exitFound
	}
	return exitMeasured
}

// readCoverage reads the coverage file in the format it was written in. A Go
// profile names files by import path, so the module is read from go.mod.
func readCoverage(file, root, format string) (Coverage, error) {
	f, err := os.Open(file)
	if err != nil {
		return nil, fmt.Errorf("the coverage file: %v", err)
	}
	defer f.Close()
	if format == "lcov" {
		cov, err := ParseLCOV(f, root)
		if err != nil {
			return nil, fmt.Errorf("the coverage file: %v", err)
		}
		return cov, nil
	}
	gomod, err := os.ReadFile(filepath.Join(root, "go.mod"))
	if err != nil {
		return nil, fmt.Errorf("gocover format needs go.mod at the repository root: %v", err)
	}
	module, err := moduleOf(string(gomod))
	if err != nil {
		return nil, err
	}
	cov, err := ParseGoCover(f, module)
	if err != nil {
		return nil, fmt.Errorf("the coverage file: %v", err)
	}
	return cov, nil
}

// gitDiff returns what base...HEAD adds, with no context lines, so the hunk
// counts are exact. Prefixes are fixed so a user's diff.noprefix cannot change
// the paths, and --relative keeps them relative to -C.
func gitDiff(root, base string) (string, error) {
	if strings.HasPrefix(base, "-") {
		return "", fmt.Errorf("-base %q is not a revision", base)
	}
	cmd := exec.Command("git", "-C", root, "diff", "--unified=0", "--no-color", "--no-ext-diff",
		"--find-renames", "--relative", "--src-prefix=a/", "--dst-prefix=b/", base+"...HEAD", "--")
	cmd.Env = gitEnv()
	var out, errOut bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &errOut
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("git diff %s...HEAD: %v: %s", base, err, strings.TrimSpace(errOut.String()))
	}
	return out.String(), nil
}

// gitEnv is git's environment without the variables that point it at a
// repository. A pre-push hook runs with GIT_DIR set to the repository being
// pushed, and an inherited GIT_DIR would aim every command here at that
// repository whatever -C says. This is the C9 failure from the README.
func gitEnv() []string {
	var env []string
	for _, kv := range os.Environ() {
		name, _, _ := strings.Cut(kv, "=")
		switch name {
		case "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES":
			continue
		}
		env = append(env, kv)
	}
	return env
}

// parseBaseline reads the one number the baseline file holds.
func parseBaseline(s string) (*big.Rat, error) {
	s = strings.TrimSpace(s)
	r, ok := new(big.Rat).SetString(s)
	if !ok {
		return nil, fmt.Errorf("the baseline %q is not a number", s)
	}
	if r.Sign() < 0 || r.Cmp(big.NewRat(100, 1)) > 0 {
		return nil, fmt.Errorf("the baseline %q must be a percentage from 0 to 100", s)
	}
	return r, nil
}

func resolve(root, p string) string {
	if filepath.IsAbs(p) {
		return p
	}
	return filepath.Join(root, p)
}

func inputError(stderr io.Writer, err error) int {
	fmt.Fprintf(stderr, "diffcover: %v\n", err)
	return exitUsage
}
