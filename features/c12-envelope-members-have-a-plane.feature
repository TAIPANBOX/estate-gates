# language: en

Feature: Every envelope member has a decision at the record plane

  @measured 2026-08-26
  """
  delegation_proof, in the v0.2 and v0.3 envelopes and emitted since that day.
  It records that the chain was PROVED. The record plane's kept-metadata list
  does not name it and the record repository does not mention it anywhere.
  That puts the chain in the kept plane and its proof in the erasable one, so
  a routine payload erasure turns a proven chain into an unproven one,
  silently, in the store whose whole claim is that it holds what happened in a
  form nobody can quietly alter.
  """

  This is not the type-level question one level down. A type the record does
  not know is refused and counted. A MEMBER has no refusal path at all: the
  mapper partitions every member into exactly two planes, and an unknown one
  is silently filed in the erasable half with nothing reported.

  @fires:c12.member
  Scenario: An envelope member the record plane has no decision about
    Given a member defined in the envelope schema
    And a mapper that neither consumes it into typed metadata nor names it in
      the plane-boundary passage
    When the estate is read
    Then it is refused, naming the member and where it is defined
    Because the mapper's own rule says a member it has never seen is by
      definition one it cannot classify, so silence is the designed outcome
      and the only place to catch it is here

  @fires:c12.schemas
  Scenario: No envelope schema could be found
    Given a schema directory with no envelope carrying properties
    When the members are read
    Then it says it measured nothing
    Because with no members to ask about, every mapper answers all of them

  @fires:c12.mapper-unreadable
  Scenario: The mapper cannot be read
    Given a mapper this run could not open
    When the partition is read
    Then it says so
    Because an unread mapper is not one that classifies everything
