"""
JIRA comment formatter for JIRA Update Hook.
"""

import logging
from typing import Dict, Any, List, Optional
import re
from datetime import datetime

from ..utils.config import get_config

logger = logging.getLogger(__name__)


class CommentFormatter:
    """Formats code analysis results into JIRA comments."""

    def __init__(self):
        """Initialize the comment formatter using configuration settings."""
        self.config = get_config()
        self.template = self.config.get('comment', 'template', '')
        
        # If no template is provided, use a default one
        if not self.template:
            self.template = """
*Code changes pushed by {author} on {date}*

*Commit:* {commit_hash}
*Message:* {commit_message}

h2. Summary of Changes
{summary}

h3. Files Changed
{files_changed}

[View full changes|{commit_url}]
"""

    def format_commit_comment(self, commit_analysis: Dict[str, Any]) -> str:
        """
        Format a JIRA comment for a single commit.
        
        Args:
            commit_analysis: Dict containing commit analysis.
            
        Returns:
            Formatted comment string.
        """
        # Extract variables for template
        commit_hash = commit_analysis.get('hash', '')
        short_hash = commit_hash[:7] if commit_hash else ''
        commit_message = commit_analysis.get('message', '').strip()
        author = commit_analysis.get('author', '').split('<')[0].strip()
        
        # Format date
        date_str = commit_analysis.get('date', '')
        try:
            date_obj = datetime.fromisoformat(date_str)
            date = date_obj.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            date = date_str
        
        # Get summary
        if 'detailed_summary' in commit_analysis:
            summary = commit_analysis['detailed_summary']
        elif 'ai_summary' in commit_analysis:
            summary = commit_analysis['ai_summary']
        else:
            summary = commit_analysis.get('summary', 'No summary available.')
        
        # Format files changed
        files_changed = self._format_files_changed(commit_analysis)
        
        # Get commit URL
        commit_url = commit_analysis.get('commit_url', '#')
        
        # Replace template variables
        comment = self.template
        comment = comment.replace('{commit_hash}', short_hash)
        comment = comment.replace('{commit_message}', commit_message)
        comment = comment.replace('{author}', author)
        comment = comment.replace('{date}', date)
        comment = comment.replace('{summary}', summary)
        comment = comment.replace('{files_changed}', files_changed)
        comment = comment.replace('{commit_url}', commit_url)
        
        return comment

    def format_push_comment(self, push_analysis: Dict[str, Any]) -> str:
        """
        Format a JIRA comment for a push (multiple commits).
        
        Args:
            push_analysis: Dict containing push analysis.
            
        Returns:
            Formatted comment string.
        """
        commits = push_analysis.get('commits', [])
        if not commits:
            return "No commits to analyze."
        
        # If there's only one commit, use the single commit formatter
        if len(commits) == 1:
            return self.format_commit_comment(commits[0])
        
        # For multiple commits, create a summary comment
        comment_lines = []
        
        # Add header
        comment_lines.append("*Code changes pushed with multiple commits*")
        comment_lines.append("")
        
        # Add push summary
        comment_lines.append("h2. Push Summary")
        comment_lines.append(push_analysis.get('summary', 'No summary available.'))
        comment_lines.append("")
        
        # Add commit list
        comment_lines.append("h3. Commits")
        for commit in commits:
            hash_short = commit.get('hash', '')[:7]
            message = commit.get('message', '').split('\n')[0]  # First line only
            author = commit.get('author', '').split('<')[0].strip()
            
            # Format date
            date_str = commit.get('date', '')
            try:
                date_obj = datetime.fromisoformat(date_str)
                date = date_obj.strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                date = date_str
            
            commit_url = commit.get('commit_url', '#')
            
            comment_lines.append(f"* [{hash_short}|{commit_url}] - {message} - by {author} on {date}")
        
        # Add detailed file changes
        comment_lines.append("")
        comment_lines.append("h3. File Changes")
        
        # Collect all changed files
        all_files = set()
        for commit in commits:
            for change in commit.get('changes', []):
                all_files.add(change.get('path', ''))
        
        # List files
        for file_path in sorted(all_files):
            comment_lines.append(f"* {file_path}")
        
        return "\n".join(comment_lines)

    def _format_files_changed(self, commit_analysis: Dict[str, Any]) -> str:
        """
        Format the list of files changed in a commit.
        
        Args:
            commit_analysis: Dict containing commit analysis.
            
        Returns:
            Formatted string of files changed.
        """
        file_lines = []
        
        # Check if we have detailed file analyses
        if 'file_analyses' in commit_analysis:
            for file in commit_analysis['file_analyses']:
                path = file.get('path', '')
                summary = file.get('summary', '')
                file_lines.append(f"* {path} - {summary}")
        else:
            # Fall back to basic changes list
            for change in commit_analysis.get('changes', []):
                path = change.get('path', '')
                change_type = change.get('type', 'modified')
                insertions = change.get('insertions', 0)
                deletions = change.get('deletions', 0)
                
                if change_type == 'added':
                    file_lines.append(f"* {path} - Added ({insertions} lines)")
                elif change_type == 'deleted':
                    file_lines.append(f"* {path} - Deleted ({deletions} lines)")
                elif change_type == 'renamed':
                    file_lines.append(f"* {path} - Renamed")
                else:
                    file_lines.append(f"* {path} - Modified (+{insertions}, -{deletions})")
        
        return "\n".join(file_lines) 