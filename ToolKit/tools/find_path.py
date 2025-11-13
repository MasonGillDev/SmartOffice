import os
import sys
import subprocess
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ToolKit.base_tool import BaseTool

class FindPathTool(BaseTool):
    """Smart tool for finding files and folders with fuzzy matching"""
    
    def get_name(self) -> str:
        return "find_path"
    
    def get_description(self) -> str:
        return "Smart search for files and folders by name. Handles variations like 'main hub' → MainHub, main_hub, etc. Returns best matches sorted by relevance and recency."
    
    def get_tool_type(self):
        """This is a retrieval tool - data needs to be fed back to LLM"""
        return "retrieval"
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name to search for (e.g., 'main hub', 'server.py', 'toolkit')"
                },
                "search_type": {
                    "type": "string",
                    "description": "Type to search for: 'file', 'folder', or 'both' (default: both)"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5)"
                }
            },
            "required": ["name"]
        }
    
    def generate_search_patterns(self, name: str) -> List[str]:
        """Generate various name patterns to search for"""
        patterns = []
        
        # Clean the input
        name_clean = name.lower().strip()
        
        # Original name
        patterns.append(f"*{name}*")
        
        # Remove common extensions for base name matching
        base_name = re.sub(r'\.(py|js|txt|md|json|yaml|yml|xml|html|css)$', '', name_clean)
        
        # Split on spaces, underscores, hyphens
        parts = re.split(r'[\s_\-]+', base_name)
        
        if len(parts) > 1:
            # CamelCase variations
            patterns.append(f"*{''.join(p.capitalize() for p in parts)}*")  # MainHub
            patterns.append(f"*{''.join(parts)}*")  # mainhub
            patterns.append(f"*{parts[0].lower()}{''.join(p.capitalize() for p in parts[1:])}*")  # mainHub
            
            # Underscore variations
            patterns.append(f"*{'_'.join(parts)}*")  # main_hub
            patterns.append(f"*{'_'.join(p.upper() for p in parts)}*")  # MAIN_HUB
            
            # Hyphen variations
            patterns.append(f"*{'-'.join(parts)}*")  # main-hub
            
            # Space variations (for exact matches)
            patterns.append(f"*{' '.join(parts)}*")  # main hub
        else:
            # Single word - just add case variations
            patterns.append(f"*{name_clean}*")
            patterns.append(f"*{name_clean.capitalize()}*")
            patterns.append(f"*{name_clean.upper()}*")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_patterns = []
        for p in patterns:
            if p.lower() not in seen:
                seen.add(p.lower())
                unique_patterns.append(p)
        
        return unique_patterns
    
    def score_match(self, path: str, search_name: str, modified_time: float) -> float:
        """Score a match based on relevance and recency"""
        score = 0.0
        path_lower = path.lower()
        search_lower = search_name.lower().replace(' ', '')
        
        # Extract just the filename/dirname
        basename = os.path.basename(path).lower()
        
        # Exact match (ignoring case and spaces)
        if basename.replace('_', '').replace('-', '') == search_lower:
            score += 100
        # Starts with search term
        elif basename.startswith(search_lower):
            score += 50
        # Contains search term
        elif search_lower in basename.replace('_', '').replace('-', ''):
            score += 25
        
        # Prefer items higher in directory tree (fewer path components)
        depth = len(Path(path).parts)
        score += max(0, 20 - depth * 2)
        
        # Prefer recently modified (last 7 days get bonus)
        days_old = (datetime.now().timestamp() - modified_time) / 86400
        if days_old < 1:
            score += 15
        elif days_old < 7:
            score += 10
        elif days_old < 30:
            score += 5
        
        # Prefer items in common project directories
        if any(d in path_lower for d in ['/home/', '/users/', '/projects/', '/documents/']):
            score += 5
        
        # Penalize hidden files/folders and system directories
        if '/.' in path or any(d in path_lower for d in ['/node_modules/', '/venv/', '/__pycache__/', '/dist/', '/build/']):
            score -= 20
        
        return score
    
    def execute(self, name: str, search_type: str = "both", max_results: int = 5, **kwargs) -> Dict[str, Any]:
        """Find files and folders with smart matching"""
        try:
            # Generate search patterns
            patterns = self.generate_search_patterns(name)
            
            # Collect all matches
            all_matches = []
            seen_paths = set()
            
            # Determine find type flag
            type_flag = ""
            if search_type == "file":
                type_flag = "-type f"
            elif search_type == "folder" or search_type == "directory":
                type_flag = "-type d"
            # "both" means no type flag
            
            # Search strategy: Start from home directory and current directory
            search_dirs = [
                os.path.expanduser("~"),  # Home directory
                os.getcwd(),  # Current working directory
            ]
            
            # Also add parent directories of CWD up to home
            current = Path(os.getcwd())
            home = Path(os.path.expanduser("~"))
            while current != home and current.parent != current:
                search_dirs.append(str(current.parent))
                current = current.parent
            
            # Remove duplicates while preserving order
            search_dirs = list(dict.fromkeys(search_dirs))
            
            for search_dir in search_dirs:
                if not os.path.exists(search_dir):
                    continue
                    
                for pattern in patterns[:3]:  # Limit patterns to avoid too many searches
                    try:
                        # Use find command with iname for case-insensitive search
                        cmd = f"find {search_dir} -iname '{pattern}' {type_flag} -not -path '*/.*' -not -path '*/node_modules/*' -not -path '*/venv/*' -not -path '*/__pycache__/*' 2>/dev/null | head -20"
                        
                        result = subprocess.run(
                            cmd,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=2  # Quick timeout per search
                        )
                        
                        if result.stdout:
                            for line in result.stdout.strip().split('\n'):
                                if line and line not in seen_paths:
                                    seen_paths.add(line)
                                    # Get modification time
                                    try:
                                        stat = os.stat(line)
                                        modified_time = stat.st_mtime
                                    except:
                                        modified_time = 0
                                    
                                    # Score the match
                                    score = self.score_match(line, name, modified_time)
                                    
                                    all_matches.append({
                                        'path': line,
                                        'type': 'directory' if os.path.isdir(line) else 'file',
                                        'score': score,
                                        'modified': datetime.fromtimestamp(modified_time).strftime('%Y-%m-%d %H:%M') if modified_time else 'unknown'
                                    })
                    except subprocess.TimeoutExpired:
                        continue
                    except Exception:
                        continue
            
            # Sort by score (highest first)
            all_matches.sort(key=lambda x: x['score'], reverse=True)
            
            # Limit results
            matches = all_matches[:max_results]
            
            if matches:
                # Format results
                result_text = f"Found {len(matches)} match{'es' if len(matches) > 1 else ''} for '{name}':\n\n"
                
                for i, match in enumerate(matches, 1):
                    result_text += f"{i}. {match['path']}\n"
                    result_text += f"   Type: {match['type']}, Modified: {match['modified']}\n"
                
                # Add the best match as a separate field for easy access
                best_match = matches[0]['path']
                
                return {
                    "success": True,
                    "matches": matches,
                    "best_match": best_match,
                    "result_text": result_text,
                    "count": len(matches)
                }
            else:
                return {
                    "success": False,
                    "matches": [],
                    "result_text": f"No matches found for '{name}'",
                    "count": 0
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "matches": [],
                "result_text": f"Error searching for '{name}': {str(e)}"
            }