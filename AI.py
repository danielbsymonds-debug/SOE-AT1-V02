import re
import json
import logging
from time import sleep
from transformers import pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QuizAI:
    def __init__(self, subject="General Knowledge", difficulty="advanced", model_name="gpt2"):
        self.subject = subject
        self.difficulty = difficulty
        # Keep a single generator instance (may be slow to init)
        self.generator = pipeline("text-generation", model=model_name)

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
            f"Generate a JSON array of exactly {num_questions} multiple-choice questions about {subj}.\n"
            "Each item must be an object with keys: \"question\" (string), \"options\" (array of 4 strings labeled 'A) ...'), and \"answer\" (a single letter A-D).\n"
            "Example:\n"
            '[{"question":"Q?","options":["A) ...","B) ...","C) ...","D) ..."],"answer":"B"}]\n'
            "Output only valid JSON (no commentary)."
        )

        for attempt in range(max_retries):
            try:
                generated = self.generator(json_prompt, max_length=512, num_return_sequences=1,
                                           temperature=0.7, top_p=0.95)[0].get("generated_text", "")
                raw = generated.strip()
                body = self._strip_prompt_echo(raw, json_prompt)
                body = self._strip_until_first_marker(body)

                parsed_json = self._try_json_parse(body)
                if parsed_json and len(parsed_json) == num_questions:
                    normalized = []
                    for item in parsed_json:
                        q = (item.get('question') or "").strip()
                        opts = item.get('options') or []
                        ans = (item.get('answer') or 'A').strip().upper()
                        if not isinstance(opts, list):
                            opts = []
                        if not re.match(r'^[A-D]$', ans):
                            ans = 'A'
                        normalized.append({"question": q, "options": opts, "answer": ans, "raw": body})
                    # final quick validation
                    if all(n['question'] for n in normalized):
                        logger.info("JSON parse success")
                        return normalized
                # else try again
            except Exception:
                logger.exception("JSON generation attempt failed")
            sleep(0.15)

        # Second: try textual multi-question prompt (numbered)
        text_prompt = (
            f"Create exactly {num_questions} {diff} multiple-choice questions about {subj}.\n"
            "Number them 1., 2., ... Each question should be followed by four choices labeled A), B), C), D) on separate lines and include 'Answer: X'.\n"
            "Output only the questions, choices and answer lines."
        )

        for attempt in range(max_retries):
            try:
                generated = self.generator(text_prompt, max_length=512, num_return_sequences=1,
                                           temperature=0.8, top_p=0.95)[0].get("generated_text", "")
                raw = generated.strip()
                body = self._strip_prompt_echo(raw, text_prompt)
                body = self._strip_until_first_marker(body)

                # split into blocks
                parts = re.split(r'(?m)^\s*\d+\.\s*', body)
                blocks = [p.strip() for p in parts if p.strip()]
                if len(blocks) < num_questions:
                    parts2 = re.split(r'(?mi)^\s*question\s*\d+[:.\s]*', body)
                    blocks = [p.strip() for p in parts2 if p.strip()]
                if len(blocks) < num_questions:
                    parts3 = re.split(r'\n\s*\n', body)
                    blocks = [p.strip() for p in parts3 if p.strip()]

                parsed = [self._parse_single_block(blk) for blk in blocks[:num_questions]]
                # validate parsed content (non-empty question)
                if len(parsed) == num_questions and all(p['question'] for p in parsed):
                    logger.info("Text multi-question parse success")
                    return parsed
            except Exception:
                logger.exception("Text multi-question attempt failed")
            sleep(0.15)

        # Last resort: generate per-question to guarantee count
        logger.info("Falling back to per-question generation")
        out = []
        for i in range(num_questions):
            prompt = (
                f"Create one {diff} multiple-choice question about {subj}.\n"
                "Provide exactly four choices labeled A), B), C), D) each on its own line, followed by 'Answer: X'.\n"
                "Output only the question, choices, and the answer line."
            )
            try:
                generated = self.generator(prompt, max_length=256, num_return_sequences=1,
                                           temperature=0.8, top_p=0.95)[0].get("generated_text", "")
                raw = generated.strip()
                body = self._strip_prompt_echo(raw, prompt)
                body = self._strip_until_first_marker(body)
                parsed = self._parse_single_block(body)
                if not parsed['question']:
                    # fallback placeholder if parsing failed
                    out.append({
                        "question": f"(auto placeholder question {i+1})",
                        "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
                        "answer": "A",
                        "raw": body
                    })
                else:
                    out.append(parsed)
            except Exception:
                logger.exception("Per-question generation failed; adding placeholder")
                out.append({
                    "question": f"(auto placeholder question {i+1})",
                    "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
                    "answer": "A",
                    "raw": generated if 'generated' in locals() else ""
                })
        return out

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