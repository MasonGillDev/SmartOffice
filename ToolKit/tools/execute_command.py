import os
import sys
import subprocess
import re
import tempfile
from datetime import datetime
from typing import Dict, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ToolKit.base_tool import BaseTool

class ExecuteCommandTool(BaseTool):
    """Tool for safely executing system commands"""
    
    def __init__(self):
        super().__init__()
        # Create command history directory
        self.history_dir = "/home/mason/SmartOffice/command_history"
        if not os.path.exists(self.history_dir):
            os.makedirs(self.history_dir)
            print(f"📁 Created command history directory: {self.history_dir}")
        
        # Create daily log file
        self.log_file = os.path.join(
            self.history_dir, 
            f"commands_{datetime.now().strftime('%Y%m%d')}.log"
        )
    
    # Patterns that are absolutely forbidden
    DANGEROUS_PATTERNS = [
        r'rm\s+-rf\s+/',           # Recursive delete from root
        r'rm\s+-rf\s+~',            # Recursive delete home
        r':\(\)\{.*:\|:&\};:',      # Fork bomb
        r'dd\s+.*of=/dev/[sh]d',    # Direct disk write
        r'format\s+[cC]:',          # Windows format
        r'del\s+/[sfq]\s+[cC]:\\',  # Windows delete
        r'>\s*/dev/[sh]d',          # Overwrite disk
        r'mkfs\.',                  # Format filesystem
        r'chmod\s+-R\s+000',        # Remove all permissions
        r':(){ :|:& };:',          # Fork bomb variant
    ]
    
    # Commands that need extra caution (will warn but allow)
    WARNING_COMMANDS = [
        'shutdown', 'reboot', 'halt', 'poweroff',
        'kill', 'killall', 'pkill',
        'systemctl stop', 'service .* stop',
        'apt remove', 'apt purge', 'yum remove',
        'brew uninstall', 'pip uninstall',
        'sudo',  # Any sudo command gets a warning
    ]
    
    # Common safe commands for reference
    SAFE_EXAMPLES = [
        'ls', 'pwd', 'echo', 'cat', 'grep', 'find',
        'ps', 'df', 'du', 'date', 'whoami', 'hostname',
        'git status', 'git log', 'npm list', 'pip list',
        'netstat', 'lsof', 'top', 'free', 'uptime'
    ]
    
    def get_name(self) -> str:
        return "execute_command"
    
    def get_description(self) -> str:
        return "Execute system commands (default dir: /home/mason). For find: use -iname for case-insensitive search. Start from '.' or '~', not '/'. Example: find . -type d -iname '*office*'"
    
    def get_tool_type(self):
        """This is a retrieval tool - output needs to be fed back to LLM"""
        return "retrieval"
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to execute (can be multi-line for scripts)"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Optional working directory to execute command in"
                }
            },
            "required": ["command"]
        }
    
    def is_command_safe(self, command: str) -> tuple[bool, str]:
        """
        Check if command is safe to execute
        Returns: (is_safe, warning_message)
        """
        command_lower = command.lower()
        
        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"BLOCKED: Command matches dangerous pattern '{pattern}'"
        
        # Check for warning commands
        warnings = []
        
        # Warn about find commands starting from root
        if re.match(r'find\s+/', command) and not re.match(r'find\s+/home', command):
            warnings.append("⚠️ Warning: 'find /' will cause many permission errors. Consider 'find .' or 'find /home/mason' instead")
        
        # Warn about other root-level operations
        if re.match(r'(ls|grep|cat)\s+/', command) and not re.match(r'(ls|grep|cat)\s+/(home|tmp|var/log)', command):
            warnings.append("⚠️ Warning: Operating on root directories may cause permission errors")
        
        for warning_cmd in self.WARNING_COMMANDS:
            if warning_cmd in command_lower:
                warnings.append(f"⚠️ Warning: Command contains '{warning_cmd}'")
        
        warning_msg = "\n".join(warnings) if warnings else ""
        return True, warning_msg
    
    def log_command(self, command: str, output: str, success: bool, error: str = None):
        """Log command execution to history file"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write(f"Status: {'SUCCESS' if success else 'FAILED'}\n")
                f.write(f"Command: {command}\n")
                
                if error:
                    f.write(f"Error: {error}\n")
                
                f.write(f"Output:\n{output if output else '(no output)'}\n")
                f.write(f"{'='*60}\n")
        except Exception as e:
            print(f"⚠️ Could not log command: {e}")
    
    def execute(self, command: str, working_dir: str = None, **kwargs) -> Dict[str, Any]:
        """Execute a system command safely"""
        try:
            # Safety check
            is_safe, warning = self.is_command_safe(command)
            
            if not is_safe:
                # Log blocked command
                self.log_command(command, "", False, warning)
                return {
                    "success": False,
                    "error": warning,
                    "command": command,
                    "output": "",
                    "blocked": True
                }
            
            # Set working directory (default to /home/mason)
            if working_dir and os.path.exists(working_dir):
                cwd = working_dir
            else:
                cwd = "/home/mason"  # Default to home directory
            
            # Handle multi-line commands (scripts)
            if '\n' in command and not command.startswith('#!'):
                # Create temporary script file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
                    f.write('#!/bin/bash\n')
                    f.write(command)
                    f.flush()
                    script_path = f.name
                
                # Make script executable
                os.chmod(script_path, 0o755)
                
                # Execute script
                result = subprocess.run(
                    ['/bin/bash', script_path],
                    capture_output=True,
                    text=True,
                    cwd=cwd,
                    timeout=30  # 30 second timeout
                )
                
                # Clean up script
                os.unlink(script_path)
            else:
                # Single command execution
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=cwd,
                    timeout=30  # 30 second timeout
                )
            
            # Prepare output
            output = result.stdout
            stderr_output = ""
            if result.stderr:
                stderr_output = result.stderr
                # Only add stderr to output if there's no stdout (for error visibility)
                if not output.strip():
                    output = f"--- STDERR ---\n{result.stderr}"
            
            # Store full output for logging
            full_output = output
            if stderr_output and output.strip():
                full_output = output + f"\n--- STDERR ---\n{stderr_output}"
            
            # Truncate very long output for return
            max_length = 5000
            if len(output) > max_length:
                output = output[:max_length] + f"\n... (truncated, {len(output) - max_length} chars omitted)"
            
            # For find command, success if we found something even with permission errors
            if command.startswith('find') and result.stdout.strip():
                success = True  # Found something, ignore permission errors
            else:
                success = result.returncode == 0
            
            self.log_command(command, full_output, success)
            
            return {
                "success": success,
                "command": command,
                "output": output,
                "return_code": result.returncode,
                "working_dir": cwd,
                "warning": warning if warning else None
            }
            
        except subprocess.TimeoutExpired:
            error_msg = "Command timed out after 30 seconds"
            self.log_command(command, "", False, error_msg)
            return {
                "success": False,
                "command": command,
                "error": error_msg,
                "output": ""
            }
        except Exception as e:
            error_msg = str(e)
            self.log_command(command, "", False, error_msg)
            return {
                "success": False,
                "command": command,
                "error": error_msg,
                "output": ""
            }