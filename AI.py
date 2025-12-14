import re
import json
import logging
from time import sleep
from transformers import pipeline
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
        # Keep a single generator instance (may be slow to init)
        #self.generator = pipeline("text-generation", model=model_name)
        #client = genai.Client(api_key="AlzaSyAFdQyYQ_deLwWfSUiAbpWaA9vPbrfEQww")

       # response = client.models.generate_content(model="gemini-2.5-flash", contents="Explain how AI works in a few words")

    def _strip_prompt_echo(self, generated_text, prompt):
        """
        Remove exact prompt echo or a first-line instruction-like echo.
        """
        txt = (generated_text or "").strip()
        if not txt:
            return txt
        if txt.startswith(prompt):
            return txt[len(prompt):].strip()
        lines = txt.splitlines()
        if len(lines) > 1:
            first = lines[0].strip()
            low = first.lower()
            if len(first) < 300 and (
                low.startswith("create")
                or low.startswith("generate")
                or "multiple-choice" in low
                or low.startswith("output")
            ):
                return "\n".join(lines[1:]).strip()
        return txt

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

    def _parse_single_block(self, block):
        raw_block = (block or "").strip()
        # find options lines like "A) text"
        options = []
        opt_matches = re.findall(r'^[A-D]\)\s*(.+)$', raw_block, flags=re.M)
        if opt_matches:
            letters = ['A)', 'B)', 'C)', 'D)']
            for lbl in letters:
                m = re.search(rf'^{re.escape(lbl)}\s*(.+)$', raw_block, flags=re.M)
                if m:
                    options.append(f"{lbl} {m.group(1).strip()}")
            if not options:
                for idx, txt in enumerate(opt_matches[:4]):
                    options.append(f"{letters[idx]} {txt.strip()}")

        # find Answer: X and normalize to A-D
        a_match = re.search(r'(?:Answer|Correct)\s*:\s*([A-Z])', raw_block, flags=re.I)
        answer = "A"
        if a_match:
            letter = a_match.group(1).upper()
            if re.match(r'^[A-D]$', letter):
                answer = letter
            else:
                # If model used different letters, coerce to closest (default fallback A)
                answer = "A"

        # question text: everything before first option label, or first substantial line
        first_option = re.search(r'^[A-D]\)', raw_block, flags=re.M)
        if first_option:
            question_text = raw_block[:first_option.start()].strip()
        else:
            lines = [ln.strip() for ln in raw_block.splitlines() if ln.strip()]
            question_text = lines[0] if lines else raw_block

        # remove numbering prefixes
        question_text = re.sub(r'^(question[:\s-]*|\d+\.\s*|q\d+[:\s-]*)', '', question_text, flags=re.I).strip()

        # avoid cases where question is actually the instruction; normalize trivial instruction matches
        lowq = question_text.lower()
        if not question_text or lowq.startswith("create") or "multiple-choice" in lowq or "answer:" in lowq:
            # invalid parsed question
            question_text = ""

        return {
            "question": question_text,
            "options": options,
            "answer": answer,
            "raw": raw_block
        }

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


    def grade(self, questions, user_answers):
        score = 0
        for q, ans in zip(questions, user_answers):
            if not isinstance(ans, str):
                continue
            if ans.strip().upper() == q.get("answer", "A"):
                score += 1
            else:
                opt_list = q.get("options") or []
                for idx, opt in enumerate(opt_list):
                    if ans.strip().upper() == chr(ord('A') + idx):
                        if q.get("answer", "A") == chr(ord('A') + idx):
                            score += 1
                        break
                    rawopt = re.sub(r'^[A-D]\)\s*', '', opt).strip()
                    if ans.strip().lower() == rawopt.lower():
                        if q.get("answer", "A") == chr(ord('A') + idx):
                            score += 1
                        break
        return score, len(questions)