# language: en

Feature: Every architecture file is current against its repository

  @decided 2026-09-09
  """
  The owner asked for one place per service that says how it is built and
  why, that the agent reads before touching the code and updates after every
  change, checked against the code as it stands. The wiki had that role and
  nothing made it red when it fell behind: service notes lagged the code by
  three days to eight weeks. This gate is what makes falling behind visible.
  """

  @fires:c18.expectations-unreadable
  Scenario: The pending list cannot be read
    Given a pending list that is absent or not JSON
    When the record is read
    Then it says so and calls nothing pending
    Because a service silently treated as pending is one nobody has to write

  @fires:c18.no-files
  Scenario: The record has no service file at all
    Given an architecture record with no services/*.md
    When the estate is read
    Then it says it measured nothing
    Because agreement over an empty set is the failure this suite exists to end

  @fires:c18.file-missing
  Scenario: A service has no file and no pending entry
    Given a registry entry with neither a service file nor a dated gap
    Then it is refused, naming the service
    Because a gap that is not recorded is a gap nobody has agreed to

  @fires:c18.stale-pending
  Scenario: A pending entry outlives its file
    Given a service file that exists while the pending list still names it
    Then it is refused, naming the entry to remove
    Because a pending list with written files in it is a graveyard

  @fires:c18.frontmatter
  Scenario: The file has no usable frontmatter
    Given a service file without verified_at
    Then it is refused, naming the key
    Because a file that says nothing about which commit it describes cannot be checked

  @fires:c18.verified-at-unknown
  Scenario: verified_at is not a commit the repository has
    Given a verified_at the repository has never seen
    Then it is refused
    Because an unknown commit is not zero drift

  @fires:c18.verified-at-unreachable
  Scenario: verified_at is on a side branch
    Given a verified_at that main does not contain
    Then it is refused
    Because a squash merge leaves branch commits behind, and the file must name main

  @fires:c18.stale
  Scenario: Code landed after the file was checked
    Given a code commit on main after verified_at
    When the estate is read
    Then it is refused, listing the commits
    Because that list is exactly what the agent has to read before trusting the file

  @fires:c18.dangling-gate
  Scenario: A decision claims a gate that does not exist
    Given a decisions row held by a script the repository does not have
    Then it is refused, naming the script
    Because a decision held by a missing gate is held by nothing
