# language: en

Feature: An optional add-on stays off the path every agent request takes

  @decided 2026-09-26
  """
  An optional add-on, typryx first, is integrated beside the core and never
  inside it. The repositories every agent request passes through, the money
  plane and the policy plane, carry no code, configuration or documentation
  naming the add-on, so a stack without it runs exactly as before and a slow
  or failed add-on cannot slow or fail a request. The add-on reaches the rest
  of the stack through the shared event bus by default; any direct link a
  consumer adds is optional, off by default, and fails open.
  """

  Subjects come from estate.json: repositories marked "addon": true, and
  repositories marked "request_path": true. An add-on is named by its
  registry key and every component its runs field lists, in any case.
  Launchers are not request-path repositories: they are where an add-on is
  wired, by configuration.

  @fires:c22.core-names-an-addon
  Scenario: A request-path repository names an add-on
    Given tokenfuse or wardryx has a tracked file naming typryx, in any case
    When the estate is read
    Then it is refused, naming each file and line
    Because a core that names the add-on is a core growing a seam for it

  @fires:c22.no-addons
  Scenario: The registry marks no add-on
    Given no estate.json entry carries "addon": true
    When the estate is read
    Then the gate says it measured nothing rather than reporting agreement

  @fires:c22.no-request-path
  Scenario: The registry marks no request-path repository
    Given no estate.json entry carries "request_path": true
    When the estate is read
    Then the gate says it measured nothing rather than reporting agreement
