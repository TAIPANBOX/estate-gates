# language: en

Feature: The pinned hash vectors, in every language that retypes them

  @measured 2026-08-05
  """
  Four implementations are supposed to reproduce the same bytes: Go, Rust in
  tokenfuse, and Python in engram and in verdryx. Three of the four hold the
  numbers as LITERALS in their own test suites, retyped by hand. Change the Go
  canonicalization, or the vector file, and the Rust and Python suites go on
  passing against the old numbers, every one of them reporting green while the
  four implementations produced three different chains.
  """

  The event log's tamper evidence is exactly the guarantee that would quietly
  stop being true.

  @fires:c6.canonical-differs
  Scenario: A copy's canonical string does not match the pinned one
    Given a copy pinning the canonical serialization of a vector
    When it is compared with the vector file
    Then a difference is refused, naming the vector and both paths
    Because the canonical string IS the comparison: each copy writes the event
      in its own language's literals, and canonicalization is what turns them
      into the same bytes

  @fires:c6.hash-differs
  Scenario: A copy's chain hash does not match the pinned one
    Given a copy pinning a chain hash
    When it is compared with the vector file
    Then a difference is refused

  @fires:c6.vector-count-differs
  Scenario: A copy pins a different number of vectors
    Given a copy with fewer or more vectors than the canonical file
    When they are compared
    Then it is refused, printing both counts
    Because a copy that stopped at two vectors is not asserting the third,
      and the non-ASCII one exists specifically to catch an encoding
      difference

  @fires:c6.copy-count-differs
  Scenario: The number of copies in the estate changed
    Given fewer or more copies found than this gate expects
    When the estate is read
    Then it is refused, listing what was found
    Because a copy that went away is an implementation nobody is comparing
      any more

  @fires:c6.copy-unreadable
  Scenario: A copy is in a form this gate has no extractor for
    Given a file pinning the vectors in an unhandled language
    When it is read
    Then it is refused
    Because reporting agreement about the copies it CAN read would be the
      silent half of this failure

  @fires:c6.copy-unparsed
  Scenario: A copy could not be parsed
    Given a copy whose contents do not parse
    When it is compared
    Then it says so

  @fires:c6.no-copies
  Scenario: Nothing in the estate quotes the vectors
    Given an estate where no file pins them
    When copies are discovered
    Then it says it measured nothing
    Because four implementations are supposed to pin these, so finding none
      means the discovery broke or they all went away, and both need a person

  @fires:c6.canonical-gone
  Scenario: The pinned vector file is unusable
    Given the canonical vector file missing or unreadable
    When the estate is read
    Then it says so
    Because four implementations claim to reproduce it and none of them can
      be checked while it is gone
