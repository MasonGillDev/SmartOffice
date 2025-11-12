from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Literal

class BaseTool(ABC):
    """Base class for all tools that can be called by the LLM"""
    
    def __init__(self):
        self.name = self.get_name()
        self.description = self.get_description()
        self.parameters = self.get_parameters()
        self.tool_type = self.get_tool_type()
    
    @abstractmethod
    def get_name(self) -> str:
        """Return the tool name"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Return a description of what this tool does"""
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Return parameter schema for this tool"""
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool with given parameters"""
        pass
    
    def get_tool_type(self) -> Literal["action", "retrieval"]:
        """
        Return the tool type:
        - 'action': Tool performs an action and returns success/failure
        - 'retrieval': Tool retrieves data that needs to be fed back to the LLM
        """
        return "action"  # Default to action type
    
    def validate_parameters(self, **kwargs) -> bool:
        """Validate that all required parameters are provided"""
        required = self.parameters.get('required', [])
        for param in required:
            if param not in kwargs:
                raise ValueError(f"Missing required parameter: {param}")
        return True