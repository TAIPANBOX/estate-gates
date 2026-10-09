package main

import (
	"bufio"
	"errors"
	"fmt"
	"os"
	"path"
	"regexp"
	"strings"
)

// allowEntry permits one value, by fingerprint, in the paths one glob matches.
// It names the value's fingerprint and never the value, so the allowlist can
// be public without becoming the leak it exists to prevent. Every entry must
// say why: an exception nobody can re-derive is how a gate goes soft.
type allowEntry struct {
	fp, glob, reason string
	line             int
	used             bool
}

type allowlist struct{ entries []*allowEntry }

var fpRe = regexp.MustCompile(`^[0-9a-f]{16}$`)

func loadAllow(p string) (*allowlist, error) {
	a := &allowlist{}
	f, err := os.Open(p)
	if errors.Is(err, os.ErrNotExist) {
		return a, nil
	}
	if err != nil {
		return nil, err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	n := 0
	for sc.Scan() {
		n++
		raw := strings.TrimSpace(sc.Text())
		if raw == "" || strings.HasPrefix(raw, "#") {
			continue
		}
		body, reason, ok := strings.Cut(raw, "#")
		reason = strings.TrimSpace(reason)
		if !ok || reason == "" {
			return nil, fmt.Errorf("%s:%d: an entry needs a reason after '#'", p, n)
		}
		fields := strings.Fields(body)
		if len(fields) != 2 || !fpRe.MatchString(fields[0]) {
			return nil, fmt.Errorf("%s:%d: want '<16-hex fingerprint> <path-glob> # reason'", p, n)
		}
		if _, err := path.Match(fields[1], ""); err != nil {
			return nil, fmt.Errorf("%s:%d: bad glob %q", p, n, fields[1])
		}
		a.entries = append(a.entries, &allowEntry{fp: fields[0], glob: fields[1], reason: reason, line: n})
	}
	return a, sc.Err()
}

// globMatch adds `**/` (any directory depth) to path.Match.
func globMatch(glob, p string) bool {
	if ok, _ := path.Match(glob, p); ok {
		return true
	}
	if rest, ok := strings.CutPrefix(glob, "**/"); ok {
		parts := strings.Split(p, "/")
		for i := range parts {
			if m, _ := path.Match(rest, strings.Join(parts[i:], "/")); m {
				return true
			}
		}
	}
	return false
}

func (a *allowlist) permits(f Finding) bool {
	fp := f.Fingerprint()
	for _, e := range a.entries {
		if e.fp == fp && globMatch(e.glob, f.Path) {
			e.used = true
			return true
		}
	}
	return false
}

func (a *allowlist) unused() []*allowEntry {
	var out []*allowEntry
	for _, e := range a.entries {
		if !e.used {
			out = append(out, e)
		}
	}
	return out
}

func (a *allowlist) unusedIf(whole bool) []*allowEntry {
	if !whole {
		return nil
	}
	return a.unused()
}
