#!/usr/bin/env python3
"""
Hook installation script for JIRA Update Hook.
"""

import os
import sys
import argparse
import shutil
import stat
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)

logger = logging.getLogger(__name__)

# Template for the post-push hook script
POST_PUSH_HOOK_TEMPLATE = """#!/bin/sh
# JIRA Update Hook - Post-push hook

# Get the previous and current HEAD
previous_head="$1"
current_head="$2"

# Path to the Python executable (modify if needed)
PYTHON_EXEC="{python_exec}"

# Path to the JIRA Update Hook script
HOOK_SCRIPT="{hook_script}"

# Path to the configuration file
CONFIG_FILE="{config_file}"

# Run the hook
$PYTHON_EXEC $HOOK_SCRIPT --config $CONFIG_FILE --base-ref $previous_head --head-ref $current_head --repo-path "$(pwd)"

# Exit with the script's exit code
exit $?
"""

# Template for the post-commit hook script
POST_COMMIT_HOOK_TEMPLATE = """#!/bin/sh
# JIRA Update Hook - Post-commit hook

# Get the commit hash
commit_hash=$(git rev-parse HEAD)
previous_hash=$(git rev-parse HEAD~1)

# Path to the Python executable (modify if needed)
PYTHON_EXEC="{python_exec}"

# Path to the JIRA Update Hook script
HOOK_SCRIPT="{hook_script}"

# Path to the configuration file
CONFIG_FILE="{config_file}"

# Run the hook
$PYTHON_EXEC $HOOK_SCRIPT --config $CONFIG_FILE --base-ref $previous_hash --head-ref $commit_hash --repo-path "$(pwd)"

# Exit with the script's exit code
exit $?
"""


def install_hook(target_repo: str, hook_type: str = 'post-push', config_file: str = 'config.yaml') -> bool:
    """
    Install the JIRA Update Hook in a Git repository.
    
    Args:
        target_repo: Path to the target Git repository.
        hook_type: Type of hook to install ('post-push' or 'post-commit').
        config_file: Path to the configuration file.
        
    Returns:
        True if successful, False otherwise.
    """
    try:
        # Validate target repository
        target_repo_path = Path(target_repo).resolve()
        git_dir = target_repo_path / '.git'
        
        if not git_dir.exists():
            logger.error(f"Not a Git repository: {target_repo_path}")
            return False
        
        # Create hooks directory if it doesn't exist
        hooks_dir = git_dir / 'hooks'
        hooks_dir.mkdir(exist_ok=True)
        
        # Determine hook file path
        if hook_type == 'post-push':
            hook_file = hooks_dir / 'post-push'
            template = POST_PUSH_HOOK_TEMPLATE
        elif hook_type == 'post-commit':
            hook_file = hooks_dir / 'post-commit'
            template = POST_COMMIT_HOOK_TEMPLATE
        else:
            logger.error(f"Unsupported hook type: {hook_type}")
            return False
        
        # Get the path to the Python executable
        python_exec = sys.executable
        
        # Get the path to the hook script
        script_dir = Path(__file__).parent
        hook_script = script_dir / 'src' / 'jira_update' / 'main.py'
        hook_script = hook_script.resolve()
        
        # Get the path to the configuration file
        config_file_path = Path(config_file).resolve()
        
        # Create the hook script
        hook_content = template.format(
            python_exec=python_exec,
            hook_script=hook_script,
            config_file=config_file_path
        )
        
        with open(hook_file, 'w') as f:
            f.write(hook_content)
        
        # Make the hook executable
        os.chmod(hook_file, os.stat(hook_file).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        
        logger.info(f"Successfully installed {hook_type} hook in {target_repo_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error installing hook: {e}")
        return False


def main():
    """Main entry point for the command-line interface."""
    parser = argparse.ArgumentParser(description='JIRA Update Hook Installer')
    parser.add_argument('--target', required=True, help='Path to the target Git repository')
    parser.add_argument('--hook-type', choices=['post-push', 'post-commit'], default='post-push',
                        help='Type of hook to install')
    parser.add_argument('--config', default='config.yaml', help='Path to the configuration file')
    
    args = parser.parse_args()
    
    # Install the hook
    success = install_hook(args.target, args.hook_type, args.config)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main() 