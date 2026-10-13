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
  and Google Vertex AI's pricing pages; OpenRouter's model list is the price
  for a row billed through OpenRouter and a secondary signal for the rest,
  where the vendor's page wins every disagreement.

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
