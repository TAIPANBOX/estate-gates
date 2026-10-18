package main

import (
	"fmt"
	"io"
	"strconv"
	"strings"
)

// Diff is what a change touches and adds, read from a unified diff with no
// context lines.
type Diff struct {
	// Files is every file the diff touches, under its new name for a rename.
	Files []string
	// Added holds, per file, the line numbers in the new file of the lines the
	// change adds, ascending. Deleted lines add nothing and move nothing.
	Added map[string][]int
}

// ParseDiff reads a unified diff. Hunk bodies are read by their counts, not by
// their first character, so an added line whose text starts with "++" is
// content and not a file header.
func ParseDiff(r io.Reader) (Diff, error) {
	d := Diff{Added: map[string][]int{}}
	seen := map[string]bool{}
	touch := func(p string) {
		if p != "" && !seen[p] {
			seen[p] = true
			d.Files = append(d.Files, p)
		}
	}
	var (
		cur              string // new-side path; "" for a deletion
		oldLeft, newLeft int    // lines still to read in the open hunk
		newLine          int    // number of the next new-side line
		err              error
	)
	sc := newScanner(r)
	for n := 1; sc.Scan(); n++ {
		line := strings.TrimRight(sc.Text(), "\r")
		if oldLeft > 0 || newLeft > 0 {
			if line == "" {
				return d, fmt.Errorf("line %d: an empty line inside a hunk", n)
			}
			switch line[0] {
			case '+':
				if newLeft == 0 {
					return d, fmt.Errorf("line %d: more added lines than the hunk header counts", n)
				}
				if cur != "" {
					d.Added[cur] = append(d.Added[cur], newLine)
				}
				newLine++
				newLeft--
			case '-':
				if oldLeft == 0 {
					return d, fmt.Errorf("line %d: more removed lines than the hunk header counts", n)
				}
				oldLeft--
			case ' ':
				if oldLeft == 0 || newLeft == 0 {
					return d, fmt.Errorf("line %d: more context lines than the hunk header counts", n)
				}
				oldLeft--
				newLeft--
				newLine++
			case '\\':
				// "\ No newline at end of file" is a marker, not a line.
			default:
				return d, fmt.Errorf("line %d: not a hunk line", n)
			}
			continue
		}
		switch {
		case strings.HasPrefix(line, "diff --git "):
			cur = ""
			touch(bPath(strings.TrimPrefix(line, "diff --git ")))
		case strings.HasPrefix(line, "rename to "):
			touch(diffPath(strings.TrimPrefix(line, "rename to ")))
		case strings.HasPrefix(line, "+++ "):
			p, _, _ := strings.Cut(strings.TrimPrefix(line, "+++ "), "\t")
			cur = ""
			if p != "/dev/null" {
				cur = diffPath(p)
				touch(cur)
			}
		case strings.HasPrefix(line, "@@ "):
			oldLeft, newLine, newLeft, err = parseHunk(line)
			if err != nil {
				return d, fmt.Errorf("line %d: %v", n, err)
			}
		}
	}
	if err := sc.Err(); err != nil {
		return d, err
	}
	return d, nil
}

// bPath reads the new-side path from the rest of a "diff --git" line. A quoted
// name is left to the +++ line, which carries the same path.
func bPath(rest string) string {
	if strings.HasPrefix(rest, `"`) {
		return ""
	}
	i := strings.LastIndex(rest, " b/")
	if i < 0 {
		return ""
	}
	return rest[i+3:]
}

// diffPath strips git's b/ prefix and any C-style quoting.
func diffPath(p string) string {
	if strings.HasPrefix(p, `"`) {
		if u, err := strconv.Unquote(p); err == nil {
			p = u
		}
	}
	return strings.TrimPrefix(p, "b/")
}

// parseHunk reads "@@ -old[,n] +new[,n] @@". A missing count means one line.
func parseHunk(line string) (oldN, newStart, newN int, err error) {
	f := strings.Fields(line)
	if len(f) < 3 || !strings.HasPrefix(f[1], "-") || !strings.HasPrefix(f[2], "+") {
		return 0, 0, 0, fmt.Errorf("malformed hunk header")
	}
	if _, oldN, err = span(f[1][1:]); err != nil {
		return 0, 0, 0, fmt.Errorf("malformed hunk header: %v", err)
	}
	if newStart, newN, err = span(f[2][1:]); err != nil {
		return 0, 0, 0, fmt.Errorf("malformed hunk header: %v", err)
	}
	return oldN, newStart, newN, nil
}

func span(s string) (start, count int, err error) {
	a, b, hasCount := strings.Cut(s, ",")
	if start, err = strconv.Atoi(a); err != nil {
		return 0, 0, err
	}
	count = 1
	if hasCount {
		if count, err = strconv.Atoi(b); err != nil {
			return 0, 0, err
		}
	}
	return start, count, nil
}
