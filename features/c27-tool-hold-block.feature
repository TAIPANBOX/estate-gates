# language: en

Feature: The tool hold is one block in both stacks

  @decided 2026-11-07
  """
  A tool call nothing grants is held for a person on a default install of either
  stack, a model call passes, and only an explicit grant lifts the hold. Each stack
  writes that block with a shell function of its own and each stack's gate holds its
  own copy, so only this repository can see the two side by side.
  """

  stack-single's install.sh and stack-k8s's lib/tool-hold.sh are read at the ref the
  run is given. The function tool_hold_block is compared line by line, the condition
  around the web grant included, and a shell comment is not part of it. The begin
  marker may name its own file and invariant number and nothing else may differ.
  tool_hold_sources is compared by the identity lists it can print.

  @fires:c27.block-differs
  Scenario: A rule of one stack is not the rule of the other
    Given stack-k8s narrows the floor, or one stack carries a seed the other has not
    When the two blocks are read
    Then the finding is red, naming both files and both lines
    Because an agent would work on a box and wait for a person on a cluster, with both suites green

  @fires:c27.sources-differ
  Scenario: The two bodies agree and the grants they render do not
    Given tool_hold_sources prints an identity list in one stack and not in the other
    When the two functions are read
    Then the finding is red, naming both lists
    Because the body says $(tool_hold_sources), so one body renders two different grants

  @fires:c27.no-floor
  Scenario: The stacks agree on a floor that holds nothing
    Given both stacks write when_no_grant: allow
    When the two blocks are read
    Then the finding is red, naming both files
    Because two copies of nothing agree

  @fires:c27.marker-missing
  Scenario: A block no longer carries the line a stack finds it by
    Given a stack rewords its begin marker
    When the block is read
    Then the finding is red, naming the file and the shape it wanted
    Because a block nothing can find is one a stack cannot render or take out

  @fires:c27.anchor-missing
  Scenario: A function is not where this check looks
    Given tool_hold_block or tool_hold_sources is renamed, or prints no list this check can read
    When the file is read
    Then the check says it measured nothing about that stack
    Because two absent functions would read as agreement

  @fires:c27.file-missing
  Scenario: A file this check reads is gone
    Given lib/tool-hold.sh or install.sh is not at the ref
    When the file is read
    Then the check names what vanished
    Because a missing subject is never a pass
