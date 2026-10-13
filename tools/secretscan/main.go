package main

import (
	"bufio"
	"bytes"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path"
	"strconv"
	"strings"
)

// Exit codes. 3 is the one that matters most: a scan that read nothing has not
// passed, and saying OK there is the failure this estate's gates keep finding
// in themselves.
const (
	exitClean    = 0
	exitFound    = 1
	exitUsage    = 2
	exitMeasured = 3
)

const usage = `secretscan: refuse a secret on its way into a repository, never print it.

  secretscan push                 read git's pre-push stdin, scan the added lines
  secretscan diff <rev-range>     scan the lines a range adds
  secretscan tree [rev]           scan every tracked file at rev (default HEAD)
  secretscan history              scan every blob reachable from any ref

  -C dir        run as if started in dir
  -allow file   allowlist (default .secretscan-allow at the repository root)

Exit 0 clean, 1 findings, 2 usage or git error, 3 measured nothing.
`

func main() {
	os.Exit(run(os.Args[1:], os.Stdin, os.Stdout, os.Stderr))
}

func run(args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("secretscan", flag.ContinueOnError)
	fs.SetOutput(stderr)
	dir := fs.String("C", ".", "repository directory")
	allowPath := fs.String("allow", "", "allowlist file")
	fs.Usage = func() { fmt.Fprint(stderr, usage) }
	if err := fs.Parse(args); err != nil {
		return exitUsage
	}
	rest := fs.Args()
	if len(rest) == 0 {
		fs.Usage()
		return exitUsage
	}
	g := gitRunner{dir: *dir}
	if *allowPath == "" {
		top, err := g.out("rev-parse", "--show-toplevel")
		if err != nil {
			top = *dir
		}
		*allowPath = path.Join(strings.TrimSpace(top), ".secretscan-allow")
	}
	allow, err := loadAllow(*allowPath)
	if err != nil {
		fmt.Fprintf(stderr, "secretscan: %v\n", err)
		return exitUsage
	}

	var findings []Finding
	var units int
	switch rest[0] {
	case "push":
		findings, units, err = scanPush(g, stdin)
	case "diff":
		if len(rest) != 2 {
			fs.Usage()
			return exitUsage
		}
		findings, units, err = scanRange(g, []string{rest[1]})
	case "tree":
		rev := "HEAD"
		if len(rest) > 1 {
			rev = rest[1]
		}
		findings, units, err = scanTree(g, rev)
	case "history":
		findings, units, err = scanHistory(g)
	default:
		fs.Usage()
		return exitUsage
	}
	if err != nil {
		fmt.Fprintf(stderr, "secretscan: %v\n", err)
		return exitUsage
	}
	if units == 0 && rest[0] != "push" {
		fmt.Fprintf(stderr, "secretscan: measured nothing: %s read no file content, so this is not a pass\n", rest[0])
		return exitMeasured
	}

	var kept []Finding
	for _, f := range findings {
		if allow.permits(f) {
			continue
		}
		kept = append(kept, f)
	}
	// Only a whole-tree read can say an entry matches nothing: a push carries
	// a few lines, and every entry for the rest of the tree is unused there.
	for _, e := range allow.unusedIf(rest[0] == "tree" || rest[0] == "history") {
		fmt.Fprintf(stderr, "secretscan: allowlist line %d (%s %s) matched nothing; remove it\n", e.line, e.fp, e.glob)
	}
	for _, f := range kept {
		fmt.Fprintf(stdout, "%s:%d: %s %s fp=%s\n", f.Path, f.Line, f.Rule, f.Masked(), f.Fingerprint())
	}
	if len(kept) > 0 {
		fmt.Fprintf(stderr, "secretscan: %d value(s) that look like secrets. If one is not, add\n"+
			"  <fp> <path-glob> # <why it is not a secret>\nto %s. Nothing above printed a value.\n", len(kept), *allowPath)
		return exitFound
	}
	fmt.Fprintf(stdout, "secretscan: clean, %d unit(s) read by %s\n", units, rest[0])
	return exitClean
}

type gitRunner struct{ dir string }

func (g gitRunner) cmd(args ...string) *exec.Cmd {
	c := exec.Command("git", append([]string{"-C", g.dir}, args...)...)
	return c
}

func (g gitRunner) out(args ...string) (string, error) {
	var stderr bytes.Buffer
	c := g.cmd(args...)
	c.Stderr = &stderr
	b, err := c.Output()
	if err != nil {
		return "", fmt.Errorf("git %s: %v: %s", strings.Join(args, " "), err, strings.TrimSpace(stderr.String()))
	}
	return string(b), nil
}

