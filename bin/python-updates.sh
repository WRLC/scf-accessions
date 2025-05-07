#!/bin/bash

# Ensure you are on the correct branch or create one
# For example:
BRANCH_NAME="update/$(date +%Y-%m-%d)"
if git rev-parse --verify "$BRANCH_NAME" >/dev/null 2>&1; then
  echo "Switching to existing branch $BRANCH_NAME."
  git checkout "$BRANCH_NAME"
else
  echo "Creating and switching to new branch $BRANCH_NAME."
  git checkout -b "$BRANCH_NAME"
fi

# Attempt to synchronize poetry.lock with pyproject.toml first.
# This can help resolve inconsistencies before checking for outdated packages.
echo "Attempting to synchronize poetry.lock with pyproject.toml using 'poetry lock'..."
# Removed --no-update flag for broader compatibility with older Poetry versions
poetry_lock_output=$(poetry lock 2>&1)
poetry_lock_status=$?

if [ $poetry_lock_status -ne 0 ]; then
  echo "Error: 'poetry lock' command failed. Poetry reported:"
  echo "$poetry_lock_output"
  echo "Please resolve the issue with your Poetry environment or pyproject.toml and try again."
  exit 1 # Exit the script as we cannot proceed if locking fails
fi
echo "'poetry lock' completed successfully."
echo ""


# Get outdated packages.
# First, execute poetry show --outdated and capture its combined output and exit status.
echo "Checking for outdated packages using 'poetry show --outdated'..."
poetry_show_output=$(poetry show --outdated 2>&1)
poetry_show_status=$?

# Check if poetry show --outdated command failed
if [ $poetry_show_status -ne 0 ]; then
  echo "Error: 'poetry show --outdated' command failed. Poetry reported:"
  echo "$poetry_show_output" # Display the actual error message from Poetry
  echo "Please resolve the issue with your Poetry environment or pyproject.toml and try again."
  # Additional check: if the output also contains "No dependencies to install or update", it might be a specific kind of error
  if echo "$poetry_show_output" | grep -q "No dependencies to install or update"; then
    echo "Note: The error output also contained 'No dependencies to install or update', which might indicate a specific resolution state."
  fi
  exit 1 # Exit the script as we cannot proceed
fi

# If poetry show --outdated was successful, parse its output (which is in $poetry_show_output)
# This awk command filters out headers and other non-package lines.
# It also tries to filter out the "No applicable" messages that can sometimes appear on stdout even on success.
outdated_packages=$(echo "$poetry_show_output" | awk 'NF > 0 && $1 !~ /^[Pp]ackage$|^---|Fetching|No applicable|Solving dependencies/ {print $1}')


if [ -z "$outdated_packages" ]; then
  echo "No packages to update."
  # Check if the original output contained "No applicable" which means poetry itself said nothing to update
  if echo "$poetry_show_output" | grep -q "No applicable"; then
    echo "(Poetry indicated no applicable updates were found.)"
  fi
  exit 0
fi

echo "The following packages will be updated:"
echo "$outdated_packages"
echo ""

# Loop through each outdated package and update it
for package_name in $outdated_packages; do
  echo "Updating $package_name..."
  # It's good to capture the output of the update command as well for debugging
  update_output=$(poetry update "$package_name" 2>&1)
  update_status=$?

  if [ $update_status -ne 0 ]; then
    echo "Error updating $package_name. Poetry reported:"
    echo "$update_output"
    echo "Skipping $package_name."
    continue
  fi
  echo "Successfully updated $package_name."
  echo "$update_output" # Show output from successful update
  echo ""


  echo "Updating requirements.txt..."
  # Consider using 'poetry export' for generating requirements.txt, as it's more idiomatic with Poetry:
  # poetry export -f requirements.txt --output requirements.txt --without-hashes
  # If you need dev dependencies:
  # poetry export -f requirements.txt --output requirements.txt --with dev --without-hashes
  poetry run pip freeze > requirements.txt

  echo "Staging changes for $package_name..."
  # Ensure poetry.lock is always added, as 'poetry update' modifies it.
  # pyproject.toml might not change if only lock file is updated.
  git add pyproject.toml poetry.lock requirements.txt

  # Check if there are any staged changes before committing
  # Specifically check poetry.lock as it's the primary indicator of a successful poetry update
  if ! git diff --staged --quiet poetry.lock; then
    echo "Committing changes for $package_name..."
    git commit -m "Update $package_name"

    if [ $? -ne 0 ]; then
      echo "Error committing changes for $package_name. Please check git status."
      # It might be better to not exit here, but to collect errors and report at the end,
      # or allow the script to continue with other packages.
      # For now, keeping original behavior of exiting on commit error.
      exit 1
    fi
    echo "$package_name updated and committed."
  else
    echo "No changes to commit for $package_name (poetry.lock unchanged, or update failed to resolve substantively)."
  fi
  echo ""
done

echo "All packages processed."
# You can add your git push command here if desired
# Ensure you are pushing the correct branch name
# git push -u origin "$BRANCH_NAME"