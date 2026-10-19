# language: en

Feature: Every cosign sign of a container image carries the legacy bundle flags

  @decided 2026-10-19
  """
  Image signatures in the estate use the bundle format that policy-controller
  reads, which is the legacy one. A signing step that drops either of the two
  flags that keep that format writes a signature no cluster verifier reads, and
  nothing fails at signing time. A gate reads every sign line of every estate
  repository and says so when one drops a flag.
  """

  The check reads every workflow file of every repository estate.json names. A
  line that runs cosign sign is a sign of an image. sign-blob and attest are not
  judged. Both flags must appear as --flag=false, because the flags are booleans
  and the space form sets them to true.

  @fires:c26.legacy-flag-missing
  Scenario: A sign line of an image drops a legacy flag
    Given a workflow runs cosign sign on an image without --new-bundle-format=false
    When the estate is read
    Then the finding is red, naming the repository, the file, the line and the flag
    Because a signature in the wrong bundle format is refused at admission, after the sign step has already passed

  @fires:c26.no-subjects
  Scenario: No workflow in the estate signs an image
    Given no workflow in any repository runs cosign sign on an image
    When the estate is read
    Then the gate says it measured nothing rather than agreeing
    Because a gate over zero sign lines would report agreement with nothing
