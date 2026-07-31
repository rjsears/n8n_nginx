# Welcome {: #manual-welcome }

Comprehensive guide to operating the n8n Management Console after installation. Every UI option, every modal, every sub-tab.

## Welcome {: #welcome }

This manual is intended for operators who have already installed and deployed the n8n Management Suite. It does not cover initial installation — see the project [README](https://github.com/rjsears/n8n_nginx/blob/main/README.md) for setup, or the [migration guide](../MIGRATION.md) if upgrading from v2.

The audience is the person who logs into the management console day-to-day: starting and stopping containers, running and verifying backups, configuring notifications, troubleshooting SSL, managing access. If that's you, you're in the right place.

## How to read this manual {: #how-to-read }

The manual is organized in three parts. Read sequentially, or jump directly to the section you need via the navigation above.

Every page has a left-hand sidebar with anchors to its subsections. Use the prev/next links at the bottom of each page to step through in order.

!!! note

    Screenshots in this manual were captured from a live test deployment. Some screenshots contain sensitive data (API tokens, internal IPs, host names) which are flagged inline and indexed in the [Security Flag Index](appendix.md#security-index). Blur those images before publishing or sharing this manual outside your organization.

## Part 1: User Guide {: #part-1 }

Everyday operations. The pages most operators will visit most often.

- [**Dashboard** — system overview at a glance: container health, resource usage, recent activity](dashboard.md)
- [**Containers** — start, stop, restart Docker services; inspect logs and stats](containers.md)
- [**Flows** — view, toggle, and trigger n8n workflows; jump to n8n itself](flows.md)
- [**Backups** — schedule, run, verify, restore; configure retention and storage](backups.md)
- [**Notifications** — channels, groups, rules, NTFY topics, n8n webhook integration](notifications.md)

## Part 2: Administration {: #part-2 }

System-level configuration and integration management. Less frequent but more consequential.

- [**System** — health checks, SSL renewal, network, Cloudflare/Tailscale integrations](system.md)
- [**Settings** — every configuration knob: NFS, access control, email, environment variables, Redis cache, and more](settings.md)

## Part 3: Appendix {: #part-3 }

Reference material and the master security index.

- [**Troubleshooting** — symptom-to-section quick reference](appendix.md#troubleshooting)
- [**Security Flag Index** — all screenshots requiring blur before publishing](appendix.md#security-index)

## Legend

Throughout the manual, you'll see colored callout boxes. Their meaning is consistent:

!!! note

    additional context, not required reading.

!!! tip

    a recommended approach or shortcut.

!!! warning

    behavior that may surprise you, or has caveats.

!!! danger

    destructive or irreversible action.

!!! security "Security flag"

    screenshot contains sensitive data; blur before publishing.
