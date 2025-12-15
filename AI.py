import re
import json
import logging
from time import sleep
import database

#Gemini Imports
#from google import genai
#End Gemini Imports

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QuizAI:
    def __init__(self, subject="General Knowledge", difficulty="advanced", model_name="gpt2"):
        self.subject = subject
        self.difficulty = difficulty
       
    
    def _strip_until_first_marker(self, text):
        """
        If the generator echoed the prompt or included instruction text, attempt to find
        the first question marker and return text from there. Markers include:
        - numbered "1." at start of line
        - "Q1" or "Question 1"
        - a line starting with "A)" (first option label)
        """
        if not text:
            return text
        # Find the earliest occurrence of any plausible marker
        markers = [
            r'(?m)^\s*1\.',                 # "1."
            r'(?m)^\s*\d+\.',               # any numbered (1., 2., ...)
            r'(?mi)^\s*q\s*1[:.\s]',        # "Q1" variations
            r'(?mi)^\s*question\s*1[:.\s]', # "Question 1"
            r'(?m)^\s*A\)',                 # "A)" option label at start of line
            r'(?m)^\s*A\)',                 # duplicate - safe
        ]
        first_index = None
        for pat in markers:
            m = re.search(pat, text)
            if m:
                idx = m.start()
                if first_index is None or idx < first_index:
                    first_index = idx
        if first_index is not None and first_index > 0:
            return text[first_index:].strip()
        return text

    def _try_json_parse(self, text):
        """
        Attempt to extract a JSON array from text; return list or None.
        """
        if not text:
            return None
        # Find first bracketed array
        m = re.search(r'(\[.*\])', text, flags=re.S)
        if m:
            candidate = m.group(1)
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, list) and all(isinstance(i, dict) and 'question' in i for i in parsed):
                    return parsed
            except Exception:
                pass
        return None

    def generate_questions(self, generated):
      
        raw = generated.strip()
        body = self._strip_until_first_marker(raw)

        parsed_json = self._try_json_parse(raw)
        return parsed_json