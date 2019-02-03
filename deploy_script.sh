 if ([ "$TRAVIS_BRANCH" == "master" ] || [ ! -z "$TRAVIS_TAG" ]) &&
    [ "$TRAVIS_PULL_REQUEST" == "false" ]; then
    pip install poetry
    poetry publish
  else
    echo "Skipping deployment, as this is not a tagged commit"
  fi


