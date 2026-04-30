import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from ai_engine import generate_answer, generate_quiz_ai
from typing import Optional, List
from evaluate import EvaluationRequest, evaluate_quiz
from langdetect import detect
from pdf_engine import extract_pdf_text


USER_LEVEL_STATE = "beginner"  
USER_PROFILE = {
    "level": "beginner",
    "score_history": [],
    "weak_topics": []
}
LAST_QUIZ = None

app = FastAPI(title="GAI Personalized Learning API")

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def detect_language(text):
    try:
        return detect(text)
    except:
        return "en"


class AskRequest(BaseModel):
    question: str
    level: str = "beginner"
    background: str | None = None
    goal: str = "answer"
    language: str = "auto"

class QuizAnswer(BaseModel):
    question: str
    selected: str

class QuizSubmission(BaseModel):
    level: str
    answers: List[QuizAnswer]

class TranslateRequest(BaseModel):
    text: str
    target_language: str

class ImageRequest(BaseModel):
    prompt: str
import re

# ===== gen-diagram =====
@app.post("/generate-diagram")
async def generate_diagram(data: dict):

    user_input = data.get("prompt")
    diagram_type = data.get("type", "auto")

    # ===== TYPE HANDLING =====
    if diagram_type == "sequence":
        first_line = "sequenceDiagram"
        extra_rules = """
- Use ONLY valid sequenceDiagram syntax
- Example:
  User->>API: Request
  API->>DB: Query
- NO brackets []
- NO flowchart syntax
"""

    elif diagram_type == "architecture":
        first_line = "flowchart LR"
        extra_rules = """
- Create a SYSTEM ARCHITECTURE diagram
- Use subgraphs:
  Client Layer
  Application Layer
  AI Layer
  Data Layer
- Show clear layers and connections
"""

    elif diagram_type == "flowchart":
        first_line = "flowchart LR"
        extra_rules = """
- Create a detailed flowchart
- Use multiple steps and decisions
- Add loops if needed
"""

    else:  # 🤖 AUTO
        first_line = "flowchart LR"
        extra_rules = """
- Choose the BEST diagram style based on topic
- If topic is system → architecture
- If topic is process → flowchart
- Use subgraphs if relevant
"""

    # ===== GENERATION =====
    try:
         diagram = generate_answer(
            question=f"""
You are a senior software architect.

Generate a UNIQUE Mermaid diagram.

STRICT:
- Output ONLY Mermaid code
- First line: {first_line}
- Minimum 8-12 nodes
- Different structure EACH time
- Adapt to topic

STYLE:
- Use meaningful names (no generic A B C)
- Add parallel flows or loops
- Avoid repeating same structure
- Use icons inside nodes (👤 💻 ⚙️ 🤖 🗄️ ☁️)

{extra_rules}

Topic:
{user_input}
""",
        level="advanced",
        background="technical"
    )

    except Exception as e:
        if "rate_limit" in str(e):
            return {
                "error": "⚠️ API limit reached, try again in 1 minute"
            }
        else:
            raise HTTPException(status_code=500, detail=str(e))

    
    # ===== CLEAN =====
    diagram = diagram.strip()
    diagram = diagram.replace("```mermaid", "").replace("```", "").strip()


    # ===== FIX BAD OUTPUT =====
    if "<" in diagram or "Definition" in diagram:
        diagram = f"""{first_line}
User --> System --> Database
"""

    # ===== ENSURE VALID START =====
    if not diagram.startswith("flowchart") and not diagram.startswith("sequenceDiagram"):
        diagram = f"{first_line}\n" + diagram

    print("FINAL DIAGRAM:\n", diagram)

    return {"diagram": diagram}
    
# ===== explain-diagram =====
@app.post("/explain-diagram")
async def explain_diagram(data: dict):

    diagram = data.get("diagram")

    explanation = generate_answer(
        question=f"""
You are an expert teacher.

Explain the following diagram step by step.

RULES:
- Explain flow from start to end
- Use simple clear sentences
- No Definition / Example / Question format
- Just explain how system works
- Use paragraphs with line breaks

Diagram:
{diagram}
""",
        level="advanced",
        background="education"
    )

    return {"explanation": explanation}

