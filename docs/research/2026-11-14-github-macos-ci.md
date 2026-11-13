# GitHub-hosted macOS CI: availability, cost, conditions, limitations

Written for: the builder and the quality-gates maintainers, a technical reader who is not a software engineer by trade.

Researched 2026-11-14 from primary sources (GitHub docs, the runner-images repository, GitHub changelog); numbered source references point to the Sources list at the end.

## Quick answers

Read this section first. Each row points to the section with the evidence; every claim in this table is sourced there.

| Question | Answer | Detail |
|---|---|---|
| Is macOS CI free on a public repo? | Yes for standard runners: free and unlimited. Larger runners (`-large`, `-xlarge`) are billed. No plan condition found. | Public repositories |
| What does it cost on a private repo? | Standard macOS $0.062 per minute, drawn from a monthly dollar allowance: $12 Free, $18 Pro and Team, $300 Enterprise Cloud. The "10x multiplier" is no longer stated by GitHub. | Cost |
| Which labels exist? | `macos-latest` (macOS 26 arm64), `macos-26`, `macos-15` (arm64); `macos-26-intel`, `macos-15-intel` (Intel). macOS 14 and 13 are retired. | Availability |
| Is Intel still available? | Yes, but being phased out: last Intel image supported until August or Fall 2027. Extra-large is arm64 only; the larger Intel size is "large". | Availability, Limitations |
| What hardware? | Standard arm64: 3 vCPU, 7 GB RAM, 14 GB disk. Standard Intel: 4 vCPU, 14 GB RAM, 14 GB disk. | Availability |
| Job and concurrency limits? | 6 hours per hosted job; 5 concurrent macOS jobs on Free, Pro and Team, 50 on Enterprise. | Conditions |
| Does code signing work? | Each job gets a fresh VM; import certificates into a temporary keychain every job. | Limitations |
| Fork pull requests? | No secrets except a read-only `GITHUB_TOKEN`; may need maintainer approval. | Public repositories |
| Self-hosted Mac instead? | No GitHub charge today; you pay for and maintain the machine. A $0.002 per minute platform fee was announced and postponed with no new date. Almost never use it with public repos. | Self-hosted alternative |
| Does it suit this repo (Python 3.9 floor)? | Python 3.9 is not preinstalled on macOS 26 or 15 arm64 images; `setup-python` has arm64 3.9 only up to 3.9.13. Pin labels, do not use `macos-latest`. Swift version is not listed; read it at run time. | Fit for this repo and its consumers |
| Which draft claims were wrong? | Extra-large is not Intel; allowances are dollars not minutes; "10x" is unconfirmed; macOS 13 and 14 labels are gone. | Verification table |
| What is unresolved? | Multiplier, larger-runner plan eligibility, regions, outages, Swift version. | Open questions |

## Public repositories

- **Free and unlimited.** "Use of the standard GitHub-hosted runners is free and unlimited on public repositories" [1]. The billing concepts page lists "Standard GitHub-hosted runners in public repositories" as usage that "remains free independently and does not reduce the included compute usage" [26]. It lists self-hosted runner usage, GitHub Pages and Dependabot as free in the same way [26].
- **Applies to macOS.** The macOS standard runners (arm64 `macos-latest`, `macos-15`, `macos-26`, `xcode-27`; Intel `macos-15-intel`, `macos-26-intel`) appear in the standard table, whose notes carry the public-repository rule [1]. The macOS specs are identical for public and private repositories [1].
- **Not free.** "Larger runners are billed for public repositories" [26][9]. That covers every `-large` and `-xlarge` label [8].
- **No plan condition found.** The pages read name no plan, spending-limit or credit-card requirement for standard runners on public repositories. The account plan does not change this in the sources read [1][26].
- **Demand.** "During periods of high demand, jobs that run on macOS runners may take longer to start." No start-time guarantee is given [1].
- **Usage terms.** GitHub's terms bar cryptomining, using Actions as a CDN or serverless backend, and activity unrelated to "the production, testing, deployment, or publication of the software project" on hosted runners. They also bar "any activity that places a burden on our servers, where that burden is disproportionate to the benefits provided to users" [27]. The terms set no numeric fair-use cap for free public usage; the burden clause is GitHub's discretion [27].
- **Fork pull requests.** Runs triggered by a fork's pull request may need manual approval from a maintainer with write access [28]. Secrets are not passed to the runner for a fork's `pull_request` run, except `GITHUB_TOKEN`, which is read-only [29]. Any gate that needs a secret cannot run on fork pull requests.
- **Rate limits that still apply.** `GITHUB_TOKEN` is limited to 1,000 requests per hour per repository; 256 jobs per matrix; 6 hours per hosted job [3].

