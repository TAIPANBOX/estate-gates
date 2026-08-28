# language: en

Feature: Three deployments of one product, and every difference written down

  @yurii 2026-08-27
  """
  це треба все робити як один спільний продукт, просто з можливістю
  встановлення за окремими функціоналами, який потрібен користувачам
  """

  @measured 2026-08-26
  """
  stack-up, stack-single and stack-k8s disagreed on which governance routines
  run, on the severity floor the notifier uses, and on which components come
  up at all. Some of those differences are deliberate and good. None of them
  was written down anywhere a reader could find, so an operator moving between
  two of them met the difference as a surprise, and nobody could tell a
  decision from an omission.
  """

  This check does not decide which divergences are acceptable. It computes
  every divergence and fails on any one the expectations file does not record
  with a reason. Recording one is cheap and converts an unstated difference
  into a decision somebody signed a date to.

  @fires:c5.unrecorded-divergence
  Scenario: Two deployments differ and nothing says why
    Given a setting with different values across deployments
    And no entry recording it
    When the estate is read
    Then it is refused, naming the key and where to record it
    Because a divergence with a reason beside it is a decision, and one
      without is indistinguishable from an omission

  @fires:c5.stale-expectation
  Scenario: A recorded allowance outlives the divergence it excused
    Given an entry for a divergence that no longer exists
    When the estate is read
    Then it is refused
    Because a file of stale allowances is how a gate becomes a formality,
      and this property is borrowed from bank-in-a-box, where a mutation left
      behind for a deleted check fails the script

  @fires:c5.runs-undeclared
  Scenario: A registry entry does not say what it runs
    Given a repository entry with no runs field
    When coverage is computed
    Then it is refused, saying where to add it
    Because an empty list is a valid and common answer and no answer is not:
      the field is how this check discovers its own subjects instead of
      holding a hand-written list, which is the defect shape this estate
      found nine times in two days

  @fires:c5.service-unmapped
  Scenario: A deployment brings up a component this check cannot name
    Given a launcher starting a component under a local name
    And no mapping from that name to a kind
    When the deployments are compared
    Then it is refused, naming the component
    Because an unmapped name silently drops out of the comparison, and a
      comparison missing a member reports parity it never established

  @fires:c5.routine-unmapped
  Scenario: A deployment installs a routine this check cannot name
    Given a routine installed under a local name
    And no mapping for it
    When the deployments are compared
    Then it is refused
    Because it cannot say which governance routine that is, or whether it is
      a sixth

  @fires:c5.unread-scheduler
  Scenario: A deployment ships no readable routine and mentions a scheduler
    Given a deployment this check reads no routine from
    And lines in it that mention a scheduler
    When the estate is read
    Then it is refused, printing those lines
    Because either it schedules something this check is blind to, or the
      mention is stale, and the two need different fixes

  @fires:c5.too-few-deployments
  Scenario: Fewer than two deployments could be read
    Given only one deployment readable
    When parity is computed
    Then it says it measured nothing
    Because parity between fewer than two is not a thing that exists

  @fires:c5.deployment-unreadable
  Scenario: A deployment could not be read
    Given a deployment the run could not open
    When the estate is read
    Then it says so
    Because it was not compared at all, which is not the same as it agreeing

  @fires:c5.expectations-gone
  Scenario: The expectations file is missing
    Given no expectations file
    When divergences are judged
    Then it says so
    Because with it gone every divergence would read as unrecorded, and the
      check would be loudest exactly when it knows least