# ===== PDF Upload =====
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):

    content = await file.read()

    with open("temp.pdf", "wb") as f:
        f.write(content)

    text = extract_pdf_text("temp.pdf")

    level_detect = generate_answer(
        question=f"""
    Classify this content level:
    {text[:1000]}
    
    Answer ONLY one word:
    beginner OR intermediate OR advanced
    """,
        level="advanced",
        background="analysis"
    ).lower().strip()
    
    summary = generate_answer(
        question=f"""
    Summarize this content clearly:
    
    {text[:2000]}
    
    Format EXACTLY:

    <b> 1. Main Idea <b>
    ....
    
    <b> 2. Key Concepts <b>
    ....
    
    <b> 3. Important Details <b>
    ....
    
    <b> 4. Conclusion <b>
    """,
        level=level_detect,
        background="education"
    )

    quiz = generate_quiz_ai(
        topic=text,
        level=level_detect,
    )

    return {
        "summary": summary,
        "quiz": quiz
    }
    
from fastapi import HTTPException
import traceback

@app.post("/ask")
def ask(request: AskRequest):

    global USER_PROFILE, LAST_QUIZ

    level_to_use = request.level.strip() if request.level else USER_PROFILE["level"]

    # ===== Language Detection =====
    detected_lang = detect_language(request.question)
    lang = request.language if request.language != "auto" else detect_language(request.question)

    print("LEVEL:", level_to_use)
    print("LANG:", lang)

    # ===== QUIZ =====
    if request.goal == "quiz":

        quiz_questions = generate_quiz_ai(
            topic=request.question,
            level=level_to_use,
            language=lang
        )

        LAST_QUIZ = quiz_questions
        print("QUIZ:", quiz_questions)

        return {
            "type": "quiz",
            "level": level_to_use,
            "language": lang,
            "questions": quiz_questions
        }

    # ===== ANSWER =====
    answer = generate_answer(
        question=request.question,
        level=level_to_use,
        background=request.background or "general",
        language=lang
    )

    return {
        "type": "answer",
        "level": level_to_use,
        "language": lang,
        "content": answer
    }


# ===== AI FEEDBACK FUNCTION =====
def generate_feedback(score, percentage, level):

    if percentage < 40:
        return "⚠️ You need to strengthen your basics. Focus on simple concepts and practice more."
    
    elif percentage < 75:
        return "👍 Good progress! You understand the basics, but you can improve with more practice."
    
    else:
        return "🔥 Excellent work! You are ready for more advanced topics."


# ===== EVALUATE =====
@app.post("/evaluate")
def evaluate(payload: EvaluationRequest):
    print("RECEIVED:", payload)
    global LAST_QUIZ, USER_PROFILE

    if LAST_QUIZ is None:
        return {"error": "No quiz available. Please request a quiz first."}

    score = 0
    total = len(payload.answers)

    for user_answer in payload.answers:
        for q in LAST_QUIZ:
            if q["question"] == user_answer.question:
                if q["answer"] == user_answer.selected:
                    score += 1

    percentage = round(score / total * 100, 2)

    # ===== ADAPTIVE SYSTEM =====

    USER_PROFILE["score_history"].append(percentage)
    
    avg = sum(USER_PROFILE["score_history"]) / len(USER_PROFILE["score_history"])
    
    if percentage <= 40:
        current_level = "beginner"
    elif percentage <= 75:
        current_level = "intermediate"
    else:
        current_level = "advanced"
    
    USER_PROFILE["level"] = current_level
    
    # feedback
    feedback = generate_feedback(score, percentage, current_level)
    
    # response
    return {
        "score": score,
        "total": total,
        "percentage": percentage,
        "level": current_level,      
        "feedback": feedback,
        "avg_score": round(avg, 2)   
    }

@app.get("/")
def root():
    return {"status": "Backend is running 🚀"}


@app.post("/translate")
def translate(req: TranslateRequest):

    prompt = f"""
You are a professional translator.

Translate the following JSON into {req.target_language}.

STRICT RULES:
- Only return the translated text
- Do NOT add explanations
- Do NOT add examples
- Do NOT add titles
- Do NOT change structure
- Keep JSON format EXACTLY the same
- Only translate text values
- Do NOT change keys

JSON:
{req.text}
"""

    translated = generate_answer(
        question=prompt,
        level="beginner",
        background="translation"
    )

    return {"translated": translated}