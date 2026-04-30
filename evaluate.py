from pydantic import BaseModel
from typing import List

class AnswerItem(BaseModel):
    question: str
    selected: str

class EvaluationRequest(BaseModel):
    level: str
    answers: List[AnswerItem]

def evaluate_quiz(user_answers, quiz):
    score = 0
    feedback = []

    for q, user_a in zip(quiz["quiz"]["questions"], user_answers):
        correct = q["answer"]
        is_correct = user_a.selected == correct

        if is_correct:
            score += 1

        feedback.append({
            "question": q["question"],
            "selected": user_a.selected,
            "correct": correct,
            "is_correct": is_correct
        })

    return {
        "score": score,
        "total": len(quiz["quiz"]["questions"]),
        "feedback": feedback
    }

