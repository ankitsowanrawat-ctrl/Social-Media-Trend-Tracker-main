#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies from dashboard/requirements.txt
pip install -r dashboard/requirements.txt

# Download required NLTK data packages
python -c "import nltk; nltk.download('stopwords'); nltk.download('vader_lexicon'); nltk.download('punkt'); nltk.download('wordnet'); nltk.download('averaged_perceptron_tagger')"
