# language: en

Feature: The event registry and what the producers emit, in both directions

  @measured 2026-08-06
  """
  The registry said idryx emits seven types. idryx has no event writer at all,
  in any file: its detections leave by OTLP and by Slack. A consumer that
  built a handler for one of those seven would have waited forever, and one
  downstream product had already shipped the operator-facing description for
  two of them.
  """

  The reverse direction is the more valuable one and nothing anywhere checks
  it: genaryx appends console_command lines under a source the registry has no
  row for at all. A source nobody registered is a producer no consumer knows
  to expect.

  @fires:c4.unregistered-source
  Scenario: A producer emits under a source the registry does not have
    Given a repository writing events with a source
    And no row for that source in the registry
    When the estate is read
    Then it is refused, naming the site and the types
    Because a consumer cannot subscribe to a producer it has never heard of

  @fires:c4.unregistered-type
  Scenario: A producer emits types its own row does not list
    Given a registered source
    And emit sites producing types the row does not name
    When the two are compared
    Then it is refused, listing the extra types

  @fires:c4.registered-type-not-emitted
  Scenario: The registry lists a type nothing produces
    Given a row naming types
    And no emit site in that repository producing some of them
    When the two are compared
    Then it is refused, listing them
    Because a consumer that builds a handler for one of those waits forever

  @fires:c4.registered-source-silent
  Scenario: A registered source has no readable producer at all
    Given a row in the registry
    And no producer for it readable in this run
    When the estate is read
    Then it is refused
    Because a row is a statement about what is written today

  @fires:c4.reserved-source-emits
  Scenario: A source recorded as reserved has an event-writing path
    Given a row marked reserved and not emitted today
    And a repository with a writer
    When the estate is read
    Then it is refused
    Because reserved is a claim about the present, and a writer contradicts it

  @fires:c4.producer-undeclared
  Scenario: A repository constructs an event writer and nothing compares it
    Given a repository calling the chained-writer constructor outside tests
    And no declaration of it among the producers this check reads
    When the estate is read
    Then it is refused
    Because every type that repository emits is currently unchecked against
      the registry, which is the state this gate exists to end

  @fires:c4.writer-anchor-gone
  Scenario: The anchor that identifies a producer stops matching
    Given a producer file that no longer contains the writer construct
    When its types are read
    Then it is refused, naming the anchor
    Because the types below it were read from a file that may no longer emit,
      and a pattern that matches nothing returns a set that agrees with
      everything

  @fires:c4.writer-file-gone
  Scenario: A recorded producer file is not there
    Given a repository recorded as writing events from a path
    And no file at that path
    When the estate is read
    Then it says so
    Because the producer moving and the producer stopping need different
      fixes

  @fires:c4.producer-unreadable
  Scenario: A producer cannot be parsed
    Given a producer whose types could not be read
    When the comparison is attempted
    Then it says so
    Because a producer this check cannot parse is a hole, not a pass

  @fires:c4.registry-unparsed
  Scenario: The registry itself cannot be parsed
    Given a registry section that does not read as a table
    When the estate is read
    Then it says so
    Because both directions of this comparison rest on it

  @fires:c4.reserved-unverifiable
  Scenario: A reserved row cannot be checked
    Given a row marked reserved
    And the repository behind it unreadable
    When the claim is checked
    Then it says so rather than accepting the claim

  @fires:c4.producer-unreadable
  Scenario: The on-box verifier's source and types are read from its constants
    Given a producer that lives inside a shared module and writes its type through a variable
    And its source and type names declared in one const block
    When the const block loses a name, or no case writes a declared type, or the source written is not the declared one
    Then the producer is reported unreadable
    Because a constant nobody writes is a type the registry would go on claiming

  @fires:c4.reserved-unregistered
  Scenario: A RESERVED row names a source the registry does not know
    Given SPEC 6.2 records a source as RESERVED, and estate.json has no entry for its repository
    When the estate is read
    Then the claim is named as unverifiable, and the run does not abort
    Because a reserved claim about a repository nobody registered cannot be checked at all


  @fires:c4.unregistered-type
  Scenario: A type emitted from a second file of the producer is compared like the first
    Given a producer whose emit sites are spread over several of its own files
    And a constant declared beside one of the later emits, naming a type its row does not list
    When the two are compared
    Then it is refused, listing the extra type
    Because a file the check never opened is a producer it never read, and a
      registered row would read as never emitted when its emit lives elsewhere

  @fires:c4.producer-unreadable
  Scenario: A type written through a constant that no file of the producer declares
    Given a producer file that emits through a name nothing in its package declares
    When its types are read
    Then it is refused, and nothing is compared with the registry
    Because a type the check cannot resolve is a hole, not an agreement

  @teeth:c4.wardryx-measured-nothing
  Scenario: A producer tree with no emit left says it measured nothing
    Given wardryx's emitting files are gone and its writer file remains
    When C4 reads wardryx
    Then the finding says it measured nothing about the producer's emits
    Because a red line that only says the file could not be read does not tell
      an unread producer from an empty one

  @fires:c4.unregistered-type
  Scenario: A Go producer's later file writes an event type its row does not list
    Given a Go producer whose event literals are spread over several of its files
    And one of the later files writes an event literal naming a type its row does not list
    When the two are compared
    Then it is refused, listing the extra type
    Because a registered row reads as complete while a file the check never read writes one more

  @fires:c4.unregistered-type
  Scenario: A Go producer's helper called from a later file emits a type its row does not list
    Given a Go producer that emits through one helper, called from several of its files
    And a later file calling the helper with a type its row does not name
    When the two are compared
    Then it is refused, listing the extra type
    Because the helper is the producer's emit, wherever it is called from

  @fires:c4.unregistered-type
  Scenario: A Python producer's later module emits a type its row does not list
    Given a Python package whose emit calls are spread over several of its modules
    And one module emitting a literal type its row does not name
    When the two are compared
    Then it is refused, listing the extra type
    Because a module the check never opened is a producer it never read

  @fires:c4.unregistered-type
  Scenario: A Rust producer's later file writes a console line of an unlisted type
    Given a Rust producer that writes its lines with literal source and type inserts
    And a later file inserting a literal type its row does not name
    When the two are compared
    Then it is refused, listing the extra type
    Because a console line of a type nobody registered is an event no consumer expects

  @fires:c4.producer-unreadable
  Scenario: A Python producer emits a type computed at runtime
    Given a module whose emit call takes a type that is not a literal string
    When its types are read
    Then it is refused, and nothing is compared with the registry
    Because a type nobody can read is a hole, never an agreement

  @teeth:c4.go-measured-nothing
  Scenario: A Go producer whose event literals are all gone says it measured nothing
    Given a Go producer whose event literals are renamed away and whose writer file remains
    When C4 reads the producer
    Then the finding says it measured nothing about the producer's emits
    Because a red line that only says nothing could be read does not tell an empty producer from an unread one

  @teeth:c4.python-measured-nothing
  Scenario: A Python producer with no emit left says it measured nothing
    Given a Python package whose emitting modules are gone and whose writer module remains
    When C4 reads the producer
    Then the finding says it measured nothing about the producer's emits
    Because an empty package and an unread one look identical in a summary

  @teeth:c4.rust-measured-nothing
  Scenario: A Rust producer with no literal type left says it measured nothing
    Given a Rust producer whose type inserts are no longer literal and whose writer file remains
    When C4 reads the producer
    Then the finding says it measured nothing about the producer's emits
    Because a producer whose type is never a literal has nothing this reader can compare
