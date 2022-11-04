#!/bin/bash

echo "Updating Server..."
branch=$(git branch 2> /dev/null | sed -e '/^[^*]/d' -e 's/* \(.*\)/(\1)/')
echo Current branch is ${branch}
git pull

if hash py; then
    echo "Python detected under py alias"
elif hash python3; then
  alias py='python3'
  echo "Python3 detected"
elif hash python; then
  alias py='python'
  echo "Python detected"
fi

py -u main.py