## Fit for this repo and its consumers

- **Python 3.9 is not preinstalled on macOS images.** The macOS 26 arm64 and macOS 15 arm64 images carry Python 3.11 to 3.14 as cached versions and 3.15.2 as the system version; 3.9 is absent from both [6][7][30][31]. The repo's floor is 3.9 (CLAUDE.md), so a macOS job must install it.
- **3.9 on arm64 is limited.** The `actions/python-versions` manifest, which `setup-python` draws from, lists darwin arm64 builds for 3.9 only up to 3.9.13. Intel (x64) builds go to 3.9.25 [32]. Whether `setup-python` resolves 3.9 on `macos-latest` was not run; settle it with a test job.
- **Label drift.** `-latest` labels move to a newer OS [1][4]. This repo already hit that on Linux, where `ubuntu-latest` moved to 26.04 and dropped Python 3.9 (git history, commit 3c794f5). Pin macOS labels (`macos-26`, `macos-15`) for the same reason.
- **Swift.** No images list a Swift compiler version; Swift comes with the Xcode versions installed [6][7]. A Swift gate should read the version from `xcodebuild -version` or `swift --version` at run time, or select Xcode explicitly.
- **Cost for private consumers.** A consumer on a private repository on Free gets $12 per month, about 193 standard macOS minutes (derived, see Cost). Pin-bump checks on macOS should be kept short or run only on Linux unless a gate needs Apple tooling.

## Cost

**Per-minute rates, USD (standard runners unless marked).** [9]
- macOS 3- or 4-core, M1 or Intel: $0.062 per minute.
- Larger macOS 12-core, x64: $0.077 per minute.
- Larger macOS 5-core arm64: $0.102 per minute.
- Linux 2-core x64: $0.006; Linux 2-core arm64: $0.005; Windows 2-core: $0.010.
- Rounding: "GitHub rounds the minutes and partial minutes each job uses up to the nearest whole minute" [9].
- Hosted prices were cut by up to 39% effective 2026-01-01 [11]; the macOS rate above is the post-cut rate [2][9].

**Multiplier.** The billing docs state no multiplier [2][9]. A docs issue opened 2026-07-13 notes that the minute-multiplier section was removed from the pricing page; a reply on 2026-10-24 says a support ticket is pending [14]. Whether macOS consumes 10x included usage is therefore unresolved [14].

**Included allowance.** [2][13]
- Free and Free for organizations: $12 per month [2].
- Pro and Team: $18 per month [2].
- Enterprise Cloud: $300 per month [2].
- The pricing page gives the same allowances as Linux-equivalent minutes: 2,000 (Free), 3,000 (Team), 50,000 (Enterprise) [13]. Pro is not shown on that page.
- Derived, not stated by GitHub: at $0.062 per macOS minute, the allowance covers about 193 macOS minutes on Free, about 290 on Pro and Team, and about 4,839 on Enterprise Cloud.

**Public vs private.** Standard hosted runners on public repos are free [2][4][9]. "Larger runners are not free for public repositories" [9]. On private repos, usage draws from the included allowance and then is charged per minute [2].

**Self-hosted fee.** On 2025-12-16, GitHub announced a "$0.002 per-minute Actions cloud platform charge" for self-hosted runners starting 2026-03-01 [10]. The same page then says GitHub is "postponing the announced billing change for self-hosted GitHub Actions to take time to re-evaluate our approach" [10][12]. No new date is given [10][12]. The current billing docs show no self-hosted charge [2][9].

## Availability

