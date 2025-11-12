import os
from datetime import datetime
from typing import Dict, Any
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ToolKit.base_tool import BaseTool

class PostNoteTool(BaseTool):
    """Tool for creating and saving notes to the filesystem"""
    
    def __init__(self):
        super().__init__()
        self.notes_dir = "/home/mason/notes"
        
        if not os.path.exists(self.notes_dir):
            os.makedirs(self.notes_dir)
            print(f"📁 Created notes directory: {self.notes_dir}")
    
    def get_name(self) -> str:
        return "post_note"
    
    def get_description(self) -> str:
        return "Create and save a note with timestamp to the notes directory"
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text content of the note to save"
                }
            },
            "required": ["text"]
        }
    
    def execute(self, text: str, **kwargs) -> Dict[str, Any]:
        """Save a note to a file with timestamp"""
        try:
            timestamp = datetime.now()
            
            filename = f"note_{timestamp.strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = os.path.join(self.notes_dir, filename)
            
            note_content = f"Note created: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            note_content += f"{'-' * 50}\n"
            note_content += f"{text}\n"
            
            with open(filepath, 'w') as f:
                f.write(note_content)
            
            return {
                "success": True,
                "message": f"Note saved successfully",
                "filename": filename,
                "path": filepath,
                "timestamp": timestamp.isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to save note",
                "error": str(e)
            }