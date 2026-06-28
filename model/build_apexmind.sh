#!/usr/bin/env bash
# Build (or rebuild) your own `apexmind` model from the Modelfile.
set -e
cd "$(dirname "$0")/.."
echo "Building apexmind from model/ApexMind.Modelfile ..."
ollama create apexmind -f model/ApexMind.Modelfile
echo
echo 'Done. Test it:  ollama run apexmind "what is your name and who made you?"'
echo "It also appears in the ApexMind chat model dropdown."
