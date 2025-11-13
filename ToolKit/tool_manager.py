import json
import os
from typing import Dict, Any, List, Optional
from importlib import import_module
import inspect

class ToolManager:
    """Manages all available tools and handles tool execution"""
    
    def __init__(self, tools_config_path: str = None):
        self.tools = {}
        self.tools_config = {}
        
        if tools_config_path is None:
            tools_config_path = os.path.join(os.path.dirname(__file__), 'tools.json')
        
        # Create tool execution log file
        self.log_dir = os.path.join(os.path.dirname(__file__), '..', 'tool_logs')
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        
        from datetime import datetime
        self.log_file = os.path.join(self.log_dir, f"tools_{datetime.now().strftime('%Y%m%d')}.log")
        
        self.load_tools_config(tools_config_path)
        self.load_tools()
    
    def load_tools_config(self, config_path: str):
        """Load tool configuration from JSON file"""
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                data = json.load(f)
                self.tools_config = data.get('tools', {})
            print(f"📚 Loaded {len(self.tools_config)} tool configurations")
    
    def load_tools(self):
        """Dynamically load all tool implementations from the tools directory"""
        tools_dir = os.path.join(os.path.dirname(__file__), 'tools')
        
        if not os.path.exists(tools_dir):
            os.makedirs(tools_dir)
            print(f"📁 Created tools directory: {tools_dir}")
            return
        
        for filename in os.listdir(tools_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                module_name = filename[:-3]
                try:
                    module = import_module(f'.tools.{module_name}', package='ToolKit')
                    
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and 
                            name != 'BaseTool' and 
                            hasattr(obj, 'execute')):
                            tool_instance = obj()
                            tool_name = tool_instance.get_name()
                            self.tools[tool_name] = tool_instance
                            print(f"✅ Loaded tool: {tool_name}")
                except Exception as e:
                    print(f"⚠️ Failed to load tool from {filename}: {e}")
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of all available tools with their descriptions"""
        tools_list = []
        for name, tool in self.tools.items():
            tools_list.append({
                "name": name,
                "description": tool.get_description(),
                "parameters": tool.get_parameters(),
                "tool_type": tool.tool_type
            })
        return tools_list
    
    def get_tools_for_prompt(self) -> str:
        """Generate a description of available tools for the LLM prompt"""
        tools_desc = "AVAILABLE TOOLS:\n"
        
        for name, tool in self.tools.items():
            tools_desc += f"- {name}: {tool.get_description()}\n"
            params = tool.get_parameters()
            
            # Show parameter details
            if params.get('properties'):
                for param_name, param_info in params['properties'].items():
                    required = param_name in params.get('required', [])
                    tools_desc += f"  - {param_name}: {param_info.get('description', 'No description')} {'(required)' if required else '(optional)'}\n"
            
            # Add example usage
            tools_desc += f'  To use: {{"tool": "{name}", "parameters": {{'
            param_examples = []
            if params.get('properties'):
                for param_name in params['properties']:
                    param_examples.append(f'"{param_name}": "value"')
            tools_desc += ', '.join(param_examples) + '}}}\n\n'
        
        tools_desc += """
🚨🚨🚨 CRITICAL TOOL USAGE RULES 🚨🚨🚨

RULE #1: When you need information or need to perform an action, OUTPUT ONLY JSON!
RULE #2: NEVER say "I will", "Let me", "I'll check", "I can help" - JUST OUTPUT THE TOOL JSON!
RULE #3: If you output ANY text before a tool call, YOU HAVE FAILED!

EXAMPLES OF FAILURES (DO NOT DO THIS):
❌ "I'll check the weather for you" → WRONG! 
❌ "Let me find that information" → WRONG!
❌ "I can help you with that" → WRONG!
❌ "Sure, I'll get that data" → WRONG!

CORRECT BEHAVIOR (DO THIS):
✅ User asks for info → IMMEDIATELY output: {"tool": "tool_name", "parameters": {...}}
✅ NO PREAMBLE, NO EXPLANATION, JUST JSON!

