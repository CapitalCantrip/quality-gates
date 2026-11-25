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
        run: |
          git fetch --no-tags --depth=1 origin "+refs/heads/${BASE}:refs/remotes/origin/${BASE}"
          qg tolerated --against "origin/${BASE}"
```

The job must have installed quality-gates before this step. `qg setup` never
edits a workflow; it prints this step when no workflow that runs on pull
requests runs `qg tolerated`.
