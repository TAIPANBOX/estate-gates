# language: en

Feature: Every action a workflow uses is pinned to a commit

  @measured 2026-09-13
  """
  Twenty-one repositories pinned ossf/scorecard-action to
  55891bbd73f2425e97637d96e306fc9d491d0b21 with the comment v2.4.4. The SHA is
  real and the workflow runs, but it is the SHA of the annotated TAG OBJECT of
  v2.4.4, not of the commit the tag points to, because git rev-parse and the
  GitHub API both answer with the tag object for an annotated tag. Every
  Scorecard run in the estate ended with "workflow verification failed:
  imposter commit", three retries and one warning, and no repository had a
  published score (SUP-4 of the 1.0 proving run). The same file pinned
  github/codeql-action the same way, under a comment naming a different
  version.
  """

  @decided 2026-09-13
  """
  A pin is the commit a tag points to, with the tag as a comment beside it. A
  tag name moves; a tag object is not what anything verifying the pin looks
  for. The gate reads every uses: line in every workflow and classifies the
  SHA from the action repository's own ref tips.
  """

  Subjects are the uses: lines of every .github/workflows file of every
  repository estate.json names. Local actions and docker images are skipped.
  A SHA at no ref tip (an older commit) is reported as not judged, never as a
  pass. The ref tips are read with git ls-remote, or from a fixture the
  self-test exports.

  @fires:c21.tag-object
  Scenario: A workflow pins an action to the SHA of an annotated tag object
    Given a uses: line whose 40-hex SHA is an annotated tag object of the action
    When the estate is read
    Then it is refused, naming the line and the commit the tag points to
    Because the workflow runs and anything verifying the pin refuses it

  @fires:c21.unpinned
  Scenario: A workflow uses an action by a tag name
    Given a uses: line ending in @v4
    When the estate is read
    Then it is refused, naming the line
    Because a tag name moves and the pin is a claim about what runs

  @fires:c21.no-subjects
  Scenario: No workflow in the estate uses an action
    Given no uses: line anywhere
    When the estate is read
    Then the gate says it measured nothing rather than reporting agreement
