from groq import Groq
import os

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def generate_answer(question, level, background, language="auto"):
    
    lang_instruction = ""

    if language == "ar":
        lang_instruction = "Respond ONLY in Arabic. Do NOT use English."
    elif language == "fr":
        lang_instruction = "Réponds UNIQUEMENT en français. N'utilise pas l'anglais."
    elif language == "en":
        lang_instruction = "Respond ONLY in English."
    else:
        lang_instruction = "Respond in the SAME language as the question."
        
    prompt = f"""
    You are an AI tutor.
    {lang_instruction}
    Explain the following topic for a {level} learner.
    Background: {background}

    Language rules:
    - If language = "auto": respond in SAME language as the question
    - Otherwise: respond strictly in {language}
    Rules:
    - Keep the answer clear and concise
    - Do NOT use symbols like ** or markdown
    - Maximum 150 words
    - Adapt your explanation based on student level:
    
        - beginner → simple words + examples
        - intermediate → moderate explanation + some details
        - advanced → technical explanation + deeper concepts
    
    Student level: {level}
    Background: {background}
    - Structure the answer like this:

    <b>Definition:<b>
    ...
    
    <b>Explanation:<b>
    ...
    
    <b>Example:<b>
    ...
    
    <b>Question:<b>
    {question}
    """
   
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content

import json

def generate_quiz_ai(topic, level, language="en"):

    prompt = f"""
Generate 5 high-quality multiple-choice questions about:{topic}

Level: {level}
Language: {language}

Rules:
- Questions must be diverse and cover different concepts
- Each question has 4 choices
- Only 1 correct answer
- No repetition
- Clear educational style
- Return ONLY valid JSON

Format:
[
  {{
    "question": "...",
    "choices": ["...", "...", "...", "..."],
    "answer": "..."
  }}
]
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.choices[0].message.content.strip()

    # تنظيف
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except:
        print("❌ JSON ERROR:", text)
        return []