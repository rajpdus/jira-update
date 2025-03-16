"""
Git commit analyzer for JIRA Update Hook.
"""

import re
import logging
from typing import List, Dict, Any, Set, Optional, Tuple
import os
from pathlib import Path
import fnmatch
import git

from ..utils.config import get_config

logger = logging.getLogger(__name__)


class GitAnalyzer:
    """Analyzes Git commits to extract JIRA ticket IDs and code changes."""

    def __init__(self, repo_path: Optional[str] = None):
        """
        Initialize the Git analyzer.
        
        Args:
            repo_path: Path to the Git repository. If None, uses the current directory.
        """
        self.repo_path = repo_path or os.getcwd()
        self.repo = git.Repo(self.repo_path)
        self.config = get_config()
        
        # Compile the regex pattern for extracting JIRA ticket IDs
        pattern = self.config.get('project', 'ticket_pattern', r'([A-Z]+-\d+)')
        self.ticket_pattern = re.compile(pattern)
        
        # Get ignore patterns
        self.ignore_patterns = self.config.get('git', 'ignore_patterns', [])
        
        # Get max commits to analyze
        self.max_commits = self.config.get('git', 'max_commits', 10)
        
        # Whether to analyze merge commits
        self.analyze_merges = self.config.get('git', 'analyze_merges', False)

    def extract_ticket_ids(self, commit_message: str) -> List[str]:
        """
        Extract JIRA ticket IDs from a commit message.
        
        Args:
            commit_message: The commit message to analyze.
            
        Returns:
            List of JIRA ticket IDs found in the commit message.
        """
        matches = self.ticket_pattern.findall(commit_message)
        
        # Filter by project keys if configured
        project_keys = self.config.get('project', 'keys', [])
        if project_keys:
            filtered_matches = []
            for match in matches:
                for key in project_keys:
                    if match.startswith(key + '-'):
                        filtered_matches.append(match)
                        break
            return filtered_matches
        
        return matches

    def should_ignore_file(self, file_path: str) -> bool:
        """
        Check if a file should be ignored based on configured patterns.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            True if the file should be ignored, False otherwise.
        """
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(file_path, pattern):
                return True
        return False

    def analyze_commit(self, commit_hash: str) -> Dict[str, Any]:
        """
        Analyze a single commit.
        
        Args:
            commit_hash: Hash of the commit to analyze.
            
        Returns:
            Dict containing commit analysis results.
        """
        commit = self.repo.commit(commit_hash)
        
        # Skip merge commits if configured
        if not self.analyze_merges and len(commit.parents) > 1:
            logger.debug(f"Skipping merge commit {commit_hash}")
            return {
                'hash': commit_hash,
                'is_merge': True,
                'ticket_ids': [],
                'changes': [],
                'summary': "Merge commit (skipped analysis)"
            }
        
        # Extract ticket IDs from commit message
        ticket_ids = self.extract_ticket_ids(commit.message)
        
        # Analyze changes
        changes = []
        for diff in commit.parents[0].diff(commit):
            # Skip ignored files
            if diff.a_path and self.should_ignore_file(diff.a_path):
                continue
            if diff.b_path and self.should_ignore_file(diff.b_path):
                continue
            
            change_type = self._get_change_type(diff)
            
            change = {
                'type': change_type,
                'path': diff.b_path or diff.a_path,
                'insertions': diff.stats.get('insertions', 0),
                'deletions': diff.stats.get('deletions', 0)
            }
            
            changes.append(change)
        
        # Generate summary
        summary = self._generate_summary(commit, changes)
        
        return {
            'hash': commit_hash,
            'author': f"{commit.author.name} <{commit.author.email}>",
            'date': commit.committed_datetime.isoformat(),
            'message': commit.message,
            'is_merge': len(commit.parents) > 1,
            'ticket_ids': ticket_ids,
            'changes': changes,
            'summary': summary
        }

    def _get_change_type(self, diff) -> str:
        """
        Get the type of change for a diff.
        
        Args:
            diff: GitPython diff object.
            
        Returns:
            String describing the change type.
        """
        if diff.new_file:
            return 'added'
        elif diff.deleted_file:
            return 'deleted'
        elif diff.renamed:
            return 'renamed'
        else:
            return 'modified'

    def _generate_summary(self, commit, changes: List[Dict[str, Any]]) -> str:
        """
        Generate a summary of the commit changes.
        
        Args:
            commit: GitPython commit object.
            changes: List of change dictionaries.
            
        Returns:
            Summary string.
        """
        total_files = len(changes)
        total_insertions = sum(change['insertions'] for change in changes)
        total_deletions = sum(change['deletions'] for change in changes)
        
        file_types = {}
        for change in changes:
            ext = os.path.splitext(change['path'])[1]
            if ext:
                file_types[ext] = file_types.get(ext, 0) + 1
        
        summary_lines = [
            f"Changed {total_files} files with {total_insertions} additions and {total_deletions} deletions.",
        ]
        
        # Add file type summary if there are multiple types
        if len(file_types) > 1:
            file_type_summary = ", ".join(f"{count} {ext}" for ext, count in file_types.items())
            summary_lines.append(f"File types: {file_type_summary}")
        
        return "\n".join(summary_lines)

    def analyze_push(self, base_ref: str, head_ref: str) -> Dict[str, Any]:
        """
        Analyze a push (multiple commits).
        
        Args:
            base_ref: Base reference (before push).
            head_ref: Head reference (after push).
            
        Returns:
            Dict containing push analysis results.
        """
        # Get the range of commits in the push
        rev_range = f"{base_ref}..{head_ref}"
        commits = list(self.repo.iter_commits(rev_range))
        
        # Limit the number of commits to analyze
        if len(commits) > self.max_commits:
            logger.warning(f"Limiting analysis to {self.max_commits} of {len(commits)} commits")
            commits = commits[:self.max_commits]
        
        # Analyze each commit
        commit_analyses = []
        all_ticket_ids = set()
        
        for commit in commits:
            analysis = self.analyze_commit(commit.hexsha)
            commit_analyses.append(analysis)
            all_ticket_ids.update(analysis['ticket_ids'])
        
        # Generate overall summary
        total_files_changed = set()
        total_insertions = 0
        total_deletions = 0
        
        for analysis in commit_analyses:
            for change in analysis['changes']:
                total_files_changed.add(change['path'])
                total_insertions += change['insertions']
                total_deletions += change['deletions']
        
        summary = f"Push contains {len(commits)} commits affecting {len(total_files_changed)} files " \
                 f"with {total_insertions} additions and {total_deletions} deletions."
        
        return {
            'base_ref': base_ref,
            'head_ref': head_ref,
            'commits': commit_analyses,
            'ticket_ids': list(all_ticket_ids),
            'summary': summary
        }

    def get_commit_url(self, commit_hash: str) -> Optional[str]:
        """
        Get the URL to view a commit in the web interface.
        
        Args:
            commit_hash: Hash of the commit.
            
        Returns:
            URL string or None if it cannot be determined.
        """
        try:
            # Try to get the remote URL
            remote_url = self.repo.remotes.origin.url
            
            # Handle different remote URL formats
            if remote_url.startswith('git@github.com:'):
                # GitHub SSH format
                repo_path = remote_url.split('git@github.com:')[1].replace('.git', '')
                return f"https://github.com/{repo_path}/commit/{commit_hash}"
            elif 'github.com' in remote_url:
                # GitHub HTTPS format
                repo_path = remote_url.split('github.com/')[1].replace('.git', '')
                return f"https://github.com/{repo_path}/commit/{commit_hash}"
            elif 'gitlab.com' in remote_url:
                # GitLab format
                repo_path = remote_url.split('gitlab.com/')[1].replace('.git', '')
                return f"https://gitlab.com/{repo_path}/-/commit/{commit_hash}"
            elif 'bitbucket.org' in remote_url:
                # Bitbucket format
                repo_path = remote_url.split('bitbucket.org/')[1].replace('.git', '')
                return f"https://bitbucket.org/{repo_path}/commits/{commit_hash}"
            else:
                logger.warning(f"Could not determine commit URL format for remote: {remote_url}")
                return None
        except Exception as e:
            logger.warning(f"Error determining commit URL: {e}")
            return None 