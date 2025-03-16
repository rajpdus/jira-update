"""
Main module for JIRA Update Hook.
"""

import os
import sys
import logging
import argparse
from typing import List, Dict, Any, Optional

from .git.analyzer import GitAnalyzer
from .jira.client import JiraClient
from .jira.formatter import CommentFormatter
from .analysis.code_analyzer import CodeAnalyzer
from .utils.config import get_config
from .utils.logging import setup_logging

logger = logging.getLogger(__name__)


def process_push(base_ref: str, head_ref: str, repo_path: Optional[str] = None) -> bool:
    """
    Process a Git push event.
    
    Args:
        base_ref: Base reference (before push).
        head_ref: Head reference (after push).
        repo_path: Path to the Git repository. If None, uses the current directory.
        
    Returns:
        True if successful, False otherwise.
    """
    try:
        # Set up logging
        setup_logging()
        
        logger.info(f"Processing push: {base_ref} -> {head_ref}")
        
        # Initialize components
        git_analyzer = GitAnalyzer(repo_path)
        code_analyzer = CodeAnalyzer()
        jira_client = JiraClient()
        comment_formatter = CommentFormatter()
        
        # Analyze the push
        push_analysis = git_analyzer.analyze_push(base_ref, head_ref)
        logger.info(f"Found {len(push_analysis['ticket_ids'])} JIRA tickets in commits")
        
        # If no tickets found, exit
        if not push_analysis['ticket_ids']:
            logger.info("No JIRA tickets found in commits. Exiting.")
            return True
        
        # Add commit URLs
        for commit in push_analysis['commits']:
            commit['commit_url'] = git_analyzer.get_commit_url(commit['hash'])
        
        # Enhance analysis with code insights
        enhanced_commits = []
        for commit in push_analysis['commits']:
            enhanced_commit = code_analyzer.analyze_changes(commit)
            enhanced_commits.append(enhanced_commit)
        
        push_analysis['commits'] = enhanced_commits
        
        # Process each ticket
        for ticket_id in push_analysis['ticket_ids']:
            # Get ticket details
            ticket = jira_client.get_issue(ticket_id)
            if not ticket:
                logger.warning(f"Could not find JIRA ticket: {ticket_id}")
                continue
            
            # Format comment
            comment = comment_formatter.format_push_comment(push_analysis)
            
            # Add comment to ticket
            success = jira_client.add_comment(ticket_id, comment)
            if not success:
                logger.error(f"Failed to add comment to JIRA ticket: {ticket_id}")
                continue
            
            # Add labels if configured
            if get_config().get('comment', 'add_labels', False):
                # Collect all file paths
                file_paths = []
                for commit in push_analysis['commits']:
                    for change in commit.get('changes', []):
                        file_paths.append(change.get('path', ''))
                
                # Get labels for files
                labels = jira_client.get_labels_for_files(file_paths)
                if labels:
                    jira_client.add_labels(ticket_id, labels)
            
            logger.info(f"Successfully updated JIRA ticket: {ticket_id}")
        
        logger.info("Push processing completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error processing push: {e}", exc_info=True)
        return False


def main():
    """Main entry point for the command-line interface."""
    parser = argparse.ArgumentParser(description='JIRA Update Hook')
    parser.add_argument('--config', help='Path to configuration file')
    parser.add_argument('--base-ref', help='Base reference (before push)')
    parser.add_argument('--head-ref', help='Head reference (after push)')
    parser.add_argument('--repo-path', help='Path to Git repository')
    parser.add_argument('--log-level', choices=['debug', 'info', 'warning', 'error'], 
                        help='Logging level')
    parser.add_argument('--log-file', help='Path to log file')
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.log_level, args.log_file)
    
    # Process push
    if args.base_ref and args.head_ref:
        success = process_push(args.base_ref, args.head_ref, args.repo_path)
        sys.exit(0 if success else 1)
    else:
        logger.error("Missing required arguments: --base-ref and --head-ref")
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main() 