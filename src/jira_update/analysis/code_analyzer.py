"""
Code analyzer for JIRA Update Hook.
"""

import os
import logging
from typing import Dict, Any, List, Optional, Set
import fnmatch
import re
from pathlib import Path
import subprocess
from pygments import lexers
from pygments.util import ClassNotFound

from ..utils.config import get_config

logger = logging.getLogger(__name__)


class CodeAnalyzer:
    """Analyzes code changes to generate meaningful summaries."""

    def __init__(self):
        """Initialize the code analyzer using configuration settings."""
        self.config = get_config()
        self.detail_level = self.config.get('analysis', 'detail_level', 'detailed')
        self.max_files = self.config.get('analysis', 'max_files', 5)
        self.max_changes_per_file = self.config.get('analysis', 'max_changes_per_file', 3)
        self.include_snippets = self.config.get('analysis', 'include_snippets', True)
        self.max_snippet_length = self.config.get('analysis', 'max_snippet_length', 100)
        
        # Optional AI-powered summary
        self.use_ai_summary = self.config.get('advanced', 'use_ai_summary', False)
        if self.use_ai_summary:
            try:
                import openai
                api_key_env = self.config.get('advanced', 'openai', {}).get('api_key_env', 'OPENAI_API_KEY')
                openai.api_key = os.environ.get(api_key_env)
                self.openai_model = self.config.get('advanced', 'openai', {}).get('model', 'gpt-3.5-turbo')
                self.openai_available = bool(openai.api_key)
                if not self.openai_available:
                    logger.warning(f"OpenAI API key not found in environment variable {api_key_env}")
            except ImportError:
                logger.warning("OpenAI module not available. AI-powered summaries disabled.")
                self.openai_available = False
        else:
            self.openai_available = False

    def analyze_changes(self, commit_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze code changes in a commit.
        
        Args:
            commit_analysis: Dict containing commit analysis from GitAnalyzer.
            
        Returns:
            Dict with enhanced analysis including code insights.
        """
        # Make a copy to avoid modifying the original
        enhanced_analysis = commit_analysis.copy()
        
        # Skip if no changes
        if not commit_analysis.get('changes'):
            return enhanced_analysis
        
        # Get the most significant files
        significant_files = self._get_significant_files(commit_analysis['changes'])
        
        # Analyze each significant file
        file_analyses = []
        for file_info in significant_files:
            file_analysis = self._analyze_file(file_info, commit_analysis['hash'])
            if file_analysis:
                file_analyses.append(file_analysis)
        
        # Generate detailed summary
        detailed_summary = self._generate_detailed_summary(file_analyses, commit_analysis)
        
        # Add AI-powered summary if enabled
        if self.use_ai_summary and self.openai_available:
            ai_summary = self._generate_ai_summary(file_analyses, commit_analysis)
            if ai_summary:
                enhanced_analysis['ai_summary'] = ai_summary
        
        # Update the analysis
        enhanced_analysis['file_analyses'] = file_analyses
        enhanced_analysis['detailed_summary'] = detailed_summary
        
        return enhanced_analysis

    def _get_significant_files(self, changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Get the most significant files from the changes.
        
        Args:
            changes: List of change dictionaries.
            
        Returns:
            List of significant file dictionaries.
        """
        # Sort changes by significance (total lines changed)
        sorted_changes = sorted(
            changes,
            key=lambda x: x.get('insertions', 0) + x.get('deletions', 0),
            reverse=True
        )
        
        # Limit to max_files
        return sorted_changes[:self.max_files]

    def _analyze_file(self, file_info: Dict[str, Any], commit_hash: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a single file change.
        
        Args:
            file_info: Dict containing file change information.
            commit_hash: Hash of the commit.
            
        Returns:
            Dict with file analysis or None if analysis fails.
        """
        file_path = file_info['path']
        change_type = file_info['type']
        
        # Skip analysis for deleted files
        if change_type == 'deleted':
            return {
                'path': file_path,
                'type': change_type,
                'language': self._detect_language(file_path),
                'summary': "File was deleted",
                'insertions': 0,
                'deletions': file_info.get('deletions', 0)
            }
        
        # Get file language
        language = self._detect_language(file_path)
        
        # Get the diff for the file
        diff_output = self._get_file_diff(file_path, commit_hash)
        if not diff_output:
            return None
        
        # Parse the diff to extract changed sections
        changed_sections = self._parse_diff(diff_output)
        
        # Limit to most significant changes
        if len(changed_sections) > self.max_changes_per_file:
            changed_sections = changed_sections[:self.max_changes_per_file]
        
        # Generate file summary
        file_summary = self._generate_file_summary(file_path, change_type, changed_sections, language)
        
        return {
            'path': file_path,
            'type': change_type,
            'language': language,
            'summary': file_summary,
            'changed_sections': changed_sections,
            'insertions': file_info.get('insertions', 0),
            'deletions': file_info.get('deletions', 0)
        }

    def _detect_language(self, file_path: str) -> str:
        """
        Detect the programming language of a file.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            String representing the language.
        """
        try:
            lexer = lexers.get_lexer_for_filename(file_path)
            return lexer.name
        except ClassNotFound:
            # Try to guess based on extension
            ext = os.path.splitext(file_path)[1].lower()
            language_map = {
                '.py': 'Python',
                '.js': 'JavaScript',
                '.ts': 'TypeScript',
                '.jsx': 'React JSX',
                '.tsx': 'React TSX',
                '.java': 'Java',
                '.c': 'C',
                '.cpp': 'C++',
                '.cs': 'C#',
                '.go': 'Go',
                '.rb': 'Ruby',
                '.php': 'PHP',
                '.html': 'HTML',
                '.css': 'CSS',
                '.scss': 'SCSS',
                '.md': 'Markdown',
                '.json': 'JSON',
                '.xml': 'XML',
                '.yaml': 'YAML',
                '.yml': 'YAML',
                '.sql': 'SQL',
                '.sh': 'Shell',
                '.bat': 'Batch',
                '.ps1': 'PowerShell'
            }
            return language_map.get(ext, 'Unknown')

    def _get_file_diff(self, file_path: str, commit_hash: str) -> Optional[str]:
        """
        Get the diff for a file in a commit.
        
        Args:
            file_path: Path to the file.
            commit_hash: Hash of the commit.
            
        Returns:
            String containing the diff output or None if it fails.
        """
        try:
            # Get the diff for the file
            cmd = ['git', 'show', '--format=', '--patch', f'{commit_hash}^..{commit_hash}', '--', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Error getting diff for {file_path} in commit {commit_hash}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting diff for {file_path}: {e}")
            return None

    def _parse_diff(self, diff_output: str) -> List[Dict[str, Any]]:
        """
        Parse a diff output to extract changed sections.
        
        Args:
            diff_output: String containing the diff output.
            
        Returns:
            List of dictionaries containing changed section information.
        """
        changed_sections = []
        
        # Regular expression to find diff hunks
        hunk_pattern = re.compile(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@(.*)')
        
        lines = diff_output.split('\n')
        current_hunk = None
        hunk_lines = []
        
        for line in lines:
            # Check for hunk header
            match = hunk_pattern.match(line)
            if match:
                # Save previous hunk if exists
                if current_hunk and hunk_lines:
                    snippet = '\n'.join(hunk_lines)
                    if len(snippet) > self.max_snippet_length:
                        snippet = snippet[:self.max_snippet_length] + '...'
                    
                    changed_sections.append({
                        'old_start': current_hunk[0],
                        'old_count': current_hunk[1],
                        'new_start': current_hunk[2],
                        'new_count': current_hunk[3],
                        'header': current_hunk[4].strip(),
                        'snippet': snippet if self.include_snippets else None
                    })
                
                # Start new hunk
                old_start = int(match.group(1))
                old_count = int(match.group(2)) if match.group(2) else 1
                new_start = int(match.group(3))
                new_count = int(match.group(4)) if match.group(4) else 1
                header = match.group(5)
                
                current_hunk = (old_start, old_count, new_start, new_count, header)
                hunk_lines = []
            elif current_hunk:
                # Add line to current hunk
                if line.startswith('+') or line.startswith('-') or line.startswith(' '):
                    hunk_lines.append(line)
        
        # Add the last hunk
        if current_hunk and hunk_lines:
            snippet = '\n'.join(hunk_lines)
            if len(snippet) > self.max_snippet_length:
                snippet = snippet[:self.max_snippet_length] + '...'
            
            changed_sections.append({
                'old_start': current_hunk[0],
                'old_count': current_hunk[1],
                'new_start': current_hunk[2],
                'new_count': current_hunk[3],
                'header': current_hunk[4].strip(),
                'snippet': snippet if self.include_snippets else None
            })
        
        return changed_sections

    def _generate_file_summary(self, file_path: str, change_type: str, 
                              changed_sections: List[Dict[str, Any]], language: str) -> str:
        """
        Generate a summary for a file change.
        
        Args:
            file_path: Path to the file.
            change_type: Type of change (added, modified, deleted, renamed).
            changed_sections: List of changed sections.
            language: Programming language of the file.
            
        Returns:
            Summary string.
        """
        file_name = os.path.basename(file_path)
        
        if change_type == 'added':
            return f"Added new {language} file with {sum(section['new_count'] for section in changed_sections)} lines"
        
        elif change_type == 'deleted':
            return f"Deleted {language} file"
        
        elif change_type == 'renamed':
            return f"Renamed file to {file_name}"
        
        else:  # modified
            total_additions = sum(len([l for l in section.get('snippet', '').split('\n') if l.startswith('+')]) 
                                for section in changed_sections)
            total_deletions = sum(len([l for l in section.get('snippet', '').split('\n') if l.startswith('-')]) 
                               for section in changed_sections)
            
            if self.detail_level == 'basic':
                return f"Modified {language} file with {total_additions} additions and {total_deletions} deletions"
            
            # Try to identify what was changed
            function_changes = []
            for section in changed_sections:
                header = section.get('header', '')
                if header:
                    function_changes.append(header)
            
            if function_changes:
                functions_str = ', '.join(function_changes[:3])
                if len(function_changes) > 3:
                    functions_str += f" and {len(function_changes) - 3} more"
                return f"Modified {language} file: changes in {functions_str}"
            
            return f"Modified {language} file with {total_additions} additions and {total_deletions} deletions in {len(changed_sections)} sections"

    def _generate_detailed_summary(self, file_analyses: List[Dict[str, Any]], 
                                  commit_analysis: Dict[str, Any]) -> str:
        """
        Generate a detailed summary of the code changes.
        
        Args:
            file_analyses: List of file analysis dictionaries.
            commit_analysis: Dict containing commit analysis.
            
        Returns:
            Detailed summary string.
        """
        if not file_analyses:
            return "No significant code changes detected."
        
        summary_lines = []
        
        # Add overall summary
        total_files = len(file_analyses)
        total_insertions = sum(file.get('insertions', 0) for file in file_analyses)
        total_deletions = sum(file.get('deletions', 0) for file in file_analyses)
        
        summary_lines.append(f"Changed {total_files} files with {total_insertions} additions and {total_deletions} deletions.")
        
        # Group files by type
        file_types = {}
        for file in file_analyses:
            language = file.get('language', 'Unknown')
            file_types[language] = file_types.get(language, 0) + 1
        
        if len(file_types) > 1:
            file_type_summary = ", ".join(f"{count} {lang}" for lang, count in file_types.items())
            summary_lines.append(f"File types: {file_type_summary}")
        
        # Add file summaries
        summary_lines.append("\nFile changes:")
        for file in file_analyses:
            path = file.get('path', '')
            summary = file.get('summary', '')
            summary_lines.append(f"- {path}: {summary}")
        
        return "\n".join(summary_lines)

    def _generate_ai_summary(self, file_analyses: List[Dict[str, Any]], 
                            commit_analysis: Dict[str, Any]) -> Optional[str]:
        """
        Generate an AI-powered summary of the code changes.
        
        Args:
            file_analyses: List of file analysis dictionaries.
            commit_analysis: Dict containing commit analysis.
            
        Returns:
            AI-generated summary string or None if it fails.
        """
        if not self.openai_available:
            return None
        
        try:
            import openai
            
            # Prepare the prompt
            prompt = f"""
            Summarize the following code changes in a concise, technical manner:
            
            Commit message: {commit_analysis.get('message', '')}
            
            Files changed:
            """
            
            for file in file_analyses:
                prompt += f"\n- {file.get('path', '')}: {file.get('summary', '')}"
                
                # Add snippets if available
                if self.include_snippets and 'changed_sections' in file:
                    for i, section in enumerate(file['changed_sections']):
                        if i >= 2:  # Limit to 2 sections per file to keep prompt size reasonable
                            break
                        if 'snippet' in section:
                            prompt += f"\n\nSnippet from {file.get('path', '')}:\n```\n{section['snippet']}\n```"
            
            prompt += "\n\nProvide a technical summary of what these changes accomplish and their potential impact."
            
            # Call the OpenAI API
            response = openai.ChatCompletion.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": "You are a technical code reviewer who provides concise, accurate summaries of code changes."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.5
            )
            
            # Extract the summary
            summary = response.choices[0].message.content.strip()
            logger.info("Generated AI-powered summary")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating AI summary: {e}")
            return None 