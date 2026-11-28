# language: en

Feature: No public README frames the work as not proven

  @decided 2026-11-27
  """
  What was built, modelled or run is stated as done. A README keeps a claim
  exactly as true as the run behind it, keeps a product limit as a fact about
  the product, and reports a failed run as what happened; it keeps no section
  whose job is to list what was not proven.
  """

  @fires:c28.gap-framing
  Scenario: A public README keeps a not-proven section or phrase
    Given a public repository whose README has a NOT PROVEN heading or says a run has not been run
    When the READMEs are read
    Then the line is named with its repository, file and number
    Because a gap list reads as the product's own description to anyone who opens the repository

  @fires:c28.no-subjects
  Scenario: No repository records a public remote
    Given an estate.json in which no repository records a public GitHub remote
    When the READMEs are read
    Then it says it measured nothing
    Because agreement over an empty set is the failure this suite exists to end
