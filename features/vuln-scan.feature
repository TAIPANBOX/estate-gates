# language: en

Feature: Every night, the main branch of every repository is read for known vulnerabilities

  @decided 2026-11-11
  """
  A new advisory is published on nobody's schedule, and a repository audits its
  dependencies only when somebody pushes. GitHub switches scheduled workflows
  off in a public repository after 60 days without activity, so a schedule in
  each repository would silently stop covering the quiet ones. The scan lives
  here instead, where the job is active every day and the subject list is
  estate.json. It runs the tool each repository already treats as a required
  check, so a red night means the next pull request there is red as well. The
  first version carries no list of exceptions of its own.
  """

  scripts/vuln-scan.py clones main of every repository estate.json names and
  runs govulncheck, cargo-audit, pip-audit or osv-scanner over what it finds.
  Each scenario below is bound to a case in scripts/vuln-scan-selftest.py that
  plants the fault in a miniature estate and requires the scanner to say so.
  Those cases run in the scan workflow before the scan does.

  @scan:rust-vulnerable-crate-is-a-finding
  Scenario: A lock file holds a crate with a published advisory
    Given a Cargo.lock pins a crate version that carries a RUSTSEC advisory
    When the scan runs
    Then the lock file is a FINDING naming the advisory, the crate and the version, and the exit code is 1
    Because cargo-audit is what the Rust repositories run on their pull requests, so what it finds is what their next pull request would find

  @scan:go-called-vulnerable-function-is-a-finding
  Scenario: A Go module calls a vulnerable function of an old dependency
    Given a Go module calls a function that a GO advisory names, in a version before the fix
    When the scan runs
    Then the module is a FINDING naming the GO id and the version that fixes it, and the exit code is 1
    Because govulncheck weighs reachability, and a called vulnerable function is the case it exists for

  @scan:go-imported-but-not-called-is-clean
  Scenario: A Go module imports a vulnerable package and never calls the vulnerable function
    Given a Go module imports a package with an advisory and calls none of the affected functions
    When the scan runs
    Then the module is clean and the exit code is 0
    Because the required check in every Go repository says the same, and a night that is red where the pull request is green would teach people to ignore it

  @scan:js-lockfile-vulnerable-package-is-a-finding
  Scenario: A JavaScript lock file holds a package with a published advisory
    Given a package-lock.json pins a package version with a GHSA advisory
    When the scan runs
    Then the lock file is a FINDING naming the package, the version and the advisory ids
    Because no JavaScript lock file in the estate has a tool of its own, so osv-scanner reads it

  @scan:py-requirements-vulnerable-pin-is-a-finding
  Scenario: A Python requirements file pins a package with a published advisory
    Given a requirements.txt pins a package version with a published advisory
    When the scan runs
    Then the file is a FINDING naming the package, the version and the fix
    Because pip-audit is what the Python repositories run, and a pinned file is read as it is

  @scan:clean-modules-are-clean
  Scenario: Modules with nothing to find are clean
    Given a Go module and a Rust lock file that carry no advisory
    When the scan runs
    Then each is reported clean, the summary says every subject was measured, and the exit code is 0
    Because a scan that cannot say clean is one nobody can act on, and the clean path is the one a broken scanner would fake

  @scan:nested-lockfiles-are-scanned
  Scenario: A lock file or module below the root is scanned on its own
    Given a repository whose root is clean and which holds a vulnerable module in a subdirectory
    When the scan runs
    Then the root is clean and the nested module is a FINDING with its own path
    Because tokenfuse keeps three lock files and vouchryx a second Go module, and a scan of the root alone would report them clean

  @scan:no-manifest-and-no-declaration-could-not-measure
  Scenario: A repository with no manifest and no declaration cannot be called clean
    Given a repository in estate.json holds no recognised manifest and does not record that it has none
    When the scan runs
    Then the line says COULD NOT MEASURE for it, the exit code is 2, and no OK line is printed
    Because a manifest in a format the scan does not know would otherwise read as a repository with nothing to find

  @scan:declared-no-manifests-is-not-a-finding
  Scenario: A repository that records having no manifest, and has none, is declared
    Given a repository whose estate.json entry records that it has no dependency manifest, and it has none
    When the scan runs
    Then the line says declared with the reason, and it is neither a finding nor a failure
    Because launchers, specifications and template repositories hold nothing for a vulnerability tool to read

  @scan:declared-none-but-manifests-exist-fails
  Scenario: A declaration of no manifest goes stale when a manifest appears
    Given a repository whose estate.json entry records no manifest and which now holds a go.mod
    When the scan runs
    Then the line is FAIL naming the manifest, and the exit code is 1
    Because a declaration nothing re-reads would switch the scan off for that repository for ever

  @scan:zero-subjects-scanned-is-not-green
  Scenario: A run that scanned nothing is not a clean run
    Given every repository in the registry is declared to hold no manifest
    When the scan runs
    Then the run says it measured nothing and the exit code is 2
    Because zero findings over zero subjects is a statement about the scanner, not about the estate

  @scan:estate-subject-without-a-clone-is-red
  Scenario: A repository in estate.json that was not read is red
    Given estate.json names a repository that is not among the checkouts
    When the scan runs
    Then the line says COULD NOT MEASURE and names the missing checkout, and the exit code is 2
    Because a repository that cannot be read must never read as one with nothing to find

  @scan:subjects-come-from-estate-json
  Scenario: The subject list is the registry, never a directory listing
    Given a checkout directory that estate.json does not name
    When the scan runs
    Then that directory is not scanned and does not appear
    Because a list of subjects kept anywhere else is the copy that goes stale first

  @scan:private-repository-is-partial-not-clean
  Scenario: A repository with no public remote is partial, never clean
    Given estate.json records a repository with no public remote and everything public is clean
    When the scan runs
    Then the line says NOT MEASURED with the recorded reason, the run says PARTIAL, and the exit code is 3
    Because the scan cannot read what CI cannot clone, and saying so is different from saying it is clean

  @scan:broken-tool-could-not-measure
  Scenario: A tool that cannot start is not a clean result
    Given the Go scanner binary exits with an error when started
    When the scan runs
    Then the subject is COULD NOT MEASURE, never clean, and the exit code is 2
    Because a tool that fails to run reports nothing, and nothing must not be read as clean

  @scan:missing-tool-could-not-measure
  Scenario: A tool that is not installed is not a clean result
    Given the Rust scanner binary does not exist
    When the scan runs
    Then the subject is COULD NOT MEASURE, never clean, and the exit code is 2
    Because a workflow step that fails to install a tool must turn the night red, not green

  @scan:wrong-tool-version-could-not-measure
  Scenario: A tool of another version is not trusted
    Given the Go scanner binary reports a version other than the pinned one and claims no vulnerabilities
    When the scan runs
    Then the subject is COULD NOT MEASURE naming the version, never clean
    Because the version is what makes a red night equal to a red pull request, and an unpinned tool would make them differ

  @scan:finding-outranks-could-not-measure
  Scenario: A finding is not hidden by a subject that could not be measured
    Given one repository has a finding and another could not be measured
    When the scan runs
    Then both are printed and the exit code is 1
    Because a red night about a vulnerability must name it even on a night the scanner also failed somewhere
