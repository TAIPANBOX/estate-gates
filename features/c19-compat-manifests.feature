# language: en

Feature: A repository at 1.0 declares its compatibility surface and holds it

  @decided 2026-09-12
  """
  SemVer item 5: version 1.0.0 defines the public API. The estate's first two
  1.0 tags, agent-passport and agent-stack-go, were cut on 2026-09-12 with the
  surface written down (SPEC.md section 10; api/surface.txt) and a gate in each
  repository that fails when the surface moves. The decision behind this gate:
  a 1.0 is earned per plane by its own rows and never stamped uniformly, and no
  plane reaches 1.0 without both halves. This gate is what makes a third 1.0
  without them red.
  """

  The declaration lives in estate.json: `major`, and `compat` naming the
  manifest and the gate (defaults compat/1.0.json and
  scripts/compat-surface.sh), or an exemption with its reason. A repository at
  0.x with no declaration has nothing to hold.

  @fires:c19.undeclared-major
  Scenario: A 1.0 tag was cut with no surface declared
    Given a repository whose newest tag is 1.0.0 or above
    And estate.json declares no major for it
    When the estate is read
    Then it is refused, naming the tag
    Because a 1.0 is a promise about a surface, and a promise nobody can point at is a mood

  @fires:c19.manifest-missing
  Scenario: The declared manifest is not in the repository
    Given a repository declaring a major and a manifest path
    And no file at that path
    When the estate is read
    Then it is refused, naming the path it looked at

  @fires:c19.gate-missing
  Scenario: The declared gate is not in the repository
    Given a repository declaring a major and a gate path
    And no script at that path
    When the estate is read
    Then it is refused, naming the path it looked at

  @fires:c19.gate-not-in-ci
  Scenario: The gate exists and no workflow runs it
    Given a repository whose surface gate no file under .github/workflows names
    When the estate is read
    Then it is refused
    Because a gate nobody runs on every push holds nothing

  @fires:c19.tag-major-mismatch
  Scenario: A major is declared and the newest tag is below it
    Given a repository declaring major 1 whose newest tag is 0.9.0
    When the estate is read
    Then it is refused, naming both
    Because a reader of estate.json would believe a surface is frozen that is not

  @fires:c19.no-tags
  Scenario: A major is declared and no tag exists at all
    Given a repository declaring a major and carrying no v* tag
    When the estate is read
    Then it is refused
    Because a declaration ahead of every release is a plan, not a promise

  @fires:c19.no-subjects
  Scenario: Nothing in the estate is at 1.0
    Given no repository declares a major and none carries a tag at 1.0.0 or above
    When the estate is read
    Then it is refused as having measured nothing
    Because the estate has two such repositories, so finding none means the wrong thing was read