const zeroSHA = "0000000000000000000000000000000000000000"

// scanPush reads git's pre-push protocol: "<local ref> <local sha> <remote ref>
// <remote sha>" per line. A deletion adds nothing; a new branch is scanned
// against everything the remote already has, not against nothing.
func scanPush(g gitRunner, stdin io.Reader) ([]Finding, int, error) {
	var all []Finding
	units := 0
	sc := bufio.NewScanner(stdin)
	for sc.Scan() {
		f := strings.Fields(sc.Text())
		if len(f) != 4 || strings.Trim(f[1], "0") == "" {
			continue
		}
		var rng []string
		if strings.Trim(f[3], "0") == "" {
			rng = []string{f[1], "--not", "--remotes"}
		} else {
			rng = []string{f[3] + ".." + f[1]}
		}
		got, n, err := scanRange(g, rng)
		if err != nil {
			return nil, 0, err
		}
		all = append(all, got...)
		units += n
	}
	return all, units, sc.Err()
}

// scanRange scans only the lines the commits in a range add. --text and
// --no-textconv make git print every file's own bytes whatever
// .gitattributes or a diff driver says, so the binary decision is made here,
// by the NUL test tree uses on the same blob. A merge shows what it adds over
// git's own merge of its parents, which is a line written while resolving it
// and not the side branch again; by default a merge shows nothing.
func scanRange(g gitRunner, rng []string) ([]Finding, int, error) {
	args := append([]string{"log", "-p", "--no-color", "--no-ext-diff", "--no-textconv", "--text", "--full-index", "--diff-merges=remerge", "-U0", "--format=commit %H"}, rng...)
	out, err := g.out(args...)
	if err != nil {
		return nil, 0, err
	}
	r, err := newBlobReader(g)
	if err != nil {
		return nil, 0, err
	}
	defer r.close()
	seen := map[string]bool{}
	return scanPatch(out, func(blob string) (bool, error) {
		if b, ok := seen[blob]; ok {
			return b, nil
		}
		data, err := r.read(blob)
		if err != nil {
			return false, err
		}
		seen[blob] = binary(data)
		return seen[blob], nil
	})
}

// binary is git's own test for a binary file, a NUL in the first 8000 bytes.
func binary(data []byte) bool { return bytes.IndexByte(data[:min(len(data), 8000)], 0) >= 0 }

// scanPatch reads `git log -p -U0` output. Inside a hunk the counts in its
// header decide which lines are content, so an added line that reads "++ x"
// is content and not a file header; it once was, and the next finding in the
// file printed that line, value and all, as its path.
func scanPatch(patch string, isBinary func(blob string) (bool, error)) ([]Finding, int, error) {
	var findings []Finding
	units := 0
	file, blob, skip, gitlink := "", "", true, false
	line, adds, dels := 0, 0, 0
	for _, l := range strings.Split(patch, "\n") {
		if adds > 0 || dels > 0 {
			switch {
			case strings.HasPrefix(l, "+"):
				if !skip {
					units++
					findings = append(findings, ScanLine(file, line, l[1:])...)
				}
				adds--
				line++
			case strings.HasPrefix(l, "-"):
				dels--
			case strings.HasPrefix(l, " "):
				adds--
				dels--
				line++
			}
			continue
		}
		switch {
		case strings.HasPrefix(l, "diff --git "):
			file, blob, skip, gitlink = "", "", true, false
		case strings.HasPrefix(l, "new file mode ") || strings.HasPrefix(l, "new mode "):
			gitlink = strings.HasSuffix(l, " 160000")
		case strings.HasPrefix(l, "index "):
			// index <old>..<new>[ <mode>]; mode 160000 is a submodule, whose id
			// names a commit in another repository and which tree passes over.
			if f := strings.Fields(l); len(f) >= 2 {
				_, blob, _ = strings.Cut(f[1], "..")
				gitlink = gitlink || len(f) >= 3 && f[2] == "160000"
			}
		case strings.HasPrefix(l, "+++ "):
			file = patchPath(strings.TrimPrefix(l, "+++ "))
			skip = file == "/dev/null" || blob == "" || gitlink
			if !skip {
				b, err := isBinary(blob)
				if err != nil {
					return nil, 0, err
				}
				skip = b
			}
		case strings.HasPrefix(l, "@@ "):
			// @@ -a[,b] +c[,d] @@
			f := strings.Fields(l)
			if len(f) >= 3 {
				_, dels = hunkRange(f[1])
				line, adds = hunkRange(f[2])
			}
		}
	}
	return findings, units, nil
}