**Labels and images.** The runner-images README lists these macOS labels: `macos-latest-large`, `macos-26-intel`, `macos-26-large` (macOS 26, x64); `macos-latest`, `macos-26`, `macos-26-xlarge` (macOS 26, arm64); `macos-15-large`, `macos-15-intel` (macOS 15, x64); `macos-15`, `macos-15-xlarge` (macOS 15, arm64); `macos-14` (macOS 14, x64, deprecated and retired); and `xcode-27`, `xcode-27-xlarge` (Xcode 27, preview) [4]. The hosted-runner reference lists the standard labels, including `macos-latest`, `macos-15`, `macos-26`, `xcode-27` and the Intel `macos-15-intel` and `macos-26-intel` [1]. The larger-runner reference adds the large and xlarge labels [8].

**What "latest" means for larger runners (unresolved).** The README maps `macos-latest-large` to macOS 26 x64 and lists no `macos-latest-xlarge` [4]. The larger-runner reference marks `macos-15-large` and `macos-15-xlarge` as "(latest)" [8]. The sources disagree; this report does not pick one. For standard runners, `macos-latest` is macOS 26 arm64 [4].

**Architecture and sizes.**
- Standard arm64 (M1): 3 vCPU, 7 GB RAM, 14 GB SSD [1].
- Standard Intel: 4 vCPU, 14 GB RAM, 14 GB SSD [1].
- Larger Intel "large": 12 vCPU, 30 GB RAM, 14 GB SSD [8].
- Larger arm64 "xlarge": 5 vCPU (plus 8 GPU-accelerated hardware units) on M2, 14 GB RAM, 14 GB SSD [8]. The billing page calls the same class a "5-core (M2 Pro)" [9]; the two sources disagree on the chip name.

**Regions.** The hosted-runner page says "GitHub hosts macOS runners in Azure data centers" [17]. No region list is published in the pages read, so regional availability is unverified [17].

**Retirements.**
- macOS 13: "will be retired by December 4th, 2025" [21].
- macOS 14 (Intel and arm64): retired on 2026-11-02; macOS 14 Intel stays on Azure DevOps until 2026-11-23 [4][5]. The retirement notice lists brownout (temporary failure) windows on 11-05, 11-12, 11-15 and 11-19 [5]. Brownout windows after 11-02 conflict with the retirement date and are flagged in Open questions.
- macOS 15 Intel: the last x86_64 image, "available from now until August 2027" [22]; the changelog says "Fall 2027" [21].

## Conditions

- **Plan and repo rules.** Larger runners require a credit card on file and a spending limit above zero [8]. Enterprise runners are not available at repo level by default and must be enabled by an organization administrator [8]. The concurrency table lists larger-runner limits for Team and Enterprise only; Free and Pro show "Not listed" [3]. This report does not infer that Free or Pro are excluded. Larger runners are billed on public repos as well as private ones [9].
- **Job timeout.** The default job timeout is 360 minutes [24]. Hosted jobs may run up to 6 hours of execution time [3]; the workflow syntax page gives the step-level maximum as 360 minutes for both hosted and self-hosted runners [24]. Self-hosted jobs may run 5 days [3].
- **Workflow run.** A run lasts up to 35 days including waiting and approvals; 256 jobs per matrix; 50 re-runs per run [3].
- **Concurrency (hosted macOS; standard and larger share one pool).** Free 5, Pro 5, Team 5, Enterprise 50 [3]. Support can raise these by ticket [3].
- **Storage per runner.** 14 GB SSD on every macOS hosted runner [1][8].
- **Cache.** 10 GB per repository; the eviction policy deletes caches by last access; entries not accessed in over 7 days are removed; no cap on cache count [19].
- **Artifacts and logs.** Retained 90 days by default. Public repos may set 1–90 days; private and internal repos 1–400 days [20]. A per-artifact `retention-days` cannot exceed the repo or org limit [23]. From 2026-10-01 the policy also applies to checks, workflow runs and commit statuses [20].
- **Artifact storage by plan.** 500 MB (Free), 1 GB (Pro), 2 GB (Team), 50 GB (Enterprise Cloud); GitHub Support cannot raise storage limits [3].
- **Network.** Hosted runners need at least 70 kbps upload and download [17]. Inbound ICMP is blocked, so ping and traceroute may not work [17]. Jobs may run on AWS or Azure [17].

## Limitations

