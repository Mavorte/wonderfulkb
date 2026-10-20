---
title: "Rollback paths must be anchored to the deployment script"
date: 2026-10-20
category: tooling
component: backend
tags: [bash, deployment, path-resolution, testing]
file_type: rules
---

# Anchor deployment rollback paths to the script

Shell deployment scripts may be invoked from any working directory. Resolve the script directory using `${BASH_SOURCE[0]}` before changing directories, then derive rollback template paths from that absolute directory. A regression test can safely evaluate only the path assignments from a separate cwd, avoiding deployment/AWS actions.

When testing via `bash -c`, `${BASH_SOURCE[0]}` does not naturally refer to the deploy script; substitute the known script path into the extracted assignment for the isolated path probe.
