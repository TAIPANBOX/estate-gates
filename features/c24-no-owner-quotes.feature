# language: en

Feature: No public repository quotes the owner or names him as the one who decided

  @decided 2026-10-13
  """
  Every public repository is free of quotations of the owner and of the old
  provenance marker that carried his first name, and a gate keeps it so. A
  decision the owner made stays recorded, as a date and a paraphrase in English.
  His name remains allowed as copyright holder, author or maintainer.
  """

  Subjects come from estate.json: every repository that records a public GitHub
  remote. A private repository is skipped, and the output says so. The output
  names each file and line and never prints the line's text, because a CI log
  of a public repository is public too.

  @fires:c24.marker
  Scenario: A public repository carries the old provenance marker
    Given a tracked file of a public repository carries the owner's first name
      after an at-sign
    When the estate is read
    Then it is refused, naming the file and the line
    Because the marker is the form a recorded decision took before it was paraphrased

  @fires:c24.guillemet
  Scenario: A quotation in guillemets, in the owner's language, is in a public repository
    Given a tracked line carries guillemets and Cyrillic together
    When the estate is read
    Then it is refused, naming the file and the line
    Because a quotation of the owner's words is what a public reader must not find

  @fires:c24.cyrillic-prose
  Scenario: Ukrainian prose sits outside a string literal in a public repository
    Given a tracked file is prose, or a code file with Cyrillic outside a string literal or a comment
    When the estate is read
    Then it is refused, naming the file and the line
    And a Cyrillic string literal in a Go or Python test passes, because hostile input needs it
    Because a decision in a public repository is paraphrased in English

  @fires:c24.owner-named
  Scenario: The owner is named as the one who said, asked, decided or found something
    Given a tracked line names the owner's first name, capitalised
    When the line does not say copyright, author or maintainer
    Then it is refused, naming the file and the line
    And the same name on an authorship line passes
    Because naming who decided is an attribution a public reader can quote

  @fires:c24.no-subjects
  Scenario: No repository records a public remote
    Given estate.json records no public GitHub remote for any repository
    When the estate is read
    Then the gate says it measured nothing rather than reporting agreement

  @fires:c24.file-unreadable
  Scenario: A tracked file cannot be read
    Given a file git tracks is missing from disk
    When the estate is read
    Then the file is named as unread, and its text is not counted as clean

  @fires:c24.nothing-scanned
  Scenario: A public repository tracks no file at all
    Given a public repository in which git tracks no file
    When the estate is read
    Then the gate says that repository had nothing read in it, rather than passing it
