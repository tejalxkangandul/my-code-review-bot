import os
import subprocess
import requests
from openai import OpenAI

# 1. --- Configuration ---
# Get secrets and context from environment variables
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")        # This is our PAT
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY")
PR_NUMBER = os.environ.get("PR_NUMBER")
BASE_REF = os.environ.get("BASE_REF")              # The target branch (e.g., 'main')

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# 2. --- Helper Functions ---

def get_pr_diff():
    """
    Fetches the diff of the pull request using git commands.
    """
    try:
        # We need to fetch the base branch to be able to compare
        print(f"Fetching base branch: {BASE_REF}")
        subprocess.run(['git', 'fetch', 'origin', BASE_REF], check=True, capture_output=True, text=True)

        # Get the diff between the base branch and the current HEAD
        # 'origin/main...HEAD'
        diff_command = ['git', 'diff', f'origin/{BASE_REF}...HEAD']
        print(f"Running diff command: {' '.join(diff_command)}")
        result = subprocess.run(diff_command, check=True, capture_output=True, text=True)

        if not result.stdout:
            print("No diff found. Exiting.")
            return None

        print(f"Diff found (first 500 chars): {result.stdout[:500]}...")
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error getting git diff: {e.stderr}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred in get_pr_diff: {e}")
        return None

def get_ai_review(diff):
    """
    Sends the diff to the AI and gets a review.
    """
    if not diff:
        return "No code changes detected."

    # This is the prompt. You can customize it heavily.
    system_prompt = """
    You are an expert code review bot. Your task is to review a pull request based on the provided code diff.

    Please provide your review in the following format:
    1.  **Summary:** A brief, one-sentence summary of the changes.
    2.  **Review:** A bulleted list of specific feedback. Focus on potential bugs, style issues, security vulnerabilities, or performance improvements.
    3.  **Overall:** A final "Looks good to me!" or "Needs changes."

    Keep your review concise and constructive. If there are no issues, just say "Looks good to me!".
    """

    user_prompt = f"Please review the following code diff:\n\n```diff\n{diff}\n```"

    try:
        print("Sending prompt to OpenAI...")
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Using a fast and cheap model. Change to "gpt-4" for more power.
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        print("OpenAI response received.")
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling OpenAI: {e}")
        return f"Error: Unable to get AI review. {e}"

def post_github_comment(review_text):
    """
    Posts the AI's review as a comment on the GitHub PR.
    """
    api_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues/{PR_NUMBER}/comments"

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }

    body = {
        "body": "### 🤖 AI Code Review\n\n" + review_text
    }

    try:
        print(f"Posting comment to {api_url}...")
        response = requests.post(api_url, headers=headers, json=body)
        response.raise_for_status() # Raises an HTTPError for bad responses
        print(f"Successfully posted comment to PR #{PR_NUMBER}.")
    except requests.exceptions.HTTPError as e:
        print(f"Error posting comment: {e.response.status_code} {e.response.text}")
    except Exception as e:
        print(f"An unexpected error occurred in post_github_comment: {e}")

# 3. --- Main Execution ---

if __name__ == "__main__":
    if not all([OPENAI_API_KEY, GITHUB_TOKEN, GITHUB_REPOSITORY, PR_NUMBER, BASE_REF]):
        print("Error: Missing one or more required environment variables.")
    else:
        print("--- Starting AI Code Review ---")

        print("Fetching PR diff...")
        diff = get_pr_diff()

        if diff:
            print("Diff fetched. Getting AI review...")
            review = get_ai_review(diff)

            print("AI review received. Posting to GitHub...")
            post_github_comment(review)

        print("--- AI Code Review Finished ---")
