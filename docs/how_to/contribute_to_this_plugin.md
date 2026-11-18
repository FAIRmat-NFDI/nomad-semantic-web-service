# Contribute to This Plugin

## Branching model

`nomad-semantic-web-service` follows the same branching model as the core NOMAD packages and the `pynxtools` family.

| Branch | Role |
|---|---|
| `develop` | Default branch. All regular development PRs target this branch. |
| `main` | Released versions only. Only `release/*` branches are merged here, so its history is the release history. |
| `release/vX.Y.Z` | Temporary release branch, created from `develop` and merged into `main`. The version may carry a pre-release suffix, e.g. `release/vX.Y.Z-beta` or `release/vX.Y.Z-rc1`. |

| Activity | Branch |
|---|---|
| Feature development | `develop` |
| PR review and integration | `develop` |
| Selecting changes for a release | `release/vX.Y.Z` |
| Release-specific bug fixes | `release/vX.Y.Z` |
| Published release history | `main` |
| Porting release fixes back to ongoing development | Merge `release/vX.Y.Z` back into `develop` |

PRs into `main` are only accepted from `release/*` branches; this is enforced as a required
status check in the branch protection rule for `main`.

## Contributing to the package on GitHub

Once you are happy with your changes, commit them on a separate branch created from `develop`
and open a pull request against `develop`:

```console
git switch develop && git pull
git switch -c <short-descriptive-name>
# commit your changes, then
git push -u origin <short-descriptive-name>
```

Never open a pull request against `main`: it receives only `release/*` branches. A number of
GitHub actions check linting, run the tests in an isolated environment, and build the
documentation. Once these pass and a peer review of the code has occurred, your contribution
will be accepted.

## Use of AI tools

We recognize the value of AI-assisted development and do not discourage its use. AI coding
assistants can be helpful for tasks such as exploratory code generation, refactoring, and
documentation updates.

At the same time, design decisions, software architecture, and acceptance of contributions must
remain under human control.

!!! note "Policy under development"
    A formal policy on AI usage in contributions is still being developed. For now, we encourage
    judicious use.

For now, contributors are expected to follow these guidelines:

**Declaration of AI usage.**
If AI tools were used in preparing a contribution, this must be stated in the pull request
description. The declaration must name the tool(s) used and briefly describe the scope of their
involvement (e.g. "Used GitHub Copilot for initial design of X" or "Used Claude Code to assist
with refactoring Y").

**Human authorship and responsibility.**
All AI-generated content must be reviewed, understood, and validated by the contributing author
before submission. The contributor is fully responsible for the correctness, quality, and
suitability of the code, regardless of how it was produced. Contributions that are evidently
fully AI-produced with no human involvement will not be accepted.

**Code review.**
AI tools may be used as a supplementary aid during code review, but final review decisions must
always be made by a human maintainer. Automated or AI-driven review does not substitute for
human judgment on design, correctness, or scientific validity.
