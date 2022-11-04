#!/bin/bash

git pull
#python3 main.py

if hash py; then
    echo "Python detected under py alias"
elif hash python3; then
  alias py='python3'
elif hash python; then
  alias py='python'
fi

py -u main.py