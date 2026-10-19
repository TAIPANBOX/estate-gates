package main

import (
	"bufio"
	"fmt"
	"io"
	"path"
	"path/filepath"
	"strconv"
	"strings"
)

// Coverage maps a repository-relative file to its executable lines and how
// often each one ran. A line the map does not hold is not executable, and that
// is a statement, not an absence: the tool does not judge it.
type Coverage map[string]map[int]int64

// ParseLCOV reads an LCOV tracefile, as cargo llvm-cov --lcov and coverage.py's
// lcov command write it. Only SF and DA records matter. A path under root is
// made relative to it, so an absolute path a tool wrote matches a path in the
// diff. A file named by a record is named even when it has no DA lines.
func ParseLCOV(r io.Reader, root string) (Coverage, error) {
	cov := make(Coverage)
	var cur map[int]int64
	open := false
	sc := newScanner(r)
	for n := 1; sc.Scan(); n++ {
		line := strings.TrimRight(sc.Text(), "\r")
		switch {
		case strings.HasPrefix(line, "SF:"):
			if open {
				return nil, fmt.Errorf("line %d: a new SF record before end_of_record", n)
			}
			name := normalise(root, strings.TrimPrefix(line, "SF:"))
			if cur = cov[name]; cur == nil {
				cur = map[int]int64{}
				cov[name] = cur
			}
			open = true
		case strings.HasPrefix(line, "DA:"):
			if !open {
				return nil, fmt.Errorf("line %d: a DA record outside an SF record", n)
			}
			f := strings.Split(strings.TrimPrefix(line, "DA:"), ",")
			if len(f) < 2 {
				return nil, fmt.Errorf("line %d: a DA record needs a line number and a hit count", n)
			}
			ln, err := strconv.Atoi(f[0])
			if err != nil || ln < 1 {
				return nil, fmt.Errorf("line %d: DA line number %q is not a positive integer", n, f[0])
			}
			hits, err := strconv.ParseInt(f[1], 10, 64)
			if err != nil || hits < 0 {
				return nil, fmt.Errorf("line %d: DA hit count %q is not a non-negative integer", n, f[1])
			}
			cur[ln] += hits
		case line == "end_of_record":
			open = false
		}
	}
	if err := sc.Err(); err != nil {
		return nil, err
	}
	if open {
		return nil, fmt.Errorf("the coverage file ends inside a record (no end_of_record): it is truncated")
	}
	return cov, nil
}

// ParseGoCover reads a profile from go test -coverprofile. Each block is
// "file:startLine.startCol,endLine.endCol numStmt count", and a line counts as
// executable only where a block with statements starts or ends. Lines in the
// middle of a block, such as a comment, are not executable. The module prefix
// is stripped from file names, and files outside the module are dropped.
func ParseGoCover(r io.Reader, module string) (Coverage, error) {
	cov := make(Coverage)
	prefix := module + "/"
	sc := newScanner(r)
	for n := 1; sc.Scan(); n++ {
		line := sc.Text()
		if strings.HasPrefix(line, "mode:") || line == "" {
			continue
		}
		colon := strings.LastIndex(line, ":")
		if colon < 0 {
			return nil, fmt.Errorf("line %d: not a cover profile block", n)
		}
		file := line[:colon]
		f := strings.Fields(line[colon+1:])
		if len(f) != 3 {
			return nil, fmt.Errorf("line %d: a cover block needs a range, a statement count and a count", n)
		}
		span := strings.SplitN(f[0], ",", 2)
		if len(span) != 2 {
			return nil, fmt.Errorf("line %d: a cover block needs a start and an end position", n)
		}
		startLine, err := blockLine(span[0])
		if err != nil {
			return nil, fmt.Errorf("line %d: %v", n, err)
		}
		endLine, err := blockLine(span[1])
		if err != nil {
			return nil, fmt.Errorf("line %d: %v", n, err)
		}
		numStmt, err := strconv.Atoi(f[1])
		if err != nil {
			return nil, fmt.Errorf("line %d: statement count %q is not an integer", n, f[1])
		}
		count, err := strconv.ParseInt(f[2], 10, 64)
		if err != nil || count < 0 {
			return nil, fmt.Errorf("line %d: block count %q is not a non-negative integer", n, f[2])
		}
		if !strings.HasPrefix(file, prefix) {
			continue
		}
		rel := strings.TrimPrefix(file, prefix)
		m := cov[rel]
		if m == nil {
			m = map[int]int64{}
			cov[rel] = m
		}
		if numStmt == 0 {
			continue
		}
		m[startLine] += count
		m[endLine] += count
	}
	if err := sc.Err(); err != nil {
		return nil, err
	}
	return cov, nil
}

// blockLine reads the line out of a "line.col" position.
func blockLine(pos string) (int, error) {
	dot := strings.Index(pos, ".")
	if dot < 0 {
		return 0, fmt.Errorf("position %q has no column", pos)
	}
	ln, err := strconv.Atoi(pos[:dot])
	if err != nil || ln < 1 {
		return 0, fmt.Errorf("position %q has a bad line", pos)
	}
	return ln, nil
}

// moduleOf reads the module path out of a go.mod file.
func moduleOf(gomod string) (string, error) {
	for _, line := range strings.Split(gomod, "\n") {
		f := strings.Fields(line)
		if len(f) >= 2 && f[0] == "module" {
			return strings.Trim(f[1], `"`), nil
		}
	}
	return "", fmt.Errorf("go.mod has no module line")
}

// normalise turns a path a coverage tool wrote into the repository-relative
// form the diff uses.
func normalise(root, p string) string {
	p = filepath.ToSlash(p)
	if path.IsAbs(p) {
		if rel, err := filepath.Rel(root, filepath.FromSlash(p)); err == nil && rel != ".." && !strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
			p = filepath.ToSlash(rel)
		}
	}
	return path.Clean(p)
}

func newScanner(r io.Reader) *bufio.Scanner {
	sc := bufio.NewScanner(r)
	sc.Buffer(make([]byte, 0, 64*1024), 16*1024*1024)
	return sc
}
