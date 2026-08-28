# language: en

Feature: A vendored cross-language table is the table, byte for byte

  @measured 2026-08-27
  """
  Some rules cannot be shared: what the record accepts of a chain, the door
  that is forbidden from importing it, and a third implementation in another
  language with no seam to either. The rules exist three times by
  construction, and three of them were found disagreeing in one afternoon.
  Prose did not hold them, and a gate reading source text could not: a regex
  over two languages says a rule is MENTIONED, never that it ANSWERS.
  """

  The answer was a table each implementation runs, which a comment cannot
  satisfy. The subjects are found by the source each table names, so a new
  language vendoring it is checked from the day it lands rather than the day
  somebody remembers this file.

  @fires:c14.copy-drifted
  Scenario: A vendored copy of a table differs from the table
    Given a canonical table and copies naming it as their source
    When they are compared
    Then a drifted copy is refused, counting how many of how many
    Because a table only holds while every copy is the same table: let one
      drift and each implementation passes its own copy, and the estate is
      back where it started with a green check on top

  @fires:c14.copy-unexercised
  Scenario: A copy no suite in its repository reads
    Given a byte-identical copy of a table
    And no test in that repository running it
    When the estate is read
    Then it is refused
    Because byte-identical copies of a table nobody runs are files that agree
      about nothing, and keeping them byte-perfect would be the whole
      appearance of a check with none of it

  @fires:c14.canonical-missing
  Scenario: Copies name a source and nothing is at that path
    Given files declaring a canonical table that is not there
    When the estate is read
    Then it is refused, listing the copies
    Because a copy whose canonical is gone is one nothing can be compared
      against

  @fires:c14.no-tables
  Scenario: No table anywhere carries the marker
    Given an estate where no JSON file declares one
    When the tables are discovered
    Then it says it measured nothing
    Because either the convention moved or this script's discovery broke,
      both need a person, and neither is a pass
