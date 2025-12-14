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

    def generate_questions(self, num_questions=3, subject=None, difficulty=None, max_retries=3):
        subj = subject or self.subject or "General Knowledge"
        diff = difficulty or self.difficulty or "advanced"

        # First: try to get JSON array from model (most deterministic)
        json_prompt = (
            f"Create a multiple choice quiz on sports with 10 questions. There are 4 choices for each question. Provide the quiz in json format with the field question no,question, answer1, answer2,answer3,answer4 and correct answer no. return in only json format"
        )

        # for attempt in range(max_retries):
          #  try:
        generated = """{ 
    "quiz": [
        {
        "question n": 1,
        "question": "What country has won the most FIFA World Cups?",
        "answer1": "Argentina",
        "answer2": "Germany",
        "answer3": "Brazil",
        "answer4": "Italy",
        "correct answer no": 3
        },
        {
        "question no": 2,
        "question": "How many points is a successful free throw worth in basketball?",
        "answer1": "1",
        "answer2": "2",
        "answer3": "3",
        "answer4": "4",
        "correct answer no": 1
        },
        {
        "question no": 3,
        "question": "What is the term for a baseball player who only bats and does not play a defensive position in the American League?",
        "answer1": "Relief Pitcher",
        "answer2": "Designated Hitter",
        "answer3": "Closer",
        "answer4": "Pinch Runner",
        "correct answer no": 2
        },
        {
        "question no": 4,
        "question": "In which city were the first modern Olympic Games held in 1896?",
        "answer1": "London",
        "answer2": "Paris",
        "answer3": "Athens",
        "answer4": "Rome",
        "correct answer no": 3
        },
        {
        "question no": 5,
        "question": "What is the only Grand Slam tennis tournament played on a clay court?",
        "answer1": "US Open",
        "answer2": "Wimbledon",
        "answer3": "Australian Open",
        "answer4": "French Open (Roland Garros)",
        "correct answer no": 4
        },
        {
        "question no": 6,
        "question": "What is the term for a score of one stroke under par on a single hole in golf?",
        "answer1": "Bogey",
        "answer2": "Birdie",
        "answer3": "Eagle",
        "answer4": "Albatross",
        "correct answer no": 2
        },
        {
        "question no": 7,
        "question": "The martial art and sport of judo originated in which country?",
        "answer1": "China",
        "answer2": "South Korea",
        "answer3": "Japan",
        "answer4": "Thailand",
        "correct answer no": 3
        },
        {
        "question no": 8,
        "question": "How many points is a touchdown worth in American football before the extra point or two-point conversion attempt?",
        "answer1": "3",
        "answer2": "5",
        "answer3": "6",
        "answer4": "7",
        "correct answer no": 3
        },
        {
        "question no": 9,
        "question": "What is the standard duration of one period in a professional ice hockey game (e.g., NHL)?",
        "answer1": "15 minutes",
        "answer2": "20 minutes",
        "answer3": "25 minutes",
        "answer4": "30 minutes",
        "correct answer no": 2
        },
        {
        "question no": 10,
        "question": "Which track and field event involves throwing a heavy spherical object?",
        "answer1": "Javelin Throw",
        "answer2": "Discus Throw",
        "answer3": "Hammer Throw",
        "answer4": "Shot Put",
        "correct answer no": 4
        }
    ]
    }"""#self.generator(json_prompt, num_return_sequences=1, temperature=0.7, top_p=0.95)[0].get("generated_text", "")
        raw = generated.strip()
        body = self._strip_prompt_echo(raw, json_prompt)
        body = self._strip_until_first_marker(body)

        parsed_json = self._try_json_parse(body)
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