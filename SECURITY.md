# Security Policy

## Supported Versions

HoverNet v1.5 is the supported open-source local loop kit.

## Reporting A Vulnerability

If you find a vulnerability, open a private GitHub security advisory when
available, or open an issue with only the minimum detail needed to coordinate a
fix.

Do not include credentials, tokens, local machine paths, or private runtime
state in a public issue.

## Local Trust Model

The v1.5 loop kit is filesystem-based. The `from` field in a signal is
provenance, not authentication. Any process with write access to a workspace can
write to that workspace's bus files.

Do not use the local bus as an access-control boundary. Keep workspaces scoped
to users and processes you trust.
