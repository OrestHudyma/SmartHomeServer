#!/bin/bash
shopt -s expand_aliases

echo "Updating Server..."
branch=$(git branch 2> /dev/null | sed -e '/^[^*]/d' -e 's/* \(.*\)/(\1)/')
echo Current branch is ${branch}
git pull

if hash pyt; then
    echo "Python detected under py alias"
elif hash python3; then
  alias pyt='python3'
  echo "Python3 detected"
elif hash python; then
  alias pyt='python'
  echo "Python detected"
fi

pyt -u main.py