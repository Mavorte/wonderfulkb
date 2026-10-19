# CODEOWNERS review gates

Wonderful supports one shared CODEOWNERS model for agent, Shared Library,
function, and app repositories. Use it when different people or groups should
review changes to different parts of a repository.

## Where the file lives

Prefer `.wonderful/CODEOWNERS`. Wonderful checks these locations in order and
uses the first file it finds:

1. `.wonderful/CODEOWNERS`
2. `CODEOWNERS`
3. `docs/CODEOWNERS`

The file is read from the current tip of the pull request's target branch.
Changing CODEOWNERS on a source branch cannot weaken the gate for that same
pull request. Merge ownership changes separately before relying on them.

Older repositories may ignore `.wonderful/*`. If so, add
`!.wonderful/CODEOWNERS` to `.gitignore` before committing the file.

## How to write rules

Each rule is a path pattern followed by one or more owners:

```text
# Default ownership
* @groups/platform-team

# More specific ownership
prompts/** @users/conversation-design
functions/payments/** payments-owner@example.com @groups/platform-team
```

Owners can be:

- A user email address.
- `@users/<user-id-or-unique-name-slug>`.
- `@groups/<group-id-or-unique-name-slug>`. For example, the group
  `Platform Team` can be referenced as `@groups/platform-team`.

Patterns follow GitHub-style CODEOWNERS matching. `*`, `**`, and `?` are
supported, paths beginning with `/` are anchored to the repository root, and
the last matching rule wins for each changed path. A later matching rule with
no owners removes ownership from that path. Negated patterns (`!`), character
ranges (`[]`), and an escaped leading `#` are not supported.

## How the gate is evaluated

Wonderful determines changed paths from the pull request's merge base to its
source commit, then matches those paths against CODEOWNERS from the current
target tip. Owners from every matched path are combined and deduplicated.

One approval from any matched user, or any current member of a matched group,
satisfies the CODEOWNERS gate. The approver must still have permission to
approve the repository, and self-approval follows the target branch policy.

CODEOWNERS is independent from the branch's approval count, explicitly
configured approvers, validation, conflicts, and required Actions checks. All
required gates must pass before merging.

A user on the target branch's merge bypass list can merge with the approval
count, configured approvers, and CODEOWNERS still unmet. Validation, conflicts,
and required Actions checks still block. Auto-merge never bypasses. Do not
merge through the bypass unless the user explicitly asks for that merge.

Unknown or ambiguous users, unknown or empty groups, an invalid pattern, an
oversized CODEOWNERS file, or an excessively large changed-file set fails
closed as a repository validation error. Do not work around that error by
removing the rule. Fix the identity or pattern on the target branch.

After pushing, inspect the server-calculated gate with:

```bash
wful pr view <number> --json
wful pr checks <number> --watch --exit-status
```

For a standalone Shared Library, add `--lib` to the pull request commands.
