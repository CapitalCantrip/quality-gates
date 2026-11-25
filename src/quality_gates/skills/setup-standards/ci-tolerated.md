# The tolerated-list step

`qg tolerated` says whether the tolerated list grew against the pull
request's base. Paste this at the end of the steps of the job that runs the
gates, in a workflow that runs on pull requests, indented like the other steps
of that job:

```yaml
      - name: qg tolerated
        if: github.event_name == 'pull_request'
        shell: bash
        env:
          BASE: ${{ github.base_ref }}
          QG_PR_LABELS: ${{ join(github.event.pull_request.labels.*.name, ',') }}
        run: |
          git fetch --no-tags --depth=1 origin "+refs/heads/${BASE}:refs/remotes/origin/${BASE}"
          qg tolerated --against "origin/${BASE}"
```

The step fails the pull request when the tolerated list grew (a baseline
entry new or raised, a new or wider `exclude` or `settings.no-comments.exclude`
prefix) unless it carries the builder's `tolerated-growth` label, or
`loosening` on a loosening pull request. It reads the labels from
`QG_PR_LABELS`. An agent never applies either label itself: the label is the
builder's yes on record.

Give the workflow's `pull_request` trigger these types, so that adding or
removing a label runs the check again; a re-run of an old job still sees the
labels it started with:

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened, labeled, unlabeled]
```

The job must have installed quality-gates before this step. `qg setup` never
edits a workflow; it prints this step when no workflow that runs on pull
requests runs `qg tolerated`.
