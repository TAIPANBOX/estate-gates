package main

import (
	"fmt"
	"io"
	"math/big"
	"sort"
	"strings"
)

// Report is the outcome of judging one change against one coverage file.
//
// Two things can be wrong with a report and they are kept apart. Problems mean
// the run measured nothing it can stand behind: the verdict is "nothing", never
// a pass. Findings mean something was measured and it is below a floor.
type Report struct {
	Problems  []string
	Findings  []string
	Uncovered []string       // "path:line" for each added executable line that did not run
	Excluded  map[string]int // added lines per file that no coverage record names

	AddedExec, AddedCovered int
	RepoExec, RepoCovered   int64
	Threshold               int
}

// Judge measures the lines a change adds against the coverage file, and the
// whole repository against a baseline.
//
// An added line is judged only when the coverage file lists it as executable.
// A line in a file no coverage record names is excluded and reported, so a
// test, a document or a generated file does not count as code that is missing
// coverage. The price of that rule is that a new source file no tool
// instrumented is excluded too, which is why the workflow asks Go for every
// package, not only the tested ones.
func Judge(cov Coverage, d Diff, threshold int, baseline *big.Rat) Report {
	r := Report{Threshold: threshold, Excluded: map[string]int{}}
	for _, lines := range cov {
		r.RepoExec += int64(len(lines))
		for _, h := range lines {
			if h > 0 {
				r.RepoCovered++
			}
		}
	}
	if r.RepoExec == 0 {
		r.Problems = append(r.Problems, "the coverage file has no executable line, so neither the change nor the repository can be judged")
		return r
	}

	files := make([]string, 0, len(d.Added))
	for f := range d.Added {
		files = append(files, f)
	}
	sort.Strings(files)
	var addedTotal, namedFiles int
	for _, f := range files {
		lines := d.Added[f]
		addedTotal += len(lines)
		fc, named := cov[f]
		if !named {
			r.Excluded[f] = len(lines)
			continue
		}
		namedFiles++
		for _, ln := range lines {
			hits, executable := fc[ln]
			if !executable {
				continue
			}
			r.AddedExec++
			if hits > 0 {
				r.AddedCovered++
			} else {
				r.Uncovered = append(r.Uncovered, fmt.Sprintf("%s:%d", f, ln))
			}
		}
	}

	switch {
	case addedTotal == 0:
		r.Problems = append(r.Problems, "the diff adds no lines")
	case namedFiles == 0:
		r.Problems = append(r.Problems, "the coverage file names no file of the diff (the diff touches "+strings.Join(d.Files, ", ")+")")
	case r.AddedExec == 0:
		r.Problems = append(r.Problems, fmt.Sprintf("the diff adds %d line(s) in %d named file(s), none of them executable", addedTotal, namedFiles))
	}
	if len(r.Problems) > 0 {
		return r
	}

	if r.AddedCovered*100 < threshold*r.AddedExec {
		r.Findings = append(r.Findings, fmt.Sprintf("below the threshold: added executable lines are covered at %s%%, threshold %d",
			pct(int64(r.AddedCovered), int64(r.AddedExec)), threshold))
	}
	if baseline != nil && big.NewRat(r.RepoCovered*100, r.RepoExec).Cmp(baseline) < 0 {
		r.Findings = append(r.Findings, fmt.Sprintf("below the baseline: the whole repository is covered at %s%%, baseline %s%%",
			pct(r.RepoCovered, r.RepoExec), baseline.FloatString(2)))
	}
	return r
}

// Verdict is "pass", "fail", or "nothing" for a run that measured nothing.
func (r Report) Verdict() string {
	switch {
	case len(r.Problems) > 0:
		return "nothing"
	case len(r.Findings) > 0:
		return "fail"
	}
	return "pass"
}

// Render writes the report. Every line names a file or a number, and no line
// of source is ever printed.
func (r Report) Render(w io.Writer) {
	if r.RepoExec > 0 {
		fmt.Fprintf(w, "whole repository: covered %d of %d executable lines = %s%%\n",
			r.RepoCovered, r.RepoExec, pct(r.RepoCovered, r.RepoExec))
	}
	if r.AddedExec > 0 {
		fmt.Fprintf(w, "added executable lines: covered %d of %d = %s%%, threshold %d\n",
			r.AddedCovered, r.AddedExec, pct(int64(r.AddedCovered), int64(r.AddedExec)), r.Threshold)
	}
	if len(r.Uncovered) > 0 {
		fmt.Fprintf(w, "uncovered added lines: %s\n", strings.Join(r.Uncovered, ", "))
	}
	for _, f := range sortedKeys(r.Excluded) {
		fmt.Fprintf(w, "excluded, no coverage record names this file: %s (%d added line(s))\n", f, r.Excluded[f])
	}
	for _, p := range r.Problems {
		fmt.Fprintf(w, "measured nothing: %s\n", p)
	}
	for _, f := range r.Findings {
		fmt.Fprintln(w, f)
	}
	if r.Verdict() == "nothing" {
		fmt.Fprintln(w, "verdict: measured nothing")
	} else {
		fmt.Fprintf(w, "verdict: %s\n", r.Verdict())
	}
}

func pct(n, d int64) string {
	return big.NewRat(n*100, d).FloatString(2)
}

func sortedKeys(m map[string]int) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}
