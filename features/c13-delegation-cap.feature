# language: en

Feature: The delegation depth cap, from every side, reduced to one number

  @measured 2026-08-27
  """
  The SPEC reads "Maximum chain depth is 32 entries", and the chain's root,
  usually a human, is one of those entries. The producers build the chain out
  of a token where the subject is deliberately NOT an actor. Two quantities,
  one sentence, and every side of the estate was free to decide which one the
  sentence meant.

  Measured against a real emitted line: two producers bounded the ACTOR list
  at 32 and then prepended the subject, while the envelope schemas, the chain
  validator and the conformance tool all bound the CHAIN at 32. A token with
  32 actors verified at the door and every record it produced was refused:

      maxItems: got 33, want 32
      chain: exceeds max depth: 33 entries, max 32

  Every number in the estate read 32. Every repository was internally
  consistent and every suite was green. The disagreement was not in a value,
  it was in the UNIT, and no repository could see it.
  """

  @fires:c13.entry-cap-differs
  Scenario: A constant caps the chain at a different number than the SPEC
    Given a cap counted in entries
    And a SPEC that caps it elsewhere
    When the two are compared
    Then a difference is refused, naming both

  @fires:c13.actor-cap-differs
  Scenario: A cap on actors leaves room for a different chain length
    Given a constant bounding the actor list
    When the room it leaves is compared with the SPEC's chain cap
    Then a difference is refused
    Because the subject is prepended after the bound is applied, so an actor
      cap equal to the entries cap accepts a chain one longer than the SPEC

  @fires:c13.actor-cap-retyped
  Scenario: The actor cap is a second literal rather than derived
    Given an actor cap written as its own number beside the entries cap
    When the estate is read
    Then it is refused
    Because the two numbers are one rule, and a second literal agrees today
      and drifts on the day one of them is edited

  @fires:c13.no-actor-cap
  Scenario: A producer builds the chain and counts no actors at all
    Given a producer assembling the chain from an actor claim
    And nothing bounding the actor count
    When the estate is read
    Then it is refused
    Because the bound belongs to the assembled chain, and a producer with no
      count emits records the consumers refuse

  @fires:c13.schema-cap-differs
  Scenario: A consumer schema bounds the chain at a different number
    Given a schema declaring the chain member with a maximum
    And a SPEC capping it elsewhere
    When the two are compared
    Then a difference is refused

  @fires:c13.schema-unbounded
  Scenario: A consumer schema declares the chain with no maximum
    Given a schema with the member and no bound on it
    When the estate is read
    Then it is refused
    Because that consumer accepts a chain the SPEC forbids, and the refusal
      would then happen somewhere else or not at all

  @fires:c13.cap-unparsed
  Scenario: A cap this check cannot evaluate
    Given a cap constant set to an expression rather than a number
    When it is read
    Then it is refused, printing what it found
    Because a bound it cannot read is one it is not comparing, and reporting
      agreement on an unread number is the failure this repository exists to
      prevent

  @fires:c13.spec-unit-unknown
  Scenario: The SPEC sentence stops counting in the unit this check knows
    Given a cap stated in some other unit
    When the sentence is parsed
    Then it is refused
    Because the unit is the whole of what this check holds: an estate that
      read one sentence two ways emitted records nothing would accept

  @fires:c13.spec-cap-gone
  Scenario: The SPEC sentence is gone
    Given no cap sentence to parse
    When the estate is read
    Then it says so
    Because every number below would be compared against nothing

  @fires:c13.no-code-caps
  Scenario: No cap constant is found anywhere
    Given an estate where no chain or delegation path declares one
    When the producers are read
    Then it says it measured nothing
    Because the producers are the side this check exists for, and finding
      none of them is an anchor that stopped matching, not an estate that
      agrees

  @fires:c13.no-schema-bounds
  Scenario: No schema declares the chain member
    Given an estate where no schema bounds it
    When the consumers are read
    Then it says it measured nothing
    Because the member is what the SPEC bounds, and a search that finds none
      of it has stopped reading rather than found agreement

  @fires:c13.no-mapping-found
  Scenario: No file declares the actor claim
    Given no file under a chain or delegation path naming it
    When the meeting point of the two units is looked for
    Then it says it measured nothing
    Because that is the only place the off-by-one can live, and an anchor
      that matches nothing has stopped looking for it

  @fires:c13.schema-search-failed
  Scenario: The schema search could not run
    Given a search over the schemas that failed
    When the consumers are read
    Then it says so

  @fires:c13.source-listing-failed
  Scenario: The source listing could not run
    Given a listing of candidate files that failed
    When the producers are read
    Then it says so
