import sys
import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter

# Add path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from KIT.gemini_client import GeminiClient
from KITCore.tools.settings_tool import get_setting as kit_get_setting
from api.services.tag_service import TagService

logger = logging.getLogger(__name__)

class TagSuggestionService:
    def __init__(self):
        self.ai_model = "gemini-1.5-flash-latest"
        
        # Tag suggestion system prompt
        self.tag_suggestion_prompt = """You are a tag suggestion AI. Your job is to analyze note content and suggest relevant tags.

RULES:
1. Suggest 3-8 tags maximum
2. Tags should be concise (1-2 words)
3. Include both content-based tags and contextual tags
4. Provide confidence scores (0.0-1.0) for each suggestion
5. Consider typed tags (category:work, priority:high, person:John, etc.)
6. Respond ONLY in JSON format

RESPONSE FORMAT:
{
  "suggestions": [
    {"tag": "meeting", "confidence": 0.95, "reason": "Content mentions scheduling a meeting"},
    {"tag": "priority:high", "confidence": 0.8, "reason": "Urgent language used"},
    {"tag": "work", "confidence": 0.9, "reason": "Professional context"}
  ]
}

CONFIDENCE SCORING:
- 0.9-1.0: Very confident (explicit keywords, clear context)
- 0.7-0.89: Confident (strong indicators, likely relevant)
- 0.5-0.69: Moderate (some indicators, possibly relevant)
- 0.3-0.49: Low (weak indicators, might be relevant)
- 0.0-0.29: Very low (speculative, unlikely relevant)

Analyze the following note content and suggest tags:"""

        try:
            self.gemini_client = GeminiClient(
                model_name=self.ai_model,
                logger=logger,
                system_instruction=self.tag_suggestion_prompt
            )
        except Exception as e:
            logger.error(f"Failed to initialize GeminiClient in TagSuggestionService: {e}")
            self.gemini_client = None

    async def suggest_tags_for_content(self, content: str, existing_tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Suggests tags for the given note content using AI analysis.
        
        Args:
            content: The note content to analyze
            existing_tags: Optional list of tags already on the note
            
        Returns:
            List of tag suggestions with confidence scores and reasons
        """
        try:
            if not self.gemini_client:
                logger.error("GeminiClient not available for tag suggestions")
                return await self._fallback_tag_suggestions(content, existing_tags)
            
            # Get existing system tags for context
            try:
                all_system_tags = await TagService.list_all_tags()
            except Exception as e:
                logger.warning(f"Could not fetch existing system tags: {e}")
                all_system_tags = []
            
            # Prepare the prompt
            analysis_prompt = f"""
Content to analyze: "{content}"

Existing tags on this note: {existing_tags if existing_tags else 'None'}
Available system tags for reference: {all_system_tags[:50] if all_system_tags else 'None'}  # Limit to first 50

Please suggest relevant tags with confidence scores and brief reasons.
"""

            # Get AI suggestions
            logger.info(f"Requesting tag suggestions for content: {content[:100]}...")
            response = await self.gemini_client.send_prompt_async(analysis_prompt)
            
            # Parse AI response
            suggestions = await self._parse_ai_response(response)
            
            # Filter out existing tags and enhance with rule-based suggestions
            filtered_suggestions = self._filter_and_enhance_suggestions(
                suggestions, existing_tags, content, all_system_tags
            )
            
            logger.info(f"Generated {len(filtered_suggestions)} tag suggestions")
            return filtered_suggestions
            
        except Exception as e:
            logger.error(f"Error generating AI tag suggestions: {e}", exc_info=True)
            return await self._fallback_tag_suggestions(content, existing_tags)

    async def _parse_ai_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse the AI response to extract tag suggestions."""
        try:
            import json
            
            # Try to find JSON in the response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                parsed = json.loads(json_str)
                
                if 'suggestions' in parsed and isinstance(parsed['suggestions'], list):
                    return parsed['suggestions']
            
            logger.warning("Could not parse AI response as JSON, using fallback")
            return []
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in AI response: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            return []

    def _filter_and_enhance_suggestions(self, ai_suggestions: List[Dict[str, Any]], 
                                       existing_tags: Optional[List[str]], 
                                       content: str,
                                       system_tags: List[str]) -> List[Dict[str, Any]]:
        """Filter AI suggestions and add rule-based enhancements."""
        filtered = []
        existing_set = set(existing_tags or [])
        
        # Process AI suggestions
        for suggestion in ai_suggestions:
            if isinstance(suggestion, dict) and 'tag' in suggestion:
                tag = suggestion['tag'].strip().lower()
                confidence = suggestion.get('confidence', 0.5)
                reason = suggestion.get('reason', 'AI suggested')
                
                # Skip if already exists
                if tag not in existing_set and tag:
                    # Validate confidence
                    try:
                        confidence = max(0.0, min(1.0, float(confidence)))
                    except (ValueError, TypeError):
                        confidence = 0.5
                    
                    filtered.append({
                        'tag': tag,
                        'confidence': confidence,
                        'reason': reason,
                        'source': 'ai'
                    })
        
        # Add rule-based suggestions
        rule_based = self._get_rule_based_suggestions(content, existing_set, system_tags)
        filtered.extend(rule_based)
        
        # Sort by confidence and limit results
        filtered.sort(key=lambda x: x['confidence'], reverse=True)
        return filtered[:8]  # Limit to 8 suggestions

    def _get_rule_based_suggestions(self, content: str, existing_tags: set, 
                                   system_tags: List[str]) -> List[Dict[str, Any]]:
        """Generate rule-based tag suggestions."""
        suggestions = []
        content_lower = content.lower()
        
        # Common patterns and their tags
        patterns = {
            r'\b(todo|task|action|need to|should|must)\b': ('todo', 0.8, 'Contains task-related keywords'),
            r'\b(urgent|asap|immediately|critical|important)\b': ('priority:high', 0.9, 'Contains urgency indicators'),
            r'\b(meeting|call|appointment|schedule)\b': ('meeting', 0.85, 'Contains meeting-related terms'),
            r'\b(project|work|office|business|client)\b': ('work', 0.7, 'Contains work-related terms'),
            r'\b(idea|brainstorm|concept|thought)\b': ('idea', 0.75, 'Contains ideation keywords'),
            r'\b(note|reminder|remember)\b': ('note', 0.6, 'Contains note-taking keywords'),
            r'\b(research|study|learn|investigate)\b': ('research', 0.8, 'Contains research-related terms'),
            r'\b(bug|error|issue|problem|fix)\b': ('issue', 0.85, 'Contains problem-related terms'),
            r'\b(review|feedback|evaluate|assess)\b': ('review', 0.75, 'Contains review-related terms'),
        }
        
        for pattern, (tag, confidence, reason) in patterns.items():
            if re.search(pattern, content_lower) and tag not in existing_tags:
                suggestions.append({
                    'tag': tag,
                    'confidence': confidence,
                    'reason': reason,
                    'source': 'rule'
                })
        
        # Date-based suggestions
        if re.search(r'\b(today|tomorrow|this week|next week|deadline)\b', content_lower):
            if 'schedule' not in existing_tags:
                suggestions.append({
                    'tag': 'schedule',
                    'confidence': 0.7,
                    'reason': 'Contains time-related references',
                    'source': 'rule'
                })
        
        return suggestions

    async def _fallback_tag_suggestions(self, content: str, existing_tags: Optional[List[str]]) -> List[Dict[str, Any]]:
        """Fallback tag suggestions when AI is not available."""
        logger.info("Using fallback tag suggestion method")
        existing_set = set(existing_tags or [])
        
        try:
            system_tags = await TagService.list_all_tags()
        except Exception:
            system_tags = []
        
        suggestions = self._get_rule_based_suggestions(content, existing_set, system_tags)
        
        # Add some common tags based on content length and type
        content_lower = content.lower()
        
        if len(content) > 200 and 'long' not in existing_set:
            suggestions.append({
                'tag': 'detailed',
                'confidence': 0.6,
                'reason': 'Note is lengthy and detailed',
                'source': 'fallback'
            })
        
        if len(content.split()) < 10 and 'quick' not in existing_set:
            suggestions.append({
                'tag': 'quick',
                'confidence': 0.5,
                'reason': 'Short note or quick thought',
                'source': 'fallback'
            })
        
        return suggestions[:6]  # Limit fallback suggestions

# Global instance
tag_suggestion_service = TagSuggestionService() 