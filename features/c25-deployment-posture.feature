# language: en

Feature: Each launcher keeps the security postures it sets today

  @decided 2026-10-17
  """
  The agent-security review of 2026-10-17 decided to close its findings, starting
  with the defaults the products ship and the launchers that turn them on. A
  launcher that stops setting one of those postures must be seen by this
  repository, not discovered by an incident.
  """

  The three launchers are read at the ref the run is given: stack-single (its
  compose file and installer), stack-k8s (its manifests and installer) and stack-up
  (its up.sh). A posture is judged on the text a launcher sets. A posture a
  launcher does not hold is red unless expectations/deployment-posture.json records
  it with a reason. An anchor that matches nothing, and a file that is gone, are
  red, naming what vanished.

  @fires:c25.client-keys
  Scenario: A launcher lets the metered door admit a caller with no client key
    Given a launcher sets no client keys, or sets them with an empty default
    When the launcher is read
    Then the posture is red, naming the launcher and the variable
    Because with no key the gateway admits every caller and trusts the agent id it is given

  @fires:c25.identity-strict
  Scenario: A launcher does not hold the identity binding strict
    Given a launcher sets the gateway's identity strictness to anything but enforce
    When the launcher is read
    Then the posture is red, naming the launcher and the line it came from
    Because a key that may speak as any agent lets one agent speak as another

  @fires:c25.firewall
  Scenario: A launcher defaults the agent firewall to shadow
    Given a launcher's default for the agent firewall is not enforce
    When the launcher is read
    Then the posture is red, naming the launcher and the line
    Because a firewall that only records what it would have refused refuses nothing

  @fires:c25.pep-mode
  Scenario: A launcher runs the gateway's policy-plane check in shadow
    Given a launcher sets the gateway's wardryx mode to anything but enforce
    When the launcher is read
    Then the posture is red, naming the launcher and the line
    Because a policy decision that is not enforced is a log line with extra steps

  @fires:c25.pep-failmode
  Scenario: A launcher lets the gateway fail open when wardryx is silent
    Given a launcher sets the gateway's wardryx fail mode to anything but closed
    When the launcher is read
    Then the posture is red, naming the launcher and the line
    Because an enforcement point that allows when its policy plane is silent is not one

  @fires:c25.pep-key-role
  Scenario: A launcher gives the gateway a policy-plane key that is not a pep
    Given a launcher's installer mints the gateway's wardryx secret as a viewer
    And a launcher hands wardryx the built-in devkey literal
    When the launcher is read
    Then the posture is red, naming the launcher and the line
    Because a viewer cannot decide, and the devkey is a credential anybody can read

  @fires:c25.declassify-key
  Scenario: A launcher lets the declassify endpoint run with no key
    Given a launcher sets the declassify key optional, or mints it and does not refuse an empty one
    When the launcher is read
    Then the posture is red, naming the launcher and the line
    Because an open declassify endpoint clears a run's taint label for anybody who reaches the port

  @fires:c25.broker-dlp
  Scenario: A launcher's MCP broker does not block secrets in tool arguments
    Given a launcher sets the broker's DLP to anything but block, or sets none
    When the launcher is read
    Then the posture is red, naming the launcher and the line
    Because a secret that reaches a tool call's arguments has left the box

  @fires:c25.broker-scan
  Scenario: A launcher's MCP broker warns where it should block
    Given a launcher sets the broker's scan to anything but block, or sets none
    When the launcher is read
    Then the posture is red, naming the launcher and the line
    Because a scan that only warns lets the call through

  @fires:c25.broker-pep-mode
  Scenario: A launcher's MCP broker does not enforce wardryx's answer
    Given a launcher hands the broker a wardryx mode other than enforce
    When the launcher is read
    Then the posture is red, naming the launcher and the line
    Because a broker that asks the policy plane and ignores the answer asks for nothing

  @fires:c25.broker-pep-failmode
  Scenario: A launcher's MCP broker fails open when wardryx is silent
    Given a launcher hands the broker a wardryx fail mode other than closed, or none
    When the launcher is read
    Then the posture is red, naming the launcher and the line
    Because a broker with no answer from the policy plane must refuse the call

  @fires:c25.admin-keys
  Scenario: A launcher leaves the gateway's admin routes open
    Given a launcher sets the admin key optional, or mints it and does not refuse an empty one
    When the launcher is read
    Then the posture is red, naming the launcher and the line
    Because the kill switch and the run listing are on those routes

  @fires:c25.launcher-missing
  Scenario: A launcher file this check reads is gone
    Given a file the check reads is missing from a launcher
    When the launcher is read
    Then the launcher is red, naming the file that vanished
    Because a check that cannot see a launcher has measured nothing about it

  @fires:c25.anchor-missing
  Scenario: The service, Deployment, start or role line a posture is read from is gone
    Given a launcher renames the gateway service, drops the else of its wardryx-wired start, or stops writing the gateway's role
    When the launcher is read
    Then the anchor is red, naming what matched nothing
    Because an anchor that matches nothing is a missing subject and never a pass

  @fires:c25.expectations-missing
  Scenario: The expectations file is gone
    Given expectations/deployment-posture.json is not there
    When the launcher postures are read
    Then the run is red, saying no divergence can be excused
    Because without the record every gap reads as a finding with nothing recorded beside it

  @fires:c25.expectation-unreasoned
  Scenario: A recorded divergence has no reason
    Given a divergence is recorded with an empty reason or no provenance
    When the expectations are read
    Then the entry is red
    Because an exception with no reason is a gap nobody wrote down

  @fires:c25.expectation-stale
  Scenario: A recorded divergence excuses nothing any more
    Given a divergence is recorded for a posture the launcher now holds, or for a name no posture carries
    When the expectations are read
    Then the entry is red and must be removed
    Because a record that excuses nothing would become a graveyard of old decisions
