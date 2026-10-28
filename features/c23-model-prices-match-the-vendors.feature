# language: en

Feature: Every built-in model price table matches the vendors' current prices

  @measured 2026-10-13
  """
  ./run-gates.py --mode ref --ref origin/main --only c23, against tokenfuse
  d3e1f65, verdryx bef9589 and costcrew e51de87, read against the vendors'
  live pages that day: the gateway's book had no row for Claude Haiku 5.5, a
  current model at 0.10 / 0.50, so it billed it at the 15 / 75 fallback; its
  Sonnet 5.5 cache read was 0.20 where the page says 0.10; it had no row for
  any of OpenAI's three latest models; it priced Gemini 3.6, 3.7 and 3.8 Flash
  at their 2027 standard rate while the introductory rate was in force.
  costcrew carried Sonnet 5 at 3 / 15 and Opus 5 at 15 / 75 against 2 / 10 and
  5 / 25. Every repository was internally consistent and every suite green.
  """

  Subjects come from estate.json: every repository whose entry declares a
  price_table, with its path, its format, and whether it must price every
  current model. Prices are read live, with no key, from Anthropic's, OpenAI's
  and Google Vertex AI's pricing pages. A row billed through OpenRouter is
  held to the providers OpenRouter routes that model to, never to its model
  list, whose one price switches provider; for the rest OpenRouter is a
  secondary signal, where the vendor's page wins every disagreement.

  @fires:c23.price-differs
  Scenario: A row billed through OpenRouter matches no provider
    Given a table prices a model billed through OpenRouter
    When no provider OpenRouter routes it to charges exactly that price, every component from the same provider
    Then it is refused, listing every provider's price today
    And a row that equals one live provider's price exactly passes, whichever provider the model list happens to show

  @fires:c23.no-endpoints
  Scenario: OpenRouter lists no provider for a model a row is billed through
    Given a table prices a model billed through OpenRouter
    When OpenRouter lists no provider with a price for it, or does not know the model
    Then it is refused, because a call billed through it has no price to be checked against

  @fires:c23.price-differs
  Scenario: A table's price disagrees with the vendor's page
    Given a row in a declared price table maps to a model on a vendor's page
    And one of its prices differs from the price in effect today by more than half a percent
    When the estate is read
    Then it is refused, naming the repository, the row, our price, the vendor's price and the page
    And it prints the row as it should read, in the table's own format

  @fires:c23.price-differs
  Scenario: A row's id names a regional endpoint
    Given a Bedrock profile id names a regional endpoint
    When the row carries the global list price
    Then it is refused, because a regional endpoint costs the premium the vendor's page states

  @fires:c23.price-differs
  Scenario: A row cannot say which endpoint or which prompt-length tier applies
    Given an id names no endpoint, or a vendor prices a model in prompt-length tiers
    When the row takes some prices from one and some from another
    Then it is refused, because every price in a row must come from the same one

  @fires:c23.price-differs
  Scenario: A dated price change takes effect
    Given a vendor's page announces a new price from a date
    When that date is within 30 days
    Then every run prints a WARN line naming the model, the date and the new price
    And on that date a row still at the old price is refused

  @fires:c23.price-differs
  Scenario: A model is priced by prompt length
    Given a vendor prices a model higher above a prompt-length threshold
    And a table can carry a prompt-length tier
    When the table's tier starts at another threshold, carries another long price, or is missing
    Then it is refused, because a long prompt would be billed at the wrong price
    And a tier the table carries for a model the vendor prices at one rate is refused too

  @fires:c23.stale-exception
  Scenario: A recorded choice stops describing anything
    Given a repository chose a disagreement on purpose and it is recorded with its reason
    When the row agrees without it, matches neither price, is gone, or the dated price it took early is now in effect
    Then the exception is refused as stale, because a choice nobody needs any more must be removed
    And while it still applies it is printed as an EXCEPTION on every run, never passed in silence

  @fires:c23.stale-exception
  Scenario: A row nobody can price is declared by its cause, and the declaration goes stale when the row is priced
    Given a row no source here can price, or whose vendor lists no such model
    And a recorded cause names that row by its id, with a reason a later run can re-derive
    When the estate is read and the row is still not judged
    Then the run prints the row under its cause as declared not judged, counted apart from the comparisons that agreed
    And the run exits 0 when nothing else is red, and the summary says every subject was measured or declared
    But when the row is priced now, or is gone, the cause is refused as stale until that id is removed

  @fires:c23.current-model-missing
  Scenario: A current model has no row in the gateway's book
    Given a vendor's page marks a model as current
    And a table declared to price every current model has no row for it
    When the estate is read
    Then it is refused, because the gateway bills that model at its fallback
    And it prints the row to add

  @fires:c23.fallback-below-current
  Scenario: The fallback is cheaper than a current model
    Given a table's fallback price is below any price of a current model
    When the estate is read
    Then it is refused, because an unlisted call would be billed under its price

  @fires:c23.source-unparseable
  Scenario: A vendor page no longer has the shape the gate reads
    Given a vendor's page was fetched
    When its table, its column headings, its standard tier, its current-model marker or its regional premium sentence can no longer be read
    Then the gate says it measured nothing for that vendor, never OK
    And a page that could not be fetched at all is NOT MEASURED and ends the run incomplete

  @fires:c23.source-unparseable
  Scenario: The regional premium is stated in the words the page used on either day
    Given Anthropic's page states the premium for regional endpoints as "10%" or as "10 percent"
    When the premium is read
    Then a row naming a regional endpoint is priced at the list plus that premium
    But a sentence in other words ("ten percent", "10 per cent", "10 pct") is a page whose shape changed
    And the gate says it measured nothing for those rows rather than guess a premium nobody stated

  @fires:c23.source-unparseable
  Scenario: A vendor's page carries more than one table of one tier
    Given OpenAI's page carries a flagship text-token table and a model group's table, both marked standard
    When the page is read
    Then both are read, each price from the column its heading names, proved against the rows the table renders
    And a model that both tables price identically is one row
    But a model they price differently is read from neither, and the page is reported, never one table picked
    And the latest models are the flagship table's, and two tables with no model group between them leave them unread

  @fires:c23.table-unreadable
  Scenario: A declared price table cannot be read
    Given estate.json declares a price table
    When the file is gone, its shape no longer parses, its format has no reader, or the declaration is incomplete
    Then it is refused rather than read as an empty table

  @fires:c23.nothing-matched
  Scenario: Not one row of a table maps to a vendor price
    Given a declared price table whose every row is priced from somewhere this gate does not read
    When the estate is read
    Then the gate says it measured nothing for that table rather than reporting agreement

  @fires:c23.no-subjects
  Scenario: The registry declares no price table
    Given no estate.json entry carries a price_table
    When the estate is read
    Then the gate says it measured nothing rather than reporting agreement

  @teeth:c23.unmeasured-row-public
  Scenario: A row nobody can judge, in a repository with a public remote, is counted and the run is incomplete
    Given a declared price table in a repository with a public remote
    And one of its long-prompt tier rows is priced by a vendor whose page states no tier for that model
    And no recorded exception declares that row
    When the estate is read
    Then the row is printed NOT MEASURED and counted, and the summary says PARTIAL with the number
    And the run exits 2, the code for an unexpected partial, never 0
    And the summary does not claim full coverage while the row is counted

  @teeth:c23.unmeasured-row-private
  Scenario: The same uncounted row in a repository with no public remote is the expected partial
    Given the same row, in a repository whose remote is private
    When the estate is read
    Then the row is printed NOT MEASURED and counted, and the summary says PARTIAL with the number
    And the run exits 3, the code CI reads as success for the expected partial

  @teeth:c23.undeclared-not-judged-row-public
  Scenario: A row no source prices, that no cause declares, is counted and the run is incomplete
    Given a declared price table in a repository with a public remote
    And one of its rows is priced from no source this gate reads, or its vendor lists no such model
    And no recorded cause declares that row not judged
    When the estate is read
    Then the row is printed NOT MEASURED and counted, and the summary says PARTIAL with the number
    And the run exits 2, never 0, and the summary does not say every subject was measured

  @teeth:c23.undeclared-not-judged-vertex
  Scenario: A Gemini model Vertex AI lists that no table prices, and no cause declares, is counted against the gateway's book
    Given Google Vertex AI's page lists a model that no declared price table prices
    And no recorded cause declares that model not judged
    When the estate is read
    Then the model is printed NOT MEASURED and counted against the gateway's book, and the summary says PARTIAL with the number
    And the run exits 2, never 0

  @fires:c23.stale-exception
  Scenario: A tier recorded as off the vendor's page stops describing anything
    Given a long-prompt tier is recorded as one the vendor's page does not state
    When the page now states a long-prompt price for that model, or the row is gone
    Then the exception is refused as stale, and the row is judged in its own right
