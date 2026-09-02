# language: en

Feature: A tag-only workflow is exercised by a pull request first

  @measured 2026-09-02
  """
  A workflow gated on push.tags: v* runs for the first time, on every commit
  that ever reached it, the day somebody cuts a release. TokenFuse's binaries
  job failed on both Linux runners the first time v0.4.2 exercised its musl
  leg, on a step that had been wrong since the workflow was written: nothing
  had ever run it before that tag. The fix, TAIPANBOX/tokenfuse#251, added a
  pull_request trigger scoped to the workflow's own path and guarded every
  publishing job off that event. A survey of the estate found ten more
  workflows with the same shape; this gate's own discovery found two more
  than the survey did, because a hand-typed list is complete on the day it
  is written and a discovered one is not.
  """

  Both requirements are asked of every workflow whose on.push.tags matches
  v*, found by reading every repository estate.json names rather than by a
  list kept here. A file can fail either one alone or both together, and a
  fix to one does not excuse the other: a pull_request trigger added without
  guarding the publish jobs would make a pull request publish, and a guard
  added without the trigger leaves the workflow exactly as untested as
  before.

  # ------------------------------------------ requirement one: the trigger

  @fires:c17.no-pull-request-for-self
  Scenario: A tag-only workflow carries no escape hatch at all
    Given a workflow whose on.push.tags matches v*
    And it has no pull_request trigger anywhere in its on: block
    When the estate is read
    Then it is refused, naming the trigger the file has and the one it needs
    Because a workflow with no pull_request trigger is first exercised by the
      release itself, which is the one occasion a mistake in it is public

  @fires:c17.no-pull-request-for-self
  Scenario: A pull request trigger watches a different file
    Given a workflow whose on.push.tags matches v*
    And its pull_request trigger's paths name another file, not this one
    When the estate is read
    Then it is refused just as loudly
    Because a trigger that never fires on an edit to this file leaves the
      workflow exactly as untested as having no trigger at all

  # -------------------------------------- requirement two: the publish guard

  @fires:c17.publish-job-unguarded
  Scenario: A job that publishes carries no accepted guard
    Given a workflow with a working pull_request trigger of its own
    And one of its jobs publishes and carries no job-level if: guard
    When the estate is read
    Then that job is refused, naming what makes it a publisher and its guard
    Because a pull_request build that reaches an unguarded publishing job
      would publish from a fork's pull request rather than only build

  # ---------------------------------------------- measuring nothing at all

  @fires:c17.no-subjects
  Scenario: Every tag-triggered workflow is gone from the estate
    Given no repository estate.json names has a workflow matching push.tags: v*
    When the estate is read
    Then the check refuses rather than reporting agreement
    Because an estate with nothing left to check and an estate where every
      such workflow is correct print the same silence, and only the first
      one is true