- **Fresh VM per job.** Hosted runners are "isolated virtual machines that are automatically destroyed at the end of the job execution" [18]. A keychain created in one job does not exist in the next [18].
- **Code signing on hosted macOS.** The Apple-certificate guide creates a temporary keychain inside the job and recommends deleting it only on self-hosted runners, where the keychain "might still exist" afterwards [18]. Inference, not stated by GitHub: signing on hosted macOS means importing the certificate and profile again in each job, from stored secrets [18].
- **Larger macOS feature gaps.** Static IP addresses, custom images and Azure private networking are "available only on Linux and Windows runners" [8][1]. Nested virtualization is not supported "due to the limitation of Apple's Virtualization Framework" [8].
- **Xcode lag and policy.** The README says "only one major version of Xcode will be supported per macOS version," and "all minor versions of the supported major version will be available" [4]. The macOS 26 arm64 image (20261102.0473.1) defaults to Xcode 26.6 and installs 26.0.1 to 26.6 [6]. The macOS 15 arm64 image (20261104.0514.1) defaults to Xcode 16.4 and lists 16.0 to 16.4 and also 26.0.1 to 26.3 [7]. The macOS 15 image therefore shows two major versions, which conflicts with the one-major-version policy; unresolved (see Open questions). Xcode 27 is in public preview [4][6].
- **Swift.** The macOS 26 arm64 readme lists SwiftFormat 0.64.5 and no Swift compiler version [6]. Swift is unverified as a separately listed tool.
- **Intel retirement.** Apple discontinued Intel; the 2025 notices name `macos-15-intel` as the last x86_64 image and say Intel support ends after the macOS 15 image retires in 2027 [21][22]. `macos-26-intel` is still listed [4]; no retirement date for it was found, so the claim that it is the last Intel image is unverified.
- **Outages.** No outage history was checked in this pass; see Open questions.

## Self-hosted alternative

- **What it saves.** The hosted per-minute charge: standard macOS $0.062/min [9]. Self-hosted usage carries no GitHub per-minute charge today [15][2][9].
- **What it costs.** "you are responsible for the cost of maintaining your runner machines" [15]. The team is responsible for updating the operating system and other software [15].
- **Security.** "self-hosted runners should almost never be used for public repositories" [16]. For private repos, anyone who can fork and open a pull request may compromise the runner [16]. Re-using hardware can expose environment data, so GitHub recommends JIT ephemeral runners created via the REST API, each starting from a clean environment [16]. Runner groups limit the damage a compromise can do [16].
- **Keychain.** Self-hosted machines may keep keychains and profiles after a job; the guide adds an explicit clean-up step [18].
- **Fee risk.** GitHub's note says the $0.002/min platform charge for self-hosted runners is postponed, not cancelled [10]. A future fee would change the cost claim.

## Verification table

Verdicts are one of: Confirmed, Corrected, Outdated, Unverified.

| # | Draft claim | Verdict | Note | Source |
|---|---|---|---|---|
| 1 | GitHub provides macOS CI natively through GitHub Actions | Confirmed | The glossary terms are definitions, not checkable facts. | [1], [17] |
| 2 | Hosted runners are preconfigured, managed macOS VMs | Confirmed | "each GitHub-hosted runner is a new virtual machine (VM) hosted by GitHub" and "comes with the runner application and other tools preinstalled." | [17] |
| 3 | Labels such as `macos-latest`, `macos-26`, `macos-15` exist | Corrected | The named labels exist. The draft omits that macOS 14 labels were retired 2026-11-02 and macOS 13 by 2025-12-04. | [4], [5], [21] |
| 4a | Both Apple Silicon (arm64) and Intel (x64) VMs are available | Confirmed | Standard and larger runners in both architectures. | [1], [4], [8] |
| 4b | Both architectures come in "standard and extra-large" sizes | Corrected | The extra-large size is arm64 only. The bigger Intel size is "large" (12 vCPU, 30 GB RAM). | [4], [8] |
| 4c | Intel runners are still offered | Outdated | Still offered, but Apple has discontinued Intel. The 2025 notices say `macos-15-intel` is the last x86_64 image and that Intel support ends when the macOS 15 image retires, dated "August 2027" in one notice and "Fall 2027" in the changelog. | [4], [21], [22] |
| 5a | Images include Xcode and Homebrew | Confirmed | Several Xcode versions (default 26.6 on macOS 26 arm64, 16.4 on macOS 15 arm64) and Homebrew 7.0.11 / 7.0.12. | [6], [7] |
| 5b | Images include Swift and other Apple dev tools | Unverified | The macOS 26 arm64 readme lists SwiftFormat 0.64.5 but no Swift compiler version. | [6] |
| 6a | Standard macOS runners are free for public repos | Confirmed | Two pages state it directly (see Public repositories below); larger runners are billed. The billing-rates page [9] does not state it. | [1], [26] |
| 6b | Private repos draw from included usage and are charged per minute | Confirmed | Per-minute macOS cost is about 10.3 times Linux 2-core ($0.062 vs $0.006; derived). | [2], [9], [13] |
| 6c | Multipliers: Linux 1x, Windows 2x, macOS 10x | Outdated | The docs now publish per-minute rates and state no multiplier. Windows 2-core is $0.010/min (about 1.7x Linux 2-core; derived). The 10x figure is unconfirmed; its removal is disputed. | [9], [14] |
| 6d | Included minutes per plan | Corrected | The allowance is in dollars: $12 Free, $18 Pro and Team, $300 Enterprise Cloud. The pricing page shows 2,000 / 3,000 / 50,000 Linux-equivalent minutes. | [2], [13] |
| 6e | macOS minutes are billed in the included pool | Confirmed | Per-minute rates "determine the cost deducted from your included compute usage." | [9] |
| 7a | Self-hosted Mac can cut costs | Confirmed | Self-hosted usage carries no GitHub per-minute charge today; maintenance cost is yours. | [15], [2], [9] |
| 7b | Requires managing uptime and code signing manually | Confirmed | The team maintains the OS and runner software; self-hosted keychains may persist after a job. | [15], [18] |
| 7c | Public-repo warning and ephemeral runners | Confirmed | "self-hosted runners should almost never be used for public repositories"; GitHub recommends just-in-time (JIT) ephemeral runners. | [16] |
| 7d | Labels for self-hosted runners | Unverified | The labels page lists custom labels, case-insensitive, but does not list macOS or arm64 as default labels. | [25] |
| 7e | Self-hosted runners carry no GitHub fee (not in the draft; checked because it changes the cost claim) | Confirmed for now | No fee in the current docs. A $0.002/min fee was announced, then postponed with no restart date. | [10], [12], [2], [9] |

## Open questions

1. **Multiplier (Linux 1x, Windows 2x, macOS 10x).** Could not confirm. Settled by GitHub's written answer to the support ticket referenced in [14], or by a billing-page revision that restores a multiplier table.
2. **Xcode policy vs the macOS 15 image.** The policy says one major version per macOS [4]; the macOS 15 image readme lists 16.x and 26.x [7]. Settled by GitHub clarifying whether the policy applies to supported or installed versions.
3. **Swift version.** Not listed in the macOS 26 arm64 readme [6]. Settled by the per-image Swift section in a runner-images readme, if one exists, or by running `swift --version` on a hosted job.
4. **"Latest" for larger runners.** README [4] and the larger-runner reference [8] disagree. Settled by GitHub aligning the two pages.
5. **Brownout windows for macOS 14.** The retirement notice lists windows on 11-15 and 11-19, after the 11-02 retirement [5]. Settled by GitHub clarifying the issue timeline, in particular whether these windows apply to the Azure DevOps Intel extension that runs to 11-23.
6. **Larger-runner eligibility by plan.** Only Team and Enterprise appear in the concurrency table [3]; Free and Pro are "Not listed." Settled by the larger-runner billing or plan page, not reached in this pass.
7. **Regions.** Only "Azure data centers" is stated [17]. Settled by a published region list, if one exists.
8. **Intel end date.** "August 2027" [22] vs "Fall 2027" [21]. Settled by GitHub's next Intel notice.
9. **`macos-26-intel` retirement.** Not announced in the sources read [4][21].
10. **Self-hosted fee restart.** No new date [10][12]. Settled by a dated GitHub changelog entry.
11. **Self-hosted labels for macOS.** The labels page does not list macOS or arm64 as default labels [25]. Settled by the self-hosted runner configuration page for macOS.
12. **Outages.** Not checked. Settled by the GitHub status history page, if the builder needs it.

## Terms