When chaining tools:
- After receiving tool data, if you need MORE info → OUTPUT ONLY JSON
- NO "I need more information" → JUST CALL THE NEXT TOOL
- Keep calling tools until you have ALL data needed

SPECIFIC TOOL USAGE:

For questions needing data:
- Weather → {"tool": "get_weather", "parameters": {"location": "city"}}
- Notes → {"tool": "get_note", "parameters": {}}
- System info → {"tool": "execute_command", "parameters": {"command": "..."}}

For actions:
- Save note → {"tool": "post_note", "parameters": {"note": "..."}}
- Run command → {"tool": "execute_command", "parameters": {"command": "..."}}

REMEMBER:
1. JSON ONLY for tool calls
2. NO explanatory text before tools
3. Chain tools automatically without narration
4. Only provide final answer when ALL data is collected

If you write ANYTHING except JSON when calling a tool, you have FAILED!"""
        
        return tools_desc
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific tool with given parameters"""
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Log tool execution start
        with open(self.log_file, 'a') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"[{timestamp}] TOOL EXECUTION START\n")
            f.write(f"Tool: {tool_name}\n")
            f.write(f"Parameters: {parameters}\n")
        
        print(f"🔧 [TOOL] Executing {tool_name} with params: {parameters}")
        
        if tool_name not in self.tools:
            error_msg = f"Tool '{tool_name}' not found"
            with open(self.log_file, 'a') as f:
                f.write(f"ERROR: {error_msg}\n")
                f.write(f"{'='*60}\n")
            return {
                "success": False,
                "error": error_msg
            }
        
        tool = self.tools[tool_name]
        try:
            tool.validate_parameters(**parameters)
            
            # Log before execution
            with open(self.log_file, 'a') as f:
                f.write(f"Tool Type: {tool.tool_type}\n")
                f.write(f"Executing...\n")
            
            result = tool.execute(**parameters)
            
            # Log after execution
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(self.log_file, 'a') as f:
                f.write(f"[{end_time}] EXECUTION COMPLETE\n")
                f.write(f"Success: {result.get('success', False)}\n")
                if not result.get('success'):
                    f.write(f"Error: {result.get('error', 'Unknown')}\n")
                f.write(f"{'='*60}\n")
            
            print(f"✅ [TOOL] {tool_name} execution complete")
            
            return {
                "success": True,
                "tool": tool_name,
                "tool_type": tool.tool_type,
                "result": result
            }
        except Exception as e:
            error_msg = str(e)
            with open(self.log_file, 'a') as f:
                f.write(f"EXCEPTION: {error_msg}\n")
                f.write(f"{'='*60}\n")
            
            print(f"❌ [TOOL] {tool_name} failed: {error_msg}")
            
            return {
                "success": False,
                "tool": tool_name,
                "tool_type": tool.tool_type,
                "error": error_msg
            }
    
    def parse_and_execute_from_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response for tool calls and execute if found"""
        print(f"🔍 [TOOL_PARSER] Checking response for tool calls...")
        print(f"🔍 [TOOL_PARSER] Response preview: {response[:200]}...")
        
        try:
            import re
            import json
            json_match = re.search(r'\{.*"tool".*\}', response, re.DOTALL)
            
            if json_match:
                print(f"🔍 [TOOL_PARSER] Found JSON match: {json_match.group()[:100]}...")
                tool_call = json.loads(json_match.group())
                tool_name = tool_call.get('tool')
                parameters = tool_call.get('parameters', {})
                
                print(f"🔍 [TOOL_PARSER] Parsed tool: {tool_name}, params: {parameters}")
                
                if tool_name:
                    return self.execute_tool(tool_name, parameters)
            else:
                print(f"🔍 [TOOL_PARSER] No tool JSON found in response")
                
        except json.JSONDecodeError as e:
            print(f"❌ [TOOL_PARSER] JSON decode error: {e}")
        except Exception as e:
            print(f"❌ [TOOL_PARSER] Error parsing tool call: {e}")
        
        return None