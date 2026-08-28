# language: en

Feature: The event registry and what the producers emit, in both directions

  @measured 2026-08-06
  """
  The registry said idryx emits seven types. idryx has no event writer at all,
  in any file: its detections leave by OTLP and by Slack. A consumer that
  built a handler for one of those seven would have waited forever, and one
  downstream product had already shipped the operator-facing description for
  two of them.
  """

  The reverse direction is the more valuable one and nothing anywhere checks
  it: genaryx appends console_command lines under a source the registry has no
  row for at all. A source nobody registered is a producer no consumer knows
  to expect.

  @fires:c4.unregistered-source
  Scenario: A producer emits under a source the registry does not have
    Given a repository writing events with a source
    And no row for that source in the registry
    When the estate is read
    Then it is refused, naming the site and the types
    Because a consumer cannot subscribe to a producer it has never heard of

  @fires:c4.unregistered-type
  Scenario: A producer emits types its own row does not list
    Given a registered source
    And emit sites producing types the row does not name
    When the two are compared
    Then it is refused, listing the extra types

  @fires:c4.registered-type-not-emitted
  Scenario: The registry lists a type nothing produces
    Given a row naming types
    And no emit site in that repository producing some of them
    When the two are compared
    Then it is refused, listing them
    Because a consumer that builds a handler for one of those waits forever

  @fires:c4.registered-source-silent
  Scenario: A registered source has no readable producer at all
    Given a row in the registry
    And no producer for it readable in this run
    When the estate is read
    Then it is refused
    Because a row is a statement about what is written today

  @fires:c4.reserved-source-emits
  Scenario: A source recorded as reserved has an event-writing path
    Given a row marked reserved and not emitted today
    And a repository with a writer
    When the estate is read
    Then it is refused
    Because reserved is a claim about the present, and a writer contradicts it

  @fires:c4.producer-undeclared
  Scenario: A repository constructs an event writer and nothing compares it
    Given a repository calling the chained-writer constructor outside tests
    And no declaration of it among the producers this check reads
    When the estate is read
    Then it is refused
    Because every type that repository emits is currently unchecked against
      the registry, which is the state this gate exists to end

  @fires:c4.writer-anchor-gone
  Scenario: The anchor that identifies a producer stops matching
    Given a producer file that no longer contains the writer construct
    When its types are read
    Then it is refused, naming the anchor
    Because the types below it were read from a file that may no longer emit,
      and a pattern that matches nothing returns a set that agrees with
      everything

  @fires:c4.writer-file-gone
  Scenario: A recorded producer file is not there
    Given a repository recorded as writing events from a path
    And no file at that path
    When the estate is read
    Then it says so
    Because the producer moving and the producer stopping need different
      fixes

  @fires:c4.producer-unreadable
  Scenario: A producer cannot be parsed
    Given a producer whose types could not be read
    When the comparison is attempted
    Then it says so
    Because a producer this check cannot parse is a hole, not a pass

  @fires:c4.registry-unparsed
  Scenario: The registry itself cannot be parsed
    Given a registry section that does not read as a table
    When the estate is read
    Then it says so
    Because both directions of this comparison rest on it

  @fires:c4.reserved-unverifiable
  Scenario: A reserved row cannot be checked
    Given a row marked reserved
    And the repository behind it unreadable
    When the claim is checked
    Then it says so rather than accepting the claim