a **runner** is a machine that executes CI jobs; **hosted** means GitHub operates it, **self-hosted** means the team operates it. A **label** is the name a workflow file uses to request a runner type. A **VM** (virtual machine) is a software-simulated computer. The **orchestrator** is GitHub Actions itself, which schedules jobs onto runners. A **pipeline** or **harness** is the workflow that runs the checks. **Ecosystem** means the wider set of tools and images around it.

## Sources

1. https://docs.github.com/en/actions/reference/runners/github-hosted-runners — read 2026-11-14; no last-updated date shown.
2. https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions — read 2026-11-14; no last-updated date shown.
3. https://docs.github.com/en/actions/reference/limits — read 2026-11-14; no last-updated date shown.
4. https://github.com/actions/runner-images — README read 2026-11-14 (labels, retirement notice, Xcode policy, `-latest` labels).
5. https://github.com/actions/runner-images/issues/15226 — macOS 14 retirement announcement; latest visible entry 2026-11-13.
6. https://github.com/actions/runner-images/blob/main/images/macos/macos-26-arm64-Readme.md — image 20261102.0473.1; read 2026-11-14.
7. https://github.com/actions/runner-images/blob/main/images/macos/macos-15-arm64-Readme.md — image 20261104.0514.1; read 2026-11-14.
8. https://docs.github.com/en/actions/reference/runners/larger-runners — read 2026-11-14; no last-updated date shown.
9. https://docs.github.com/en/billing/reference/actions-runner-pricing — read 2026-11-14; no last-updated date shown.
10. https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/ — announcement 2025-12-16; postponement note undated; read 2026-11-14.
11. https://github.blog/changelog/2026-01-01-reduced-pricing-for-github-hosted-runners-usage/ — dated 2026-01-01; read 2026-11-14.
12. https://github.com/resources/insights/2026-pricing-changes-for-github-actions — published 2025-12-15; read 2026-11-14.
13. https://github.com/pricing — "© 2026 GitHub, Inc."; no last-updated date; read 2026-11-14.
14. https://github.com/github/docs/issues/45138 — opened 2026-07-13; replies to 2026-10-24; read 2026-11-14.
15. https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners — read 2026-11-14; no last-updated date shown.
16. https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions — read 2026-11-14; no last-updated date shown.
17. https://docs.github.com/en/actions/concepts/runners/github-hosted-runners — read 2026-11-14; no last-updated date shown.
18. https://docs.github.com/en/actions/use-cases-and-examples/deploying/installing-an-apple-certificate-on-macos-runners-for-xcode-development — read 2026-11-14; no last-updated date shown.
19. https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching — read 2026-11-14; no last-updated date shown.
20. https://docs.github.com/en/organizations/managing-organization-settings/configuring-the-retention-period-for-github-actions-artifacts-and-logs-in-your-organization — read 2026-11-14; no last-updated date shown.
21. https://github.blog/changelog/2025-09-19-github-actions-macos-13-runner-image-is-closing-down/ — dated 2025-09-19; read 2026-11-14.
22. https://github.com/actions/runner-images/issues/13045 — opened 2025-09-19; read 2026-11-14.
23. https://docs.github.com/en/actions/using-workflows/storing-workflow-data-as-artifacts — read 2026-11-14; no last-updated date shown.
24. https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax — read 2026-11-14 (timeout-minutes section, read at two offsets); no last-updated date shown.
25. https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/using-labels-with-self-hosted-runners — read 2026-11-14; no last-updated date shown.
26. https://docs.github.com/en/billing/concepts/product-billing/github-actions — read 2026-11-14; no last-updated date shown.
27. https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features — Actions section; read 2026-11-14.
28. https://docs.github.com/en/actions/how-tos/manage-workflow-runs/approve-runs-from-forks — read 2026-11-14.
29. https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows — `pull_request` section; read 2026-11-14.
30. https://github.com/actions/runner-images/blob/main/images/macos/macos-26-arm64-Readme.md — same page as [6]; Python section re-read 2026-11-14.
31. https://github.com/actions/runner-images/blob/main/images/macos/macos-15-arm64-Readme.md — same page as [7]; Python section re-read 2026-11-14.
32. https://raw.githubusercontent.com/actions/python-versions/main/versions-manifest.json — parsed locally 2026-11-14.
