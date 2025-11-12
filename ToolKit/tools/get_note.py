import os
from typing import Dict, Any, List
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ToolKit.base_tool import BaseTool

class GetNoteTool(BaseTool):
    """Tool for retrieving notes from the filesystem"""
    
    def __init__(self):
        super().__init__()
        self.notes_dir = "/home/mason/notes"
        
        if not os.path.exists(self.notes_dir):
            os.makedirs(self.notes_dir)
    
    def get_name(self) -> str:
        return "get_note"
    
    def get_description(self) -> str:
        return "Retrieve notes from the notes directory to answer questions about past notes"
    
    def get_tool_type(self):
        """This is a retrieval tool - data needs to be fed back to LLM"""
        return "retrieval"
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "search_term": {
                    "type": "string",
                    "description": "Optional search term to filter notes"
                }
            },
            "required": []
        }
    
    def execute(self, search_term: str = None, **kwargs) -> Dict[str, Any]:
        """Retrieve notes, optionally filtered by search term"""
        try:
            notes = []
            
            if not os.path.exists(self.notes_dir):
                return {
                    "success": True,
                    "message": "No notes directory found",
                    "notes": []
                }
            
            note_files = sorted(os.listdir(self.notes_dir), reverse=True)
            
            if not note_files:
                return {
                    "success": True,
                    "message": "No notes found",
                    "notes": []
                }
            
            for filename in note_files[:10]:  # Limit to 10 most recent
                if filename.endswith('.txt'):
                    filepath = os.path.join(self.notes_dir, filename)
                    
                    with open(filepath, 'r') as f:
                        content = f.read()
                    
                    if search_term is None or search_term.lower() in content.lower():
                        notes.append({
                            "filename": filename,
                            "content": content
                        })
            
            # Format notes for LLM consumption
            formatted_notes = "\n\n".join([
                f"Note from {note['filename']}:\n{note['content']}"
                for note in notes
            ])
            
            return {
                "success": True,
                "message": f"Found {len(notes)} note(s)",
                "notes": formatted_notes if formatted_notes else "No notes found",
                "count": len(notes)
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to retrieve notes",
                "error": str(e)
            }