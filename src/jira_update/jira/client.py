"""
JIRA API client for JIRA Update Hook.
"""

import logging
from typing import Dict, Any, List, Optional
import re

from jira import JIRA
from jira.exceptions import JIRAError

from ..utils.config import get_config

logger = logging.getLogger(__name__)


class JiraClient:
    """Client for interacting with JIRA API."""

    def __init__(self):
        """Initialize the JIRA client using configuration settings."""
        self.config = get_config()
        self.jira = self._create_jira_client()

    def _create_jira_client(self) -> JIRA:
        """
        Create a JIRA client instance.
        
        Returns:
            JIRA client instance.
            
        Raises:
            Exception: If JIRA client creation fails.
        """
        jira_config = self.config.get('jira')
        
        if not jira_config:
            raise Exception("JIRA configuration not found")
        
        url = jira_config.get('url')
        if not url:
            raise Exception("JIRA URL not specified in configuration")
        
        auth_method = jira_config.get('auth_method', 'basic')
        
        try:
            if auth_method == 'basic':
                username = jira_config.get('username')
                password = jira_config.get('password')
                
                if not username or not password:
                    raise Exception("JIRA username or password not specified in configuration")
                
                return JIRA(server=url, basic_auth=(username, password))
            
            elif auth_method == 'oauth':
                oauth_config = jira_config.get('oauth', {})
                
                access_token = oauth_config.get('access_token')
                access_token_secret = oauth_config.get('access_token_secret')
                consumer_key = oauth_config.get('consumer_key')
                key_cert = oauth_config.get('key_cert')
                
                if not all([access_token, access_token_secret, consumer_key, key_cert]):
                    raise Exception("Incomplete OAuth configuration for JIRA")
                
                oauth_dict = {
                    'access_token': access_token,
                    'access_token_secret': access_token_secret,
                    'consumer_key': consumer_key,
                    'key_cert': key_cert
                }
                
                return JIRA(server=url, oauth=oauth_dict)
            
            else:
                raise Exception(f"Unsupported JIRA authentication method: {auth_method}")
                
        except JIRAError as e:
            logger.error(f"JIRA authentication error: {e}")
            raise Exception(f"Failed to authenticate with JIRA: {e}")

    def get_issue(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """
        Get details of a JIRA issue.
        
        Args:
            issue_key: JIRA issue key (e.g., PROJECT-123).
            
        Returns:
            Dict containing issue details or None if the issue is not found.
        """
        try:
            issue = self.jira.issue(issue_key)
            
            # Extract relevant issue details
            issue_dict = {
                'key': issue.key,
                'summary': issue.fields.summary,
                'description': issue.fields.description,
                'status': issue.fields.status.name,
                'issue_type': issue.fields.issuetype.name,
                'assignee': issue.fields.assignee.displayName if issue.fields.assignee else None,
                'reporter': issue.fields.reporter.displayName if issue.fields.reporter else None,
                'priority': issue.fields.priority.name if hasattr(issue.fields, 'priority') and issue.fields.priority else None,
                'labels': issue.fields.labels,
                'components': [c.name for c in issue.fields.components] if hasattr(issue.fields, 'components') else [],
                'url': f"{self.config.get('jira', 'url')}/browse/{issue.key}"
            }
            
            logger.debug(f"Retrieved JIRA issue: {issue_key}")
            return issue_dict
            
        except JIRAError as e:
            if e.status_code == 404:
                logger.warning(f"JIRA issue not found: {issue_key}")
                return None
            else:
                logger.error(f"Error retrieving JIRA issue {issue_key}: {e}")
                return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving JIRA issue {issue_key}: {e}")
            return None

    def add_comment(self, issue_key: str, comment: str) -> bool:
        """
        Add a comment to a JIRA issue.
        
        Args:
            issue_key: JIRA issue key (e.g., PROJECT-123).
            comment: Comment text to add.
            
        Returns:
            True if the comment was added successfully, False otherwise.
        """
        try:
            self.jira.add_comment(issue_key, comment)
            logger.info(f"Added comment to JIRA issue: {issue_key}")
            return True
        except JIRAError as e:
            logger.error(f"Error adding comment to JIRA issue {issue_key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error adding comment to JIRA issue {issue_key}: {e}")
            return False

    def add_labels(self, issue_key: str, labels: List[str]) -> bool:
        """
        Add labels to a JIRA issue.
        
        Args:
            issue_key: JIRA issue key (e.g., PROJECT-123).
            labels: List of labels to add.
            
        Returns:
            True if the labels were added successfully, False otherwise.
        """
        try:
            issue = self.jira.issue(issue_key)
            
            # Get existing labels
            existing_labels = issue.fields.labels
            
            # Add new labels (avoid duplicates)
            new_labels = list(set(existing_labels + labels))
            
            # Update the issue
            issue.update(fields={'labels': new_labels})
            
            logger.info(f"Added labels to JIRA issue {issue_key}: {', '.join(labels)}")
            return True
        except JIRAError as e:
            logger.error(f"Error adding labels to JIRA issue {issue_key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error adding labels to JIRA issue {issue_key}: {e}")
            return False

    def get_labels_for_files(self, file_paths: List[str]) -> List[str]:
        """
        Get JIRA labels for file types based on configuration.
        
        Args:
            file_paths: List of file paths.
            
        Returns:
            List of labels to add.
        """
        labels_config = self.config.get('comment', 'labels', {})
        if not labels_config:
            return []
        
        labels = set()
        
        for file_path in file_paths:
            for pattern, label in labels_config.items():
                if re.match(pattern.replace('*', '.*'), file_path):
                    labels.add(label)
        
        return list(labels) 