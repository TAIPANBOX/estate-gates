# language: en

Feature: Constants retyped by hand into another language still agree

  @measured 2026-08-04
  """
  verdryx held seven of the nine Breaker block-decision wire strings. The
  other two, unit_budget_exceeded and identity_mismatch, had been in tokenfuse
  since 2026-07-23. For eleven days verdryx counted the avoided estimate on
  those two decisions as real money, because a blocked call's cost_microusd
  carries what was NOT spent. Both repositories were internally consistent.
  Both test suites were green.
  """

  The copy was correct on the day it was written and nothing was watching it
  afterwards.

  @fires:c3.blocked-differ
  Scenario: The block-decision strings do not agree as sets
    Given tokenfuse's Breaker decisions and verdryx's mirror of them
    When the two are compared
    Then a difference in membership is refused
    And order is not compared, because order is not a contract and
      membership is

  @fires:c3.prices-differ
  Scenario: The price book and its mirror disagree
    Given the gateway's default price book
    And verdryx's copy of it
    When the two are compared per model
    Then any disagreement is refused
    Because a mirrored price is what an unlisted spend resolves through, and
      a wrong one is money reported wrongly rather than an error

  @fires:c3.fallback-differs
  Scenario: The conservative fallback price differs
    Given a fallback rate on each side
    When they are compared
    Then a difference is refused, printing both
    Because the fallback is the rate every unlisted model resolves through,
      so it is the one price that is always in use

  @fires:c3.verdryx-fallback-missing
  Scenario: The mirror has no fallback at all
    Given verdryx with no fallback declared
    When the fallback is read
    Then it says so
    Because a missing fallback is not a matching one

  @fires:c3.column-absent
  Scenario: A column read on one side is not in the schema written on the other
    Given the Parquet column names verdryx reads
    And tokenfuse's read schema
    When they are compared
    Then a column absent from the schema is refused, counting how many
    Because a reader asking for a column nobody writes gets nothing rather
      than an error

  @fires:c3.tokenfuse-unreadable
  Scenario: The source side cannot be read
    Given tokenfuse's constants unreadable in this run
    When the comparison is attempted
    Then it says so rather than passing
    Because the two modes of this check, a generated artifact and a regular
      expression over Rust, differ in strength and the output names which
      one ran

  @fires:c3.verdryx-blocked-unreadable
  Scenario: The mirror's decisions cannot be read
    Given verdryx's block-decision list unreadable
    When the comparison is attempted
    Then it says so

  @fires:c3.verdryx-prices-unreadable
  Scenario: The mirror's price book cannot be read
    Given verdryx's price book unreadable
    When the comparison is attempted
    Then it says so

  @fires:c3.verdryx-columns-unreadable
  Scenario: The mirror's column list cannot be read
    Given verdryx's column names unreadable
    When the comparison is attempted
    Then it says so
