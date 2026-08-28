# language: en

Feature: A git command aimed at another repository clears the hook's environment

  @measured 2026-08-26
  """
  Found in trailryx, in a check asking whether the local advisory database has
  untracked files. From a terminal it answered nothing, correctly. From the
  pre-push hook it answered 1221 lines, every entry of the database, and
  refused the push. Deterministic, and invisible from a terminal, which is why
  three sessions in a row retried instead of looking at the environment.
  """

  git runs a hook with GIT_DIR set, pointing at the repository being pushed.
  Changing the working directory does not clear it, so the command reads the
  other repository's tree against THIS repository's index and object database.
  The failure only exists in a context nobody debugs from.

  @fires:c9.foreign-git-keeps-the-environment
  Scenario: A script runs git against another repository without clearing the variables
    Given a shell script under a scanned directory
    And a git invocation aimed at another path
    And no clearing of the variables git exports into a hook
    When the estate is read
    Then it is refused, counting the invocations and naming the repository
    Because the worse shape is the quieter one: a status under the wrong
      index reports files that are not untracked, which is loud, while
      resolving a ref under the wrong object database succeeds and returns
      the WRONG CONTENT, so a check comparing a vendored copy against its
      canonical would compare the copy against itself and report agreement

  @fires:c9.nothing-scanned
  Scenario: Repositories were readable and not one script was found
    Given repositories that opened
    And no shell script under any scanned directory
    When the scan finishes
    Then it says it measured nothing
    Because either the estate stopped keeping its gates there or this check's
      file filter stopped matching, and a scan that read nothing must not
      report agreement
