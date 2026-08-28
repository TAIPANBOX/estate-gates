# language: en

Feature: A vendored schema is byte-identical to the schema it claims to be

  @measured 2026-08-05
  """
  agent-conform advertises full schema validation. Its vendored copy of the
  passport schema fell three weeks behind the canonical one, so the two fields
  that exist for AI Act code inventory, filesystem and models, were simply not
  part of what it validated. Nothing was broken in either repository. The tool
  passed, the schema passed, and the claim between them was false.
  """

  Copies are fine. Copies nothing watches are the defect.

  @fires:c2.bytes-differ
  Scenario: A copy has drifted from its canonical
    Given a repository vendoring a canonical schema
    And the copy differing from the original by any byte
    When the estate is read
    Then it is refused, naming both paths
    Because a validator running an old copy reports a pass it never earned

  @fires:c2.copy-unwatched
  Scenario: A copy nobody declared, found by what it claims to be
    Given a file carrying a canonical schema's $id at an undeclared path
    When the estate is searched
    Then it is refused as a copy nothing compares
    Because the hand-written list was itself a copy of the truth that nothing
      watched, and on 2026-08-26 it was two entries short: agent-stack-go
      vendored the v0.3 envelope and a second passport schema, and both
      drifted in silence while the six that WERE named went red

  @fires:c2.canonical-has-no-id
  Scenario: The canonical carries no $id
    Given a canonical schema with no $id to be claimed by
    When copies are discovered
    Then it is refused
    Because discovery by $id is what survives a rename, and without one no
      copy of this schema can be found that way at all

  @fires:c2.canonical-gone
  Scenario: The canonical is missing and copies still claim it
    Given vendored copies claiming a canonical that is not there
    When the comparison is attempted
    Then it says so
    Because none of them can be checked while the original is missing, and
      that is not the same as them agreeing

  @fires:c2.copy-gone
  Scenario: A declared copy is not there
    Given a repository recorded as vendoring a schema at a path
    And no file at that path
    When the estate is read
    Then it says so
    Because a copy that was deleted and a copy that moved need different
      fixes, and silence would look like the first
