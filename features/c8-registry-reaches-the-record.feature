# language: en

Feature: Every registered event type is a decision at the record plane

  @measured 2026-08-07
  """
  policy_updated, wardryx's admin type, registered at severity high and
  emitted whenever an operator changes a policy through the policy-as-code
  API. trailryx neither mapped it nor named it as refused, so the record plane
  silently dropped the event that says somebody changed the rules.
  """

  A type the record does not know is refused and counted, and that refusal is
  correct. The problem is that "we decided this does not belong in the record"
  and "nobody got to it" produce exactly the same refusal, the same counter
  and the same silence, and only one of them is a decision somebody made.

  @fires:c8.type-unanswered
  Scenario: A registered type the record neither maps nor refuses by name
    Given a type in the registry
    And a record plane that does not map it
    And no passage naming it as deliberately refused
    When the estate is read
    Then it is refused, listing the unanswered types
    Because the record plane's whole claim is that it holds what happened,
      and an unanswered type leaves silently

  @fires:c8.mapper-file-gone
  Scenario: The mapper file is not there
    Given the record plane recorded as mapping the envelope from a path
    And no file at that path
    When the estate is read
    Then it says so
    Because the mapper moving and the record plane no longer reading the bus
      need different fixes

  @fires:c8.mapper-unreadable
  Scenario: The mapper cannot be read
    Given a mapper this run could not open
    When the comparison is attempted
    Then it says so

  @fires:c8.registry-unparsed
  Scenario: The registry cannot be parsed
    Given a registry section that does not read as a table
    When the estate is read
    Then it says so
