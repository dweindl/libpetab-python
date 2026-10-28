# petab contribution guide

We are happy about contributions to PEtab of any form.

## Contributions to this repository

General:

* For code contributions, please adhere to the
  [PEP8 style guide](https://www.python.org/dev/peps/pep-0008/)
* All new functionality should be covered by unit tests
* Please use Python type hints
* Please document all modules, functions, classes, attributes, arguments,
  return values, ... in a style consistent with the rest of the library
* Use descriptive commit messages

To contribute to this repository:

* Read our [contribution policy](#contribution-policy) below

* Create a pull request

  *By creating a pull request you agree with your contribution being made
  available under the license terms specified in
  [https://github.com/PEtab-dev/libpetab-python/blob/main/LICENSE](https://github.com/PEtab-dev/libpetab-python/blob/main/LICENSE).*

* Assign a reviewer, or let us know otherwise, that your pull request is ready
  for review.

* Wait for feedback (and feel free to send a gentle reminder if you did not
  get any feedback within a week)

## Contribution policy

We use AI coding tools ourselves, and we have no objection to contributors
using them.
What we need, with or without AI, is a human who understands the change,
stands behind it, and has put in the work to make it fit the project's
architecture, conventions, and style.
Reviewing a contribution takes real maintainer time —
often more than writing the change would have taken.
A contribution has to be worth more to the project than the time it takes
to review it.
To keep that balance, the following rules apply to all contributions
(code, documentation, issues, and comments).

### Use of AI tools

1. **Disclose any use of AI.**
   State in the pull request or issue description which AI tools you used
   and for what, and which parts of the contribution are AI-generated
   (e.g., "implementation drafted with Claude Code and revised by hand,
   tests written manually").
   Using AI tools to understand the code or to debug does not need to be
   disclosed, nor does routine autocompletion; what matters is what ends up
   in the contribution.
   Pull requests with apparently undisclosed use of AI may be closed
   without review.

2. **You are the author, and you are responsible for the contribution.**
   Before submitting, you should have reviewed the change, understand what
   it does and why, and have run the relevant tests yourself.
   You are also responsible for ensuring that AI-generated content does not
   infringe third-party copyright and can be released under this project's
   license.

3. **We talk to you, not to your agent.**
   You may use AI tools to draft the initial text of an issue or pull
   request, as long as you review it before posting and disclose it.
   In the discussion that follows, however, we expect to talk to you.
   Do not use AI tools to speak for you in review comments or discussions.
   They may help you present information, e.g., format a table or a minimal
   example, but the reasoning and the wording have to be your own.
   If it seems that review comments are answered by relaying them to an AI
   tool and pasting the reply back, we may stop reviewing and close the pull
   request.

### Review capacity

4. **Discuss before you (or your agent) implement.**
   For anything beyond a small, obvious fix (as a rough guide: more than a
   few dozen lines, a new feature, or changes to the public API),
   open an issue or comment on an existing one first, and wait
   for feedback from a maintainer.
   A small fix can go straight to a pull request; describe the bug there.
   Large pull requests that were not discussed beforehand are closed
   without review.
   This saves time on both sides: yours, if the change is not wanted;
   ours, if it is wanted but needs a different approach.

5. **Contributions have to be worth the review effort.**
   We close issues and pull requests whose benefit to the project does not
   justify the time it takes to review them, regardless of how they were
   produced (bug reports excepted, see below).
   This includes contributions that are mostly AI-generated and do not meet
   the quality standards described above and in the
   [developer's guide](https://petab.readthedocs.io/projects/libpetab-python/en/latest/development.html).

6. **Bug reports are the exception.**
   We would rather have a rough bug report than none.
   Bug reports may be drafted with AI tools, as long as this is disclosed,
   you actually observed the problem, and you tell us how to reproduce it.
   AI-generated analyses of the cause are fine if marked as such, but they
   do not replace a reproducible example: a minimal PEtab problem or script
   we can run, preferably reduced to the bare minimum rather than your full
   model and data.
   Reports of problems nobody has observed are closed.
   This exception does not extend to feature requests, questions, or
   anything else that starts a discussion.

We are a small team and cannot afford to spend review time on
contributions that mainly serve to pad a GitHub profile.
If we closed your pull request with a link to this section, it is not a
judgement of you or your work; we have to prioritize.
We are glad to support anyone who wants to get involved for longer, brings
some background in the field, and is willing to familiarize themselves
with the code base; we are happy to point you to suitable issues.
If that is you, open an issue and tell us what you would like to work on.
