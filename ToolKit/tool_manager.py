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
IMPORTANT TOOL USAGE RULES:
1. ONLY use tools when the user EXPLICITLY asks for that action
2. DO NOT use post_note unless the user says words like "note", "save", "remember", "write down"
3. DO NOT use get_note unless the user asks about past notes or what they noted before
4. For general conversation, answer WITHOUT using any tools
5. When you DO use a tool:
   - First acknowledge the user's request
   - Then include the tool call as JSON on a new line
   - Keep your response brief

Examples of when to use post_note:
✓ "Note that I have a meeting at 3pm"
✓ "Save a reminder about calling mom"
✓ "Remember to buy milk"
✗ "I have a meeting at 3pm" (just conversation, no note request)
✗ "What's the weather?" (no note request)"""
        
        return tools_desc
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific tool with given parameters"""
        if tool_name not in self.tools:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found"
            }
        
        tool = self.tools[tool_name]
        try:
            tool.validate_parameters(**parameters)
            result = tool.execute(**parameters)
            return {
                "success": True,
                "tool": tool_name,
                "tool_type": tool.tool_type,
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "tool": tool_name,
                "tool_type": tool.tool_type,
                "error": str(e)
            }
    
    def parse_and_execute_from_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response for tool calls and execute if found"""
        try:
            import re
            json_match = re.search(r'\{.*"tool".*\}', response, re.DOTALL)
            if json_match:
                tool_call = json.loads(json_match.group())
                tool_name = tool_call.get('tool')
                parameters = tool_call.get('parameters', {})
                
                if tool_name:
                    return self.execute_tool(tool_name, parameters)
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"Error parsing tool call: {e}")
        
        return None