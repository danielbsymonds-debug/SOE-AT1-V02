from transformers import pipeline
import re

class QuizAI:
    def __init__(self, subject="General Knowledge", difficulty="advanced", model_name="gpt2"):
        self.subject = subject
        self.difficulty = difficulty
        # Load a text-generation pipeline
        # Note: this can be slow; keep one instance around and update its attributes for different subjects/difficulties.
        self.generator = pipeline("text-generation", model=model_name)

    def generate_questions(self, num_questions=3):
        """
        Generate `num_questions` multiple-choice questions.

        Returns a list of dicts:
            {
              "question": "...",
              "options": ["A) ...", "B) ...", "C) ...", "D) ..."],   # may be empty if parsing failed
              "answer": "A"   # letter A-D
            }
        The parsing is defensive against unexpected generator output.
        """
        questions = []
        for i in range(num_questions):
            prompt = (
                f"Create a {self.difficulty} multiple-choice exam question in {self.subject}. "
                f"Include 4 answer choices labeled A), B), C), D) and mark the correct one using a line like 'Answer: A'."
            )

            # Generate text (may contain newlines)
            generated = self.generator(prompt, max_length=200, num_return_sequences=1,
                                       temperature=0.8, top_p=0.9)[0]["generated_text"]
            result = generated.strip()

            # Default fallbacks
            question_text = ""
            options = []
            answer = "A"

            # Robust parsing: find option lines and answer line using safe regexes
            try:
                # Find option lines that start with A), B), C), or D) (multiline)
                # This will pick up lines like "A) Option text"
                opt_matches = re.findall(r'^[A-D]\)\s*(.+)$', result, flags=re.M)
                if opt_matches:
                    # Prepend letter labels so we keep the original A)/B)/... labels
                    # re.findall returned just the text after the label; build full options
                    letters = ['A)', 'B)', 'C)', 'D)']
                    # If generator included labels in the result (e.g., "A) foo"), opt_matches should preserve order A-D
                    options = []
                    # Try to recover label order: search for lines beginning with each label
                    for lbl in letters:
                        m = re.search(rf'^{re.escape(lbl)}\s*(.+)$', result, flags=re.M)
                        if m:
                            options.append(f"{lbl} {m.group(1).strip()}")
                    # If the above didn't populate (unlikely), fall back to using opt_matches with letters
                    if not options:
                        for idx, text in enumerate(opt_matches[:4]):
                            lbl = letters[idx] if idx < len(letters) else f"{chr(ord('A')+idx)})"
                            options.append(f"{lbl} {text.strip()}")

                # Find the declared answer like "Answer: A" or "Correct: A"
                a_match = re.search(r'(?:Answer|Correct)\s*:\s*([A-D])', result, flags=re.I)
                if a_match:
                    answer = a_match.group(1).upper()

                # Question text: everything before the first option label (A)) or the first blank line if no options
                first_option = re.search(r'^[A-D]\)', result, flags=re.M)
                if first_option:
                    question_text = result[:first_option.start()].strip()
                else:
                    # use the first non-empty line(s) as question text
                    lines = [ln.strip() for ln in result.splitlines() if ln.strip()]
                    question_text = lines[0] if lines else result

                # If question_text still contains the label or is empty, fallback
                if not question_text:
                    # fallback to the first sentence or entire result
                    q_fallback = re.split(r'\n', result, maxsplit=1)[0].strip()
                    question_text = q_fallback

            except re.error:
                # If any regex fails, do a safe fallback parse
                lines = [ln.strip() for ln in result.splitlines() if ln.strip()]
                # first non-empty line as question
                question_text = lines[0] if lines else result
                # try to find options by simple scanning for lines starting with A),B),C),D)
                options = []
                for ln in lines[1:]:
                    if re.match(r'^[A-D]\)', ln):
                        options.append(ln)
                    if len(options) >= 4:
                        break
                # try to find answer token
                try:
                    a_match = re.search(r'([A-D])', lines[-1]) if lines else None
                    if a_match:
                        answer = a_match.group(1).upper()
                except Exception:
                    answer = "A"

            # Normalize: ensure options is a list of up to 4 strings, answer is A-D
            if not isinstance(options, list):
                options = []

            # Ensure answer is one of A-D
            if not re.match(r'^[A-D]$', answer):
                answer = "A"

            questions.append({
                "question": question_text,
                "options": options,
                "answer": answer
            })

        return questions

    def grade(self, questions, user_answers):
        score = 0
        for q, ans in zip(questions, user_answers):
            # Some questions may expect option label letters (A/B/C/D) or full text.
            if not isinstance(ans, str):
                continue
            if ans.strip().upper() == q.get("answer", "A"):
                score += 1
            else:
                # If user submitted full option text instead of letter, compare to option contents
                opt_list = q.get("options") or []
                for idx, opt in enumerate(opt_list):
                    # opt like "A) The answer text"
                    # match either label or text
                    if ans.strip().upper() == chr(ord('A') + idx):
                        if q.get("answer", "A") == chr(ord('A') + idx):
                            score += 1
                        break
                    # compare raw text portion
                    # remove leading "A) " if present
                    raw = re.sub(r'^[A-D]\)\s*', '', opt).strip()
                    if ans.strip().lower() == raw.lower():
                        if q.get("answer", "A") == chr(ord('A') + idx):
                            score += 1
                        break
        return score, len(questions)