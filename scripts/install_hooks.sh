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
# a checkout from before the hook (or a branch without it): a push to main is refused, since
# it could not be checked (243); any other ref goes
while read -r lref lsha rref rsha; do
    case "\$rref" in refs/heads/main)
        case "\$lsha" in 0000000000000000000000000000000000000000) ;; *)
            echo "$name: refusing to push to main: this checkout has no scripts/hooks/$name, so the pins cannot be checked (push from a checkout of main)" >&2
            exit 1;;
        esac;;
    esac
done
exit 0
STUB
    chmod +x "$dest"
    echo "install-hooks: $name (a stub running each worktree's scripts/hooks/$name)"
done
