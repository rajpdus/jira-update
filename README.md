# JIRA Update Hook

A Git hook system that analyzes code changes, extracts JIRA ticket references from commit messages, and automatically creates informative comments on the corresponding JIRA tickets.

## Features

- Extracts JIRA ticket IDs from commit messages
- Analyzes code changes to generate meaningful summaries
- Fetches ticket details from JIRA to understand context
- Posts detailed comments to JIRA tickets automatically
- Configurable for different projects and workflows

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/jira-update.git
   cd jira-update
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Configure your JIRA credentials and project settings:
   ```
   cp config.example.yaml config.yaml
   # Edit config.yaml with your settings
   ```

4. Install the Git hook in your repository:
   ```
   python install_hook.py --target=/path/to/your/repo
   ```

## Configuration

The `config.yaml` file contains all necessary configuration:

- JIRA credentials and API endpoint
- Project-specific settings
- Comment templates
- Code analysis preferences

See `config.example.yaml` for a detailed example.

## Usage

Once installed, the hook will automatically:

1. Extract JIRA ticket IDs from your commit messages (format: PROJECT-123)
2. Analyze the code changes in your commits
3. Generate a summary of the changes
4. Post the summary as a comment on the corresponding JIRA ticket

## Development

See `implementation.md` for the detailed implementation plan and architecture.

## License

MIT
