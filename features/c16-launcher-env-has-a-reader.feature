# language: en

Feature: A launcher hands a variable to something that reads it

  @yurii 2026-08-31
  """
  додай гейт, який звіряє змінні лаунчера з тим, що читає бінарник
  """

  He asked for this the day one of its findings cost a database. stack-single
  generated a correct DSN, declared depends_on with condition: service_healthy,
  WAITED for policy-db to come up, and handed the value over as WARDRYX_DSN.
  wardryx reads WARDRYX_DB and has never read the other name. So the database
  was provisioned, waited on and never used, which left policy and approvals in
  memory: a restart dropped every console-written policy and unfroze the fleet
  while the console still showed it stopped.

  Writing the check found a second one nobody was looking for. stack-k8s sets
  TOKENFUSE_CLOUD_EVENTS_PATH into a container by configMapKeyRef; that name
  appears nowhere in tokenfuse, whose cloud reads TOKENFUSE_CLOUD_REPLAY_EVENTS,
  which no launcher sets at all.

  THE QUIET KIND. Nothing is misspelled, nothing errors, the value is correct,
  the dependency is healthy, and the service starts and answers. A key with no
  reader is a wire that was never connected while every signal around it says
  the opposite. C5 cannot see it, because C5 compares the launchers against
  each other and three launchers can agree perfectly on a variable nobody
  reads.

  BOTH SIDES COME FROM THE REPOSITORIES. The answer is every name under an env
  block in a components.json, each proved by its own repository against its own
  source. The subjects are what the launchers deliver, by forms read off the
  launchers themselves.

  BINDING. Each scenario names a finding id, because in this repository the id
  is the unit of proof: selftest.py plants a fault per id and requires the
  check to go red on it.

  # ------------------------------------------------- the comparison, both ways

  @fires:c16.no-reader
  Scenario: A launcher hands over a name no binary reads
    Given a launcher that delivers an environment variable to a service
    And no repository in the estate declares reading that name
    When the estate is read
    Then it is refused, naming the variable and the file that sets it
    Because the value is correct and the service starts, so nothing else in the
      system will ever mention it, and the wiring it was meant to do is simply
      not happening

  @fires:c16.no-reader
  Scenario: A repository stops declaring the variable a launcher hands it
    Given a launcher that delivers an environment variable, unchanged
    And the repository that used to declare reading it no longer does
    When the estate is read
    Then it is refused just as loudly
    Because a comparison that only watched the launcher would stay green while
      the two sides drifted apart from the other end

  # ------------------------------------- and the ways it can measure nothing

  @fires:c16.declarations
  Scenario: Not one repository says what it reads
    Given an estate where no components.json carries an env block
    When the estate is read
    Then the check refuses rather than reporting agreement
    Because with no answer to compare against, every launcher variable would
      pass, and a check that passes everything is worse than no check

  @fires:c16.nothing-delivered
  Scenario: No launcher appears to hand over anything
    Given three launchers that install this estate
    And not one service-prefixed variable found in any of them
    When the estate is read
    Then the check refuses and says the delivery forms have stopped matching
    Because launchers that install a stack necessarily configure it, so an
      empty result means this check stopped seeing rather than that there is
      nothing to see

  @fires:c16.launcher-unreadable
  Scenario: The launcher whose environment is read is gone
    Given a launcher file the check expects and cannot open
    When the estate is read
    Then the check refuses, naming the file
    Because a launcher that vanished and a launcher that delivers nothing look
      identical in the result and mean opposite things

  @fires:c16.manifest-unreadable
  Scenario: A declaring manifest is not readable as JSON
    Given a repository whose components.json cannot be parsed
    And another repository whose declarations are still readable
    When the estate is read
    Then it is refused for that repository by name
    Because the answer is now missing whatever that repository reads, and a
      launcher variable it alone consumes would be reported as unread
