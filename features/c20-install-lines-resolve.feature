# language: en

Feature: Every README install line resolves to a release that exists

  @measured 2026-09-12
  """
  tokenfuse's front page said docker run ghcr.io/taipanbox/tokenfuse for two
  months while latest in the registry was a July build: the release workflow
  wrote latest only on the default branch, which a tag push never is, so
  every tag after v0.3.0 published its own tag and left latest where it was.
  The line was correct as a command and wrong as a claim, and nothing could
  see it (PUBLISH-READINESS 2026-09-12, section 1.1).
  """

  @decided 2026-09-12
  """
  No moving tag anywhere in the estate (decision 10.26, route A, extending the
  2026-08-02 decision four planes already followed). A README pins the tag it
  means, and this gate holds the pin against the repository's own tags and
  Release objects, so the day a newer tag is cut the README is red until the
  line is bumped.
  """

  Subjects are the README.md of every repository estate.json names: image
  references under ghcr.io/taipanbox and release download links under
  github.com/TAIPANBOX. A line carrying a placeholder is a template a reader
  fills in and is skipped. The owner of an image is the repository whose name
  is the longest prefix of the image name; Releases are read through the
  GitHub API, or from a fixture the self-test exports.

  @fires:c20.image-unpinned
  Scenario: A README names an image with no tag
    Given a README line pulling ghcr.io/taipanbox/<image> with no tag
    And the owning repository declares no moving tag
    When the estate is read
    Then it is refused, naming the line
    Because without a tag docker pulls latest, and there is no latest to pull

  @fires:c20.image-unowned
  Scenario: A README names an image no repository owns
    Given a README line pulling an image whose name is no repository's name or prefix
    When the estate is read
    Then it is refused
    Because it is a typo, or an image this estate does not publish

  @fires:c20.tag-unknown
  Scenario: A README pins a tag the repository never cut
    Given a README line pulling ghcr.io/taipanbox/<image>:<tag>
    And the owning repository has no git tag of that name
    When the estate is read
    Then it is refused, listing the tags the repository does have

  @fires:c20.repo-unknown
  Scenario: A README links a release of a repository the estate does not name
    Given a README line linking github.com/TAIPANBOX/<name>/releases/download
    And no repository <name> in estate.json
    When the estate is read
    Then it is refused

  @fires:c20.release-missing
  Scenario: A README links a download for a tag with no Release
    Given a README line linking releases/download/<tag>/<asset>
    And the repository has the git tag and no Release object for it
    When the estate is read
    Then it is refused, saying the git tag exists
    Because the URL is a 404 until somebody creates the Release

  @fires:c20.no-releases
  Scenario: A README links releases/latest in a repository with no Release
    Given a README line linking releases/latest/download/<asset>
    And the repository has no Release object at all
    When the estate is read
    Then it is refused

  @fires:c20.no-subjects
  Scenario: No README in the estate carries an install line
    Given every README without an image reference or a release link
    When the estate is read
    Then it is refused as having measured nothing
    Because a dozen repositories publish one, so finding none means the wrong thing was read
