# language: en

Feature: Every consumer of the shared module is pinned to what the module is

  @measured 2026-07-28
  """
  idryx sat on agent-stack-go v0.3.0 while the module was at v0.5.1, and the
  whole delta was the tamper-evidence chain verifier idryx needed most.
  Nothing failed. Nothing could: no gate in any repository can see two
  repositories at once.
  """

  agent-stack-go is where the wire types live. A consumer a minor behind is not
  slightly behind, it is speaking a different contract while every document in
  the estate says there is one.

  @fires:c1.minor-behind
  Scenario: A consumer is a minor or more behind the module
    Given a repository requiring the shared module at an older minor
    When the estate is read
    Then it is refused, naming the consumer, its pin and the newest tag
    Because the module is pre-1.0, so a minor bump is where behaviour and
      breakage live, and two consumers a minor apart are two dialects

  @fires:c1.patch-behind
  Scenario: A consumer is a patch behind
    Given a repository one patch release behind the module
    When the estate is read
    Then it is refused, and the exit code does not soften for it
    Because the alternative was a warning that fails nothing, and a warning
      nothing enforces is a comment with an exit code: it accumulates,
      everyone learns to scroll past it, and the estate is back where it began

  @fires:c1.ahead-of-module
  Scenario: A pin no tag names
    Given a consumer pinned ahead of the module's newest tag
    When the estate is read
    Then it is refused
    Because a build that cannot be reproduced from a tag is not a release,
      and this is what a pseudo-version usually looks like from outside

  @fires:c1.unparseable-pin
  Scenario: A pin that is not a plain version tag
    Given a consumer whose require line names something other than vX.Y.Z
    When the estate is read
    Then it is refused, printing what it found
    Because a pin this check cannot compare is one it is not comparing, and
      saying nothing about it would read as agreement

  @fires:c1.replace-directive
  Scenario: A replace directive makes the pin unenforceable
    Given a consumer carrying a replace for the shared module
    When the estate is read
    Then it is refused
    Because the version it names is not the version it builds, and that is
      invisible to every other check in the estate

  @fires:c1.require-unparsed
  Scenario: The module is named and no require line can be read
    Given a go.mod that mentions the module with no parseable require
    When the pin is looked for
    Then it is refused, naming the anchor that stopped matching
    Because the fix is the anchor, and assuming the pin is fine is how a
      check quietly stops checking

  @fires:c1.no-consumers
  Scenario: Not one repository requires the shared module
    Given an estate where no go.mod names it
    When the consumers are counted
    Then it says it measured nothing
    Because the estate has at least six Go consumers, so finding none means
      this check read the wrong thing rather than that the estate is clean

  @fires:c1.no-tags
  Scenario: The module has no tags to compare against
    Given a module repository with no version tags
    When the newest tag is looked for
    Then it says it measured nothing
    Because every pin below would be compared against nothing

  @fires:c1.repo-unreadable
  Scenario: A consumer repository could not be read
    Given a repository the run could not open
    When the estate is read
    Then it says so rather than passing it
    Because an unread repository is not a clean one

  @fires:c1.gomod-vanished
  Scenario: A consumer's go.mod is gone
    Given a repository recorded as a consumer with no go.mod present
    When its pin is read
    Then it says so
    Because a consumer that stopped being one and a file that moved need
      different fixes, and neither is agreement
