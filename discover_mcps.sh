#!/bin/bash
# discover_mcps.sh
find mcps -maxdepth 1 -type d -exec test -f {}/pyproject.toml \; -print | sed 's|mcps/||' | sort > mcp_list.txt
echo "Found $(wc -l < mcp_list.txt) MCPs"
cat mcp_list.txt