# language: en

Feature: A repository says what it contributes, and the estate reads it

  @yurii 2026-08-27
  """
  це треба все робити як один спільний продукт, просто з можливістю
  встановлення за окремими функціоналами, який потрібен користувачам
  """

  One product installed by function needs one question answered per piece:
  what is this, and who installs it. Until 2026-08-28 that answer lived in six
  hand-written lists, and vouchryx spent nineteen hours installable by nothing
  without a single check going red.

  The split this feature describes: the repository DECLARES and proves what it
  can, in its own CI where the toolchain is; this repository READS across all
  of them and asks the questions no single repository can ask about itself.

  A component that was FORGOTTEN is invisible from outside by construction. No
  central file can contradict an empty list, which is why the declaration has
  to come from the repository and why "checked" has to mean checked THERE.

  BINDING. Scenarios below name a finding id rather than a function, because in
  this repository the finding id is the unit of proof: selftest.py plants a
  fault per id and requires the check to go red on it. So a bound scenario is
  transitively proved to be able to fail, which a function name alone is not.
  scripts/features-are-bound.sh holds all three directions.

  # ------------------------------------------------ the two files must agree

  @fires:c15.registry-names-what-the-repo-does-not
  Scenario: The registry and the repository disagree about one fact
    Given a repository whose manifest declares what it contributes
    And a registry entry that lists a component the manifest does not
    When the estate is read
    Then it is refused, naming the component and both files
    Because two files disagreeing about one fact is this repository's subject,
      and whichever is right, a reader has no way to tell which

  @fires:c15.unknown-schema
  Scenario: A manifest written to a contract this reader does not have
    Given a manifest whose schema is not taipanbox.dev/components/v1
    When the estate is read
    Then it is refused rather than read on a guess
    Because a reader that guesses at an unknown contract reports agreement it
      never established

  @fires:c15.manifest-unreadable
  Scenario: A manifest that is not JSON
    Given a manifest that does not parse
    When the estate is read
    Then it is refused, naming the repository and the parse error
    Because a file too broken to read is not a repository with nothing to say

  # ------------------------- a claim nobody can check must carry its own why

  @fires:c15.declared-without-a-reason
  Scenario: A declared claim arrives with no reason
    Given a component with a declared entry and no why
    When the estate is read
    Then it is refused
    Because declared means nobody can verify this, and a claim wearing the
      costume of a decision is exactly what the two buckets exist to prevent

  @fires:c15.manifest-declares-nothing
  Scenario: A manifest that declares no components at all
    Given a repository carrying a manifest with an empty component list
    When the estate is read
    Then it is refused
    Because adopting the file and saying nothing in it reads as adoption from
      every angle except the only one that matters

  # ------------------------------------- installed by function, or by nobody

  @fires:c15.nothing-installs-it
  Scenario: A service nothing installs, found by a run rather than by hand
    Given a component declared as a service or a daemon
    And no launcher manifest that installs it
    And nothing recording why that is intended
    When the estate is read
    Then it is refused, naming the component
    Because this is the vouchryx failure, and it was found by a person the
      first time and by this check the second: trailryx-ingest, on its first
      run, in a repository whose own suite was green

  @fires:c15.probe-disagrees
  Scenario: A launcher polls a different health path than the component declares
    Given a component declaring the path its health is served on
    And a deployment polling a different path for it
    And nothing recording why they differ
    When the estate is read
    Then it is refused, naming both paths
    Because these are two facts in two repositories and nothing compared them
      until now: the install waits on a path the service never serves, and the
      only symptom is a timeout that reads as the service being slow

  # ---------------- a check whose subject is gone says so, and never reports OK

  @fires:c15.no-manifest-anywhere
  Scenario: Not one repository carries a manifest
    Given an estate where no repository has adopted the file
    When the estate is read
    Then it says it measured nothing, rather than reporting agreement
    Because agreement about nothing is the most convincing wrong answer this
      check could give, and adoption being incremental is the reason the empty
      case is reachable at all

  @fires:c15.no-service-to-judge
  Scenario: Not one component in the estate is a service or a daemon
    Given manifests that declare only tools and dev-tools
    When the question "is there a service nothing installs" is asked
    Then it says it measured nothing
    Because a tool nobody installs is not news, so with no service present the
      question has no subject and a pass would be an answer to nothing

  @fires:c15.no-launcher-manifest
  Scenario: No launcher declares what it installs
    Given an estate whose launchers carry no manifest
    When the question "is there a service nothing installs" is asked
    Then it says it measured nothing
    Because with nothing declaring installs, every service looks uninstalled
      and the check would be loudest exactly when it knows least

  @fires:c15.launchers-install-nothing
  Scenario: A launcher declares itself and installs nothing
    Given a launcher manifest that lists no installed component
    When the estate is read
    Then it says it measured nothing
    Because a launcher is the one kind of component defined by what it puts
      somewhere else, so one that installs nothing has not been described

  @fires:c15.probe-unreadable
  Scenario: The launcher whose probes are read is gone
    Given the file the health paths are read out of no longer exists
    When the estate is read
    Then it is refused
    Because the comparison silently stops comparing, and the check would report
      agreement between a manifest and a file it never opened

  @fires:c15.probe-anchor-matched-nothing
  Scenario: The launcher stops calling the function this check reads
    Given a launcher that no longer calls wait_health
    When the health paths are read out of it
    Then it is refused
    Because a pattern that matches nothing returns an empty set, and an empty
      set agrees with everything
