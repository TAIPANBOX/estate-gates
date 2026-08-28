# language: en

Feature: The delegation mapping produces one chain in every language

  @measured 2026-08-26
  """
  Two mistakes are available and both were made in the hour the mapping was
  first written. The direction: reverse it wrongly and the record says the
  root delegated to nobody and the newest agent authorised the whole chain.
  The head: the token keeps the subject OUT of the actor list, so the mapping
  is the subject plus the reversed actors. Miss that and the chain is written
  WITH THE HUMAN MISSING FROM IT. Every token still verifies. Nothing
  downstream can tell.
  """

  This is the one place in the estate where a mistake produces something that
  verifies perfectly and asserts the opposite of what happened. A signature is
  over the claims; it says nothing about whether the reader turned them into
  the right list.

  @fires:c10.mapping-disagrees-across-languages
  Scenario: Two implementations map one token to two different chains
    Given a Go implementation and a Rust one, neither able to see the other
    And each holding its expected chain as a literal
    When the two literals are compared
    Then a disagreement is refused, printing both chains
    Because both suites pass on their own copy, and the estate would produce
      two different records of the same delegation

  @fires:c10.vector-has-no-human-at-its-root
  Scenario: The pinned vector is not rooted at a human
    Given a vector whose first principal is an agent
    When it is read
    Then it is refused
    Because the mapping's worst failure writes the chain with the human
      missing from it, and a vector rooted at an agent cannot catch it

  @fires:c10.vector-too-short
  Scenario: The vector is too short to show direction
    Given an implementation asserting fewer than a subject and two actors
    When the vector is read
    Then it is refused, printing how many it found
    Because a shorter one cannot show a direction or a missing head, which
      are the only two failures this check exists for

  @fires:c10.no-assertion-to-read
  Scenario: The test makes no assertion this check can anchor on
    Given an implementation whose expected chain is not stated as a literal
    When it is read
    Then it is refused
    Because the principals found could be the token's rather than the
      expected chain's, and comparing the input to itself agrees always

  @fires:c10.no-implementation-to-read
  Scenario: An implementation is gone
    Given a repository with no file holding the mapping function
    When it is looked for at its recorded path and then across the repository
    Then it is refused
    Because a MOVED implementation is found by that search, so this finding
      means deleted, and a comparison with one side missing agrees with itself

  @fires:c10.no-vector-to-read
  Scenario: The implementation is there and asserts no vector
    Given the mapping present with no vector beside it
    When the estate is read
    Then it is refused
    Because the mapping's own vector is then not being asserted anywhere this
      gate can see