// hunkRange reads "-a,b" or "+c,d"; a count left out is 1.
func hunkRange(s string) (start, count int) {
	a, b, ok := strings.Cut(s[1:], ",")
	start, _ = strconv.Atoi(a)
	count = 1
	if ok {
		count, _ = strconv.Atoi(b)
	}
	return start, count
}

// patchPath turns the path of a "+++ " line into the path tree prints: git
// quotes a name holding a quote, a backslash, a control character or a
// non-ASCII byte, and writes a tab after a name holding a space.
func patchPath(p string) string {
	if strings.HasPrefix(p, `"`) {
		if u, err := strconv.Unquote(p); err == nil {
			p = u
		}
	} else {
		p = strings.TrimSuffix(p, "\t")
	}
	return strings.TrimPrefix(p, "b/")
}

// blob reads objects through one long-lived cat-file process.
type blobReader struct {
	cmd *exec.Cmd
	in  io.WriteCloser
	out *bufio.Reader
}

func newBlobReader(g gitRunner) (*blobReader, error) {
	c := g.cmd("cat-file", "--batch")
	in, err := c.StdinPipe()
	if err != nil {
		return nil, err
	}
	o, err := c.StdoutPipe()
	if err != nil {
		return nil, err
	}
	if err := c.Start(); err != nil {
		return nil, err
	}
	return &blobReader{cmd: c, in: in, out: bufio.NewReaderSize(o, 1<<20)}, nil
}

func (b *blobReader) read(sha string) ([]byte, error) {
	if _, err := io.WriteString(b.in, sha+"\n"); err != nil {
		return nil, err
	}
	hdr, err := b.out.ReadString('\n')
	if err != nil {
		return nil, err
	}
	f := strings.Fields(hdr)
	if len(f) != 3 {
		return nil, errors.New("cat-file: " + strings.TrimSpace(hdr))
	}
	size, err := strconv.Atoi(f[2])
	if err != nil {
		return nil, err
	}
	data := make([]byte, size+1)
	if _, err := io.ReadFull(b.out, data); err != nil {
		return nil, err
	}
	return data[:size], nil
}

func (b *blobReader) close() { b.in.Close(); b.cmd.Wait() }

// scanBlobs skips what binary() calls binary, as scanRange does, so tree and
// history read the files whose added lines diff and push read. It once also
// skipped every text blob over 2 MiB, which diff reads (a 2.8 MB bundle,
// 2026-10-13); the blob was in memory either way.
func scanBlobs(g gitRunner, blobs [][2]string) ([]Finding, int, error) {
	r, err := newBlobReader(g)
	if err != nil {
		return nil, 0, err
	}
	defer r.close()
	var findings []Finding
	units := 0
	for _, b := range blobs {
		data, err := r.read(b[0])
		if err != nil {
			return nil, 0, err
		}
		if binary(data) {
			continue
		}
		units++
		findings = append(findings, ScanText(b[1], string(data))...)
	}
	return findings, units, nil
}

func scanTree(g gitRunner, rev string) ([]Finding, int, error) {
	// The default format, not --format: git 2.56 quotes a --format %(path)
	// holding a quote or a non-ASCII byte even under -z, and diff, push and
	// history print those paths as they are.
	out, err := g.out("ls-tree", "-r", "-z", rev)
	if err != nil {
		return nil, 0, err
	}
	var blobs [][2]string
	for _, e := range strings.Split(out, "\x00") {
		// <mode> <type> <object>\t<path>
		meta, p, ok := strings.Cut(e, "\t")
		f := strings.Fields(meta)
		if !ok || len(f) != 3 || f[1] != "blob" {
			continue
		}
		blobs = append(blobs, [2]string{f[2], p})
	}
	return scanBlobs(g, blobs)
}

func scanHistory(g gitRunner) ([]Finding, int, error) {
	out, err := g.out("rev-list", "--all", "--objects")
	if err != nil {
		return nil, 0, err
	}
	paths := map[string]string{}
	var order []string
	for _, l := range strings.Split(out, "\n") {
		sha, p, ok := strings.Cut(l, " ")
		if !ok {
			continue
		}
		if _, dup := paths[sha]; !dup {
			paths[sha] = p
			order = append(order, sha)
		}
	}
	chk := g.cmd("cat-file", "--batch-check")
	chk.Stdin = strings.NewReader(strings.Join(order, "\n") + "\n")
	b, err := chk.Output()
	if err != nil {
		return nil, 0, err
	}
	var blobs [][2]string
	for _, l := range strings.Split(string(b), "\n") {
		f := strings.Fields(l)
		if len(f) == 3 && f[1] == "blob" {
			blobs = append(blobs, [2]string{f[0], paths[f[0]]})
		}
	}
	return scanBlobs(g, blobs)
}
