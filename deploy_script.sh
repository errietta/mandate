echo $TRAVIS_BRANCH 
echo $TRAVIS_PULL_REQUEST
echo $TRAVIS_TAG

if ([ "$TRAVIS_BRANCH" == "master" ] && [ ! -z "$TRAVIS_TAG" ]) &&
    [ "$TRAVIS_PULL_REQUEST" == "false" ]; then
    pip install poetry
    poetry publish --build -u $USERNAME -p $PASSWORD
  else
    echo "Skipping deployment, as this is not a tagged commit"
  fi


