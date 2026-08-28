# language: en

Feature: Nothing tells the decision point a chain was proved unless it verified one

  @measured 2026-08-25
  """
  wardryx decides on chain_proven, and its own comment states the trust
  boundary plainly: a caller that lies about this is believed, and that is not
  a weakness of the field, it is where the boundary is. The decision point
  cannot tell a verified true from an asserted one. Nobody can, from inside
  wardryx. It is visible only to something holding wardryx and every producer
  open at once.
  """

  The upgrade is the dangerous half. A downgrade makes a policy fire that
  should not have; an upgrade makes one stay silent, and a rule that denies
  unproven chains staying silent looks exactly like an estate where every
  chain is proved.

  @fires:c11.asserted-not-verified
  Scenario: A file sets the field true and reaches no verifier
    Given non-test code setting chain_proven to a literal true
    And no delegation verifier reached anywhere in that file
    When the estate is read
    Then it is refused, naming the file
    Because the decision point believes this field, and the check has to live
      on this side of the boundary since nothing inside wardryx can see it

  @fires:c11.no-producer
  Scenario: Nothing in the estate mentions the field outside tests
    Given no enforcement point setting it
    When the estate is read
    Then it says it measured nothing
    And it names the two ways that happens, because they need different
      people: either no enforcement point has been built yet, or the anchor
      this check reads stopped matching
