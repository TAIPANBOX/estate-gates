# language: en

Feature: A rule retyped out of a schema still agrees with the schema

  @measured 2026-08-09
  """
  The agent_id grammar and the 255-byte cap the envelope puts on it exist as
  four separate constants in four repositories, read out of the SPEC once and
  retyped. A drifted file is visible in a diff. A drifted constant compiles,
  passes its own suite, and is only visible to somebody holding both
  repositories open.
  """

  The copy is what decides whether an emitter warns about an id a consumer
  will reject, so two copies that disagree mean two planes disagreeing about
  whether the same event is well formed.

  @fires:c7.pattern-differs
  Scenario: A copy enforces a different grammar
    Given a repository carrying its own agent_id pattern
    And that pattern differing from the published one
    When the estate is read
    Then it is refused, printing both
    Because the heaviest copy is imported by six repositories, so a
      disagreement propagates from it

  @fires:c7.cap-differs
  Scenario: A copy caps the length at a different number
    Given a repository capping an agent_id at its own byte count
    When it is compared with the published cap
    Then a difference is refused
    Because the cap is half the rule, and a copy enforcing only the grammar
      accepts an id the envelope rejects

  @fires:c7.anchor-gone
  Scenario: A copy no longer carries a pattern this check can find
    Given a repository whose grammar constant was renamed or removed
    When its pattern is read
    Then it is refused, printing what was looked for
    Because either it was renamed, in which case the anchor needs updating,
      or the copy is gone, and neither of those is agreement

  @fires:c7.cap-anchor-gone
  Scenario: A copy no longer carries a cap this check can find
    Given a repository whose cap constant cannot be located
    When the cap is read
    Then it is refused

  @fires:c7.copy-gone
  Scenario: A recorded copy is not there
    Given a repository recorded as holding a copy
    And the file absent
    When the estate is read
    Then it says so

  @fires:c7.canonical-gone
  Scenario: The published rule is missing
    Given no canonical schema to read the rule from
    When the comparison is attempted
    Then it says so
    Because every copy would be compared against nothing

  @fires:c7.canonical-unusable
  Scenario: The published rule cannot be read
    Given a canonical schema that does not yield the rule
    When the comparison is attempted
    Then it says so
