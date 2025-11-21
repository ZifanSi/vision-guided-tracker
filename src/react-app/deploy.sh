#!/usr/bin/env sh

# Navigate to the same directory as this script
cd "$(dirname "$0")"

yarn build || exit 1

ssh rocam@100.117.52.117 "rm -r ~/frontend"
scp -r ./dist/* rocam@100.117.52.117:~/frontend