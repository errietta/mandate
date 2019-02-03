
if [ ! -z "$TRAVIS_TAG" ] && [ "$TRAVIS_PULL_REQUEST" == "false" ]; then
    pip install poetry
    poetry publish --build -u $USERNAME -p $PASSWORD
else
  echo "Skipping deployment, as this is not a tagged commit"
fi


