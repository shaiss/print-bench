#!/usr/bin/env bash
# The data-branch stand-in for scripts/vercel-ignore-build.sh — NOT a copy of it.
#
# The Vercel project's Ignored Build Step is `bash scripts/vercel-ignore-build.sh`,
# and Vercel runs it inside the PUSHED commit's tree. The `telemetry` data branch
# (built with git plumbing by ci.yml's telemetry roll-up and reeve.yml's
# `observe` job) carries no scripts/, so the real gate is missing there, bash
# exits 127, and Vercel reads any non-zero exit as "build" — a preview
# deployment for every data push. Both builders hash this file into the data
# tree at scripts/vercel-ignore-build.sh (mode 100755), beside a root vercel.json
# from the same directory that turns git deployments of the commit off outright
# (git.deploymentEnabled: false, ignoreCommand: exit 0). This is the belt to
# that file's braces: if the project setting still runs, it skips.
#
# Exit 0 is Vercel's "skip the build". The branch holds data, never a site.
exit 0
