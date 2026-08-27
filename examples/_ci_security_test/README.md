# CI security-gate test fixture (temporary)

This folder exists only to verify that the `shift-left-security` job added in
`.github/workflows/pr-check.yml` actually runs and fails a PR as expected.

`requirements.txt` pins `pyyaml==5.1`, which has known CVEs
(CVE-2020-14343, CVE-2020-1747) that Trivy's filesystem scan should flag.

**Do not merge this PR.** Delete this folder and close the PR once the
`shift-left-security` check is confirmed failing.
