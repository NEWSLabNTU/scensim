#!/usr/bin/env bash
# The git hooks (scripts/hooks/) into the clone's shared hooks directory (`just install-hooks`;
# `just setup` runs it): each as a stub that runs the pushing worktree's own
# scripts/hooks/<name>, so every worktree of the clone has it and none takes it away by being
# removed (133). An earlier stub or link of ours is replaced; a hook of another origin is left
# alone, and said so.
#
#     scripts/install_hooks.sh [<checkout>]      # default: the one this script is in
set -e
cd "${1:-$(dirname "$0")/..}"
hooks="$(git rev-parse --path-format=absolute --git-common-dir)/hooks"
mkdir -p "$hooks"
mark="# scensim install-hooks stub"
for h in scripts/hooks/*; do
    [ -f "$h" ] && [ -x "$h" ] || continue      # the hooks only, not a __pycache__
    name=$(basename "$h"); dest="$hooks/$name"
    if [ -e "$dest" ] || [ -L "$dest" ]; then
        if ! { grep -qF "$mark" "$dest" 2>/dev/null || readlink "$dest" | grep -q "/scripts/hooks/$name\$"; }; then
            echo "install-hooks: $dest exists and is not scensim's: left alone (remove it, then run this again)" >&2
            continue
        fi
        rm -f "$dest"
    fi
    cat > "$dest" <<STUB
#!/bin/sh
$mark: runs the pushing worktree's scripts/hooks/$name
top=\$(git rev-parse --show-toplevel) || exit 1
hook="\$top/scripts/hooks/$name"
if [ -x "\$hook" ]; then exec "\$hook" "\$@"; fi
echo "$name: \$hook is missing (a checkout from before it): not checked" >&2
exit 0
STUB
    chmod +x "$dest"
    echo "install-hooks: $name (a stub running each worktree's scripts/hooks/$name)"
done
