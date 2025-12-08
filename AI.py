# ai_module.py
from transformers import pipeline
import re

class QuizAI:
    def __init__(self, subject="General Knowledge", difficulty="advanced", model_name="gpt2"):
        self.subject = subject
        self.difficulty = difficulty
        # Load a text-generation pipeline
        self.generator = pipeline("text-generation", model=model_name)

    def generate_questions(self, num_questions=3):
        questions = []
        for i in range(num_questions):
            prompt = (
                f"Create a {self.difficulty} multiple-choice exam question in {self.subject}. "
                f"Include 4 answer choices labeled A), B), C), D) and mark the correct one."
            )
            result = self.generator(prompt, max_length=200, num_return_sequences=1,
                                    temperature=0.8, top_p=0.9)[0]["generated_text"]

            # Simple regex parsing to extract question, options, and answer
            q_match = re.search(r"(.*?)A\)", result, re.S)
            if q_match:
                question_text = q_match.group(1).strip()
            else:
                question_text = result.strip()

            options = []
            for opt in ["A)", "B)", "C)", "D)"]:
                opt_match = re.search(rf"{opt}(.*?)(?=[A-D]\)|Answer:|$)", result, re.S)
                if opt_match:
                    options.append(f"{opt} {opt_match.group(1).strip()}")

            answer_match = re.search(r"Answer:\s*([A-D])", result)
            answer = answer_match.group(1) if answer_match else "A"

            questions.append({
                "question": question_text,
                "options": options,
                "answer": answer
            })
        return questions

    def grade(self, questions, user_answers):
        score = 0
        for q, ans in zip(questions, user_answers):
            if ans.upper() == q["answer"]:
                score += 1
        return score, len(questions)