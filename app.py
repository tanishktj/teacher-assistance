import os
import json
import boto3
import base64
import ssl
import urllib3
import requests as req_lib
from flask import Flask, render_template, request, jsonify, session, Response, redirect, url_for
from dotenv import load_dotenv
from sarvamai import SarvamAI
from translations import TRANSLATIONS, LANGUAGE_NAMES

# Suppress SSL warnings for development
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Fix SSL certificate verification issues
ssl._create_default_https_context = ssl._create_unverified_context

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-me")

# Template context processor to inject translations
@app.context_processor
def inject_translations():
    lang = session.get('language', 'en')
    return {
        't': TRANSLATIONS.get(lang, TRANSLATIONS['en']),
        'current_lang': lang,
        'language_names': LANGUAGE_NAMES
    }



# Initialize Sarvam client
sarvam_client = SarvamAI(api_subscription_key=os.environ.get("SARVAM_API_KEY"))

# AWS Bedrock Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

# Initialize Bedrock client
bedrock_client = None
try:
    bedrock_client = boto3.client(
        service_name="bedrock-runtime",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )
except Exception as e:
    print(f"Warning: Could not initialize Bedrock client: {e}")

# Load student data
def load_students():
    with open("data/students.json", "r") as f:
        return json.load(f)

# Available classes and subjects
CLASSES = {
    "9": "Class 9",
    "10": "Class 10"
}

SUBJECTS = {
    "science": {
        "name": "Science",
        "sub_subjects": {
            "physics": "Physics",
            "chemistry": "Chemistry",
            "biology": "Biology"
        }
    },
    "mathematics": {
        "name": "Mathematics",
        "sub_subjects": {
            "algebra": "Algebra",
            "geometry": "Geometry",
            "trigonometry": "Trigonometry",
            "statistics": "Statistics",
            "number_systems": "Number Systems",
            "coordinate_geometry": "Coordinate Geometry",
            "mensuration": "Mensuration"
        }
    },
    "english": {
        "name": "English",
        "sub_subjects": {
            "literature": "Literature",
            "grammar": "Grammar",
            "writing": "Writing Skills"
        }
    },
    "social_science": {
        "name": "Social Science",
        "sub_subjects": {
            "history": "History",
            "geography": "Geography",
            "political_science": "Political Science",
            "economics": "Economics"
        }
    },
    "hindi": {
        "name": "Hindi",
        "sub_subjects": {
            "hindi_literature": "Hindi Literature",
            "hindi_grammar": "Hindi Grammar",
            "hindi_writing": "Hindi Writing Skills"
        }
    }
}

# CBSE topics for each sub-subject and class
CBSE_TOPICS = {
    "9": {
        # Science
        "physics": [
            "Motion", "Force and Laws of Motion", "Gravitation",
            "Work and Energy", "Sound"
        ],
        "chemistry": [
            "Matter in Our Surroundings", "Is Matter Around Us Pure",
            "Atoms and Molecules", "Structure of the Atom"
        ],
        "biology": [
            "The Fundamental Unit of Life", "Tissues",
            "Diversity in Living Organisms", "Why Do We Fall Ill",
            "Natural Resources", "Improvement in Food Resources"
        ],
        # Mathematics
        "algebra": [
            "Polynomials", "Linear Equations in Two Variables"
        ],
        "geometry": [
            "Lines and Angles", "Triangles", "Quadrilaterals",
            "Circles", "Constructions"
        ],
        "trigonometry": [
            "Introduction to Trigonometry"
        ],
        "statistics": [
            "Statistics", "Probability"
        ],
        "number_systems": [
            "Number Systems", "Real Numbers"
        ],
        "coordinate_geometry": [
            "Coordinate Geometry"
        ],
        "mensuration": [
            "Areas of Parallelograms and Triangles",
            "Surface Areas and Volumes", "Herons Formula"
        ],
        # English
        "literature": [
            "Beehive - The Fun They Had", "Beehive - The Sound of Music",
            "Beehive - The Little Girl", "Beehive - A Truly Beautiful Mind",
            "Beehive - The Snake and the Mirror", "Beehive - My Childhood",
            "Beehive - Reach for the Top", "Beehive - Kathmandu",
            "Moments - The Lost Child", "Moments - The Adventures of Toto",
            "Moments - Iswaran the Storyteller", "Moments - In the Kingdom of Fools"
        ],
        "grammar": [
            "Tenses", "Subject-Verb Agreement", "Reported Speech",
            "Active and Passive Voice", "Determiners",
            "Modals", "Clauses"
        ],
        "writing": [
            "Letter Writing", "Story Writing", "Diary Entry",
            "Article Writing", "Paragraph Writing",
            "Notice Writing", "Message Writing"
        ],
        # Social Science
        "history": [
            "The French Revolution", "Socialism in Europe and the Russian Revolution",
            "Nazism and the Rise of Hitler", "Forest Society and Colonialism",
            "Pastoralists in the Modern World"
        ],
        "geography": [
            "India - Size and Location", "Physical Features of India",
            "Drainage", "Climate", "Natural Vegetation and Wildlife",
            "Population"
        ],
        "political_science": [
            "What is Democracy Why Democracy", "Constitutional Design",
            "Electoral Politics", "Working of Institutions",
            "Democratic Rights"
        ],
        "economics": [
            "The Story of Village Palampur", "People as Resource",
            "Poverty as a Challenge", "Food Security in India"
        ],
        # Hindi
        "hindi_literature": [
            "दो बैलों की कथा", "ल्हासा की ओर", "उपभोक्तावाद की संस्कृति",
            "साँवले सपनों की याद", "नाना साहब की पुत्री",
            "प्रेमचंद के फटे जूते", "मेरे बचपन के दिन"
        ],
        "hindi_grammar": [
            "उपसर्ग और प्रत्यय", "समास", "अलंकार",
            "वाक्य भेद", "पद परिचय", "रस"
        ],
        "hindi_writing": [
            "अनुच्छेद लेखन", "पत्र लेखन", "संवाद लेखन",
            "विज्ञापन लेखन", "सूचना लेखन", "अनौपचारिक पत्र"
        ]
    },
    "10": {
        # Science
        "physics": [
            "Light - Reflection and Refraction", "Human Eye and Colourful World",
            "Electricity", "Magnetic Effects of Electric Current",
            "Sources of Energy"
        ],
        "chemistry": [
            "Chemical Reactions and Equations", "Acids, Bases and Salts",
            "Metals and Non-metals", "Carbon and its Compounds",
            "Periodic Classification of Elements"
        ],
        "biology": [
            "Life Processes", "Control and Coordination",
            "How do Organisms Reproduce", "Heredity and Evolution",
            "Our Environment"
        ],
        # Mathematics
        "algebra": [
            "Polynomials", "Pair of Linear Equations in Two Variables",
            "Quadratic Equations", "Arithmetic Progressions"
        ],
        "geometry": [
            "Triangles", "Circles", "Constructions"
        ],
        "trigonometry": [
            "Introduction to Trigonometry",
            "Some Applications of Trigonometry"
        ],
        "statistics": [
            "Statistics", "Probability"
        ],
        "number_systems": [
            "Real Numbers"
        ],
        "coordinate_geometry": [
            "Coordinate Geometry"
        ],
        "mensuration": [
            "Areas Related to Circles",
            "Surface Areas and Volumes"
        ],
        # English
        "literature": [
            "First Flight - A Letter to God", "First Flight - Nelson Mandela",
            "First Flight - Two Stories about Flying", "First Flight - From the Diary of Anne Frank",
            "First Flight - The Hundred Dresses", "First Flight - Glimpses of India",
            "First Flight - Madam Rides the Bus", "First Flight - The Sermon at Benares",
            "Footprints - A Triumph of Surgery", "Footprints - The Thiefs Story",
            "Footprints - The Midnight Visitor", "Footprints - The Hack Driver"
        ],
        "grammar": [
            "Tenses", "Modals", "Subject-Verb Agreement",
            "Reported Speech", "Active and Passive Voice",
            "Clauses", "Determiners", "Prepositions"
        ],
        "writing": [
            "Formal Letter Writing", "Informal Letter Writing",
            "Article Writing", "Story Writing",
            "Analytical Paragraph Writing", "Email Writing",
            "Notice Writing", "Message Writing"
        ],
        # Social Science
        "history": [
            "The Rise of Nationalism in Europe", "Nationalism in India",
            "The Making of a Global World", "The Age of Industrialisation",
            "Print Culture and the Modern World"
        ],
        "geography": [
            "Resources and Development", "Forest and Wildlife Resources",
            "Water Resources", "Agriculture", "Minerals and Energy Resources",
            "Manufacturing Industries", "Lifelines of National Economy"
        ],
        "political_science": [
            "Power Sharing", "Federalism",
            "Democracy and Diversity", "Gender Religion and Caste",
            "Popular Struggles and Movements", "Political Parties",
            "Outcomes of Democracy", "Challenges to Democracy"
        ],
        "economics": [
            "Development", "Sectors of the Indian Economy",
            "Money and Credit", "Globalisation and the Indian Economy",
            "Consumer Rights"
        ],
        # Hindi
        "hindi_literature": [
            "सूरदास - पद", "तुलसीदास - राम-लक्ष्मण-परशुराम संवाद",
            "देव - सवैया और कवित्त", "जयशंकर प्रसाद - आत्मकथ्य",
            "सूर्यकांत त्रिपाठी निराला - उत्साह और अट नहीं रही",
            "नागार्जुन - यह दंतुरहित मुस्कान", "बालगोबिन भगत",
            "लखनवी अंदाज़", "मानवीय करुणा की दिव्य चमक"
        ],
        "hindi_grammar": [
            "रस", "अलंकार", "छंद",
            "वाक्य भेद", "पद परिचय",
            "समास", "मुहावरे और लोकोक्तियाँ"
        ],
        "hindi_writing": [
            "निबंध लेखन", "पत्र लेखन", "विज्ञापन लेखन",
            "सूचना लेखन", "संदेश लेखन", "अनुच्छेद लेखन",
            "ईमेल लेखन"
        ]
    }
}


def get_system_prompt(grade, sub_subject, students, gender="male"):
    student_summary = f"You have {len(students)} students in Class {grade}."

    # Gender-specific instruction
    gender_instruction = ""
    if gender == "female":
        gender_instruction = """
👩 GENDER-SPECIFIC LANGUAGE REQUIREMENT:
You are speaking as a FEMALE teacher. Use feminine forms in your language:
- Hindi: Use feminine verb forms (मैं समझाती हूं, मैं बताती हूं, मैं देती हूं)
- Hinglish: Use feminine forms (Main samjhati hoon, Main batati hoon)
- Other languages: Use appropriate feminine forms
- First person: "I explain..." (as a female teacher)

Examples:
✅ Hindi: "मैं आपको समझाती हूं कि..."
✅ Hinglish: "Main aapko samjhati hoon ki..."
❌ NEVER use: "मैं समझाता हूं" (masculine)
"""
    else:
        gender_instruction = """
👨 GENDER-SPECIFIC LANGUAGE REQUIREMENT:
You are speaking as a MALE teacher. Use masculine forms in your language:
- Hindi: Use masculine verb forms (मैं समझाता हूं, मैं बताता हूं, मैं देता हूं)
- Hinglish: Use masculine forms (Main samjhata hoon, Main batata hoon)
- Other languages: Use appropriate masculine forms
- First person: "I explain..." (as a male teacher)

Examples:
✅ Hindi: "मैं आपको समझाता हूं कि..."
✅ Hinglish: "Main aapko samjhata hoon ki..."
❌ NEVER use: "मैं समझाती हूं" (feminine)
"""

    return f"""🌍 MULTILINGUAL RESPONSE REQUIREMENT - HIGHEST PRIORITY 🌍

YOU MUST RESPOND IN THE SAME LANGUAGE AS THE USER'S QUESTION.

LANGUAGE MATCHING RULES (FOLLOW EXACTLY):
1. English (Latin script: A-Z, a-z) → Respond in ENGLISH ONLY
2. Hindi (Devanagari: अ-ह, क-ज्ञ) → Respond in HINDI ONLY (using Devanagari script)
3. Hinglish (Mix of English+Hindi in Latin script, like "kya haal hai") → Respond in HINGLISH (English letters but Hindi/English mix)
4. Tamil (Tamil script: அ-ஹ) → Respond in TAMIL ONLY
5. Telugu (Telugu script: అ-హ) → Respond in TELUGU ONLY
6. Bengali (Bengali script: অ-হ) → Respond in BENGALI ONLY
7. Gujarati (Gujarati script: અ-હ) → Respond in GUJARATI ONLY
8. Kannada (Kannada script: ಅ-ಹ) → Respond in KANNADA ONLY
9. Malayalam (Malayalam script: അ-ഹ) → Respond in MALAYALAM ONLY
10. Marathi (Devanagari script) → Respond in MARATHI ONLY
11. Punjabi (Gurmukhi script: ਅ-ਹ) → Respond in PUNJABI ONLY
12. Odia (Odia script: ଅ-ହ) → Respond in ODIA ONLY

CRITICAL EXAMPLES:
❌ WRONG: User asks "What is force?" → You respond "बल क्या है? बल..."
✅ CORRECT: User asks "What is force?" → You respond "Force is a push or pull..."

❌ WRONG: User asks "बल क्या है?" → You respond "Force is..."
✅ CORRECT: User asks "बल क्या है?" → You respond "बल एक धक्का या खिंचाव है..."

❌ WRONG: User asks "force kya hai" → You respond "Force is..."
✅ CORRECT: User asks "force kya hai" → You respond "Force ek push ya pull hai jo..."

DETECTION STRATEGY:
- Check the FIRST character/word of user's message
- If Latin alphabet (A-Z) with English words → ENGLISH response
- If Latin alphabet with Hindi/mixed words → HINGLISH response
- If Devanagari script → HINDI/MARATHI response (use context to differentiate)
- If Tamil/Telugu/Bengali/Gujarati/etc script → Respond in THAT script

{gender_instruction}

---

You are an intelligent Teaching Assistant for a CBSE Class {grade} {sub_subject.title()} teacher.

Your capabilities:
1. **Subject Planner**: Create detailed lesson plans for any topic with learning objectives, activities, and time allocation.
2. **Quiz Generator**: Generate MCQ and short-answer quizzes on selected topics with answer keys.
3. **Solved Examples**: Provide step-by-step solved examples for numerical and conceptual problems.
4. **Student Context**: {student_summary}

Guidelines:
- Follow CBSE curriculum standards strictly.
- Make explanations clear and age-appropriate for Class {grade} students.
- When generating quizzes, include 5-10 questions with difficulty levels (Easy/Medium/Hard).
- For solved examples, show each step clearly with reasoning.
- When asked for a lesson plan, include: Topic, Duration, Learning Objectives, Prerequisites, Teaching Method, Activities, Assessment, and Homework.

Always be helpful, concise, and educational in your responses."""


def chat_with_llm(messages):
    """Send messages to AWS Bedrock and get response."""
    if not bedrock_client:
        return "⚠️ AWS Bedrock client not initialized. Please check your AWS credentials in the .env file."

    if not AWS_ACCESS_KEY_ID or AWS_ACCESS_KEY_ID == "your_access_key_here":
        return "⚠️ Please set your AWS credentials in the .env file:\n- AWS_ACCESS_KEY_ID\n- AWS_SECRET_ACCESS_KEY\n- AWS_REGION"

    # Build the messages for Bedrock (Claude format)
    system_prompt = ""
    bedrock_messages = []

    for msg in messages:
        if msg["role"] == "system":
            system_prompt = msg["content"]
        else:
            # Merge consecutive messages with the same role
            if bedrock_messages and bedrock_messages[-1]["role"] == msg["role"]:
                bedrock_messages[-1]["content"].append({"type": "text", "text": msg["content"]})
            else:
                bedrock_messages.append({
                    "role": msg["role"],
                    "content": [{"type": "text", "text": msg["content"]}]
                })

    # Ensure messages start with a user message
    if bedrock_messages and bedrock_messages[0]["role"] != "user":
        bedrock_messages = bedrock_messages[1:]

    # Bedrock request body for Claude models
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "temperature": 0.7,
        "messages": bedrock_messages
    }

    if system_prompt:
        request_body["system"] = system_prompt

    try:
        response = bedrock_client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(request_body)
        )

        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"]

    except bedrock_client.exceptions.AccessDeniedException:
        return "🚫 Access denied. Make sure your AWS IAM user/role has `bedrock:InvokeModel` permission."
    except bedrock_client.exceptions.ValidationException as e:
        return f"⚠️ Validation error: {str(e)}"
    except Exception as e:
        return f"❌ Error communicating with Bedrock: {str(e)}"





@app.route("/change_language/<lang>")
def change_language(lang):
    """Change the interface language."""
    if lang in LANGUAGE_NAMES:
        session['language'] = lang
    return redirect(request.referrer or url_for('index'))


@app.route("/")
def index():
    """Landing page - Select class."""
    return render_template("index.html", classes=CLASSES)


@app.route("/subjects/<grade>")
def subjects(grade):
    """Subject selection page."""
    if grade not in CLASSES:
        return "Invalid class selected", 404
    session["grade"] = grade
    return render_template("subjects.html", grade=grade, subjects=SUBJECTS)


@app.route("/sub_subjects/<grade>/<subject>")
def sub_subjects(grade, subject):
    """Sub-subject selection page."""
    if grade not in CLASSES or subject not in SUBJECTS:
        return "Invalid selection", 404
    session["grade"] = grade
    session["subject"] = subject
    sub_subs = SUBJECTS[subject]["sub_subjects"]
    subject_name = SUBJECTS[subject]["name"]
    return render_template("sub_subjects.html", grade=grade, subject=subject,
                           sub_subjects=sub_subs, subject_name=subject_name)


@app.route("/chat/<grade>/<sub_subject>")
def chat(grade, sub_subject):
    """Chatbot page."""
    if grade not in CLASSES:
        return "Invalid class", 404

    topics = CBSE_TOPICS.get(grade, {}).get(sub_subject, [])
    students = load_students()
    grade_students = [s for s in students if s["grade"] == int(grade)]

    session["grade"] = grade
    session["sub_subject"] = sub_subject

    # Find parent subject for breadcrumb
    parent_subject = None
    parent_subject_name = None
    for subj_key, subj_data in SUBJECTS.items():
        if sub_subject in subj_data["sub_subjects"]:
            parent_subject = subj_key
            parent_subject_name = subj_data["name"]
            break

    return render_template("chat.html", grade=grade, sub_subject=sub_subject,
                           topics=topics, student_count=len(grade_students),
                           username='Teacher', parent_subject=parent_subject,
                           parent_subject_name=parent_subject_name)


def detect_language(text):
    """Detect the language of the input text based on script/characters."""
    if not text:
        return "English"

    # Sample first 50 characters for detection
    sample = text[:50]

    # Count character types
    devanagari = sum(1 for c in sample if 'ऀ' <= c <= 'ॿ')
    tamil = sum(1 for c in sample if '஀' <= c <= '௿')
    telugu = sum(1 for c in sample if 'ఀ' <= c <= '౿')
    bengali = sum(1 for c in sample if 'ঀ' <= c <= '৿')
    gujarati = sum(1 for c in sample if '઀' <= c <= '૿')
    kannada = sum(1 for c in sample if 'ಀ' <= c <= '೿')
    malayalam = sum(1 for c in sample if 'ഀ' <= c <= 'ൿ')
    gurmukhi = sum(1 for c in sample if '਀' <= c <= '੿')
    odia = sum(1 for c in sample if '଀' <= c <= '୿')
    latin = sum(1 for c in sample if ('a' <= c.lower() <= 'z'))

    # Determine language based on dominant script
    if tamil > 2:
        return "Tamil"
    elif telugu > 2:
        return "Telugu"
    elif bengali > 2:
        return "Bengali"
    elif gujarati > 2:
        return "Gujarati"
    elif kannada > 2:
        return "Kannada"
    elif malayalam > 2:
        return "Malayalam"
    elif gurmukhi > 2:
        return "Punjabi"
    elif odia > 2:
        return "Odia"
    elif devanagari > 2:
        # Check if it's Hindi or Marathi (default to Hindi for CBSE context)
        return "Hindi"
    elif latin > 2:
        # Check if it's English or Hinglish
        # Simple heuristic: if contains common Hindi words in Latin, it's Hinglish
        import re
        hinglish_words = ['kya', 'hai', 'hain', 'aur', 'ka', 'ki', 'ke', 'mein', 'main',
                          'hoon', 'ho', 'kaise', 'kahan', 'kyun', 'kab', 'kaun', 'batao',
                          'bataiye', 'dijiye', 'karo', 'kare', 'nahi', 'nahin', 'achha',
                          'thik', 'samjho', 'samjhe', 'seekho', 'padho', 'bataye', 'padhaiye']
        lower_text = text.lower()
        # Use word boundary matching to avoid false positives
        if any(re.search(r'\b' + word + r'\b', lower_text) for word in hinglish_words):
            return "Hinglish"
        return "English"
    else:
        return "English"


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """API endpoint for chatbot."""
    data = request.json
    user_message = data.get("message", "")
    grade = data.get("grade", session.get("grade", "9"))
    sub_subject = data.get("sub_subject", session.get("sub_subject", "physics"))
    history = data.get("history", [])
    detected_lang = data.get("detected_language", None)  # From STT if available
    gender = data.get("gender", "male")  # Get selected gender from frontend

    students = load_students()
    grade_students = [s for s in students if s["grade"] == int(grade)]

    system_prompt = get_system_prompt(grade, sub_subject, grade_students, gender)

    # Detect language from the message text
    if not detected_lang:
        detected_lang = detect_language(user_message)

    # Create language instruction prefix for the message
    lang_map = {
        "en-IN": "English",
        "hi-IN": "Hindi",
        "ta-IN": "Tamil",
        "te-IN": "Telugu",
        "bn-IN": "Bengali",
        "gu-IN": "Gujarati",
        "kn-IN": "Kannada",
        "ml-IN": "Malayalam",
        "mr-IN": "Marathi",
        "pa-IN": "Punjabi",
        "od-IN": "Odia"
    }

    # If detected_lang is a language code from STT, map it
    if detected_lang in lang_map:
        language_name = lang_map[detected_lang]
    else:
        language_name = detected_lang

    # Add explicit language instruction to the user message
    enhanced_message = f"[Language: {language_name}] {user_message}"

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-10:]:  # Keep last 10 messages for context
        messages.append(msg)
    messages.append({"role": "user", "content": enhanced_message})

    response = chat_with_llm(messages)

    return jsonify({"response": response, "detected_language": language_name})


@app.route("/api/students/<int:grade>")
def api_students(grade):
    """API endpoint to get students by grade."""
    students = load_students()
    grade_students = [s for s in students if s["grade"] == grade]
    return jsonify(grade_students)


@app.route("/api/stt/transcribe", methods=["POST"])
def stt_transcribe():
    """STT transcription using file upload to Sarvam REST API."""
    SARVAM_KEY = os.environ.get("SARVAM_API_KEY")
    if not SARVAM_KEY:
        return jsonify({"error": "SARVAM_API_KEY not configured"}), 500

    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files['audio']

    try:
        # Use Sarvam's REST API for speech-to-text
        headers = {
            "api-subscription-key": SARVAM_KEY
        }

        files = {
            "file": (audio_file.filename, audio_file, audio_file.content_type)
        }

        data = {
            "model": "saaras:v3",
            "language_code": "unknown"  # Auto-detect language
        }

        response = req_lib.post(
            "https://api.sarvam.ai/speech-to-text",
            headers=headers,
            files=files,
            data=data,
            timeout=30,
            verify=False
        )

        if response.status_code == 200:
            result = response.json()
            return jsonify({
                "transcript": result.get("transcript", ""),
                "language_code": result.get("language_code", "en-IN")
            })
        else:
            return jsonify({
                "error": f"Sarvam API error: {response.status_code}",
                "details": response.text
            }), response.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tts/stream", methods=["GET", "POST"])
def tts_stream():
    """TTS endpoint using Sarvam REST API for reliable audio generation."""
    SARVAM_KEY = os.environ.get("SARVAM_API_KEY")
    if not SARVAM_KEY:
        return jsonify({"error": "SARVAM_API_KEY not configured"}), 500

    # Support both GET and POST
    if request.method == "GET":
        text = request.args.get("text", "")
        lang = request.args.get("language_code", "en-IN")
        speaker = request.args.get("speaker", "shubh")
    else:
        body = request.get_json()
        text = body.get("text", "")
        lang = body.get("language_code", "en-IN")
        speaker = body.get("speaker", "shubh")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    # TTS language fallback — bulbul:v2 supports only these 11
    SUPPORTED_TTS_LANGS = {
        "hi-IN", "bn-IN", "ta-IN", "te-IN", "gu-IN",
        "kn-IN", "ml-IN", "mr-IN", "pa-IN", "od-IN", "en-IN"
    }
    if lang not in SUPPORTED_TTS_LANGS:
        lang = "en-IN"

    # Validate speaker
    VALID_SPEAKERS = ["shubh", "pooja"]
    if speaker not in VALID_SPEAKERS:
        speaker = "shubh"

    # Sarvam TTS REST API has a text limit (~500 chars), so split if needed
    MAX_CHUNK_LEN = 480
    text_chunks = []
    while len(text) > MAX_CHUNK_LEN:
        # Try to split at sentence boundary
        split_idx = text.rfind('.', 0, MAX_CHUNK_LEN)
        if split_idx == -1:
            split_idx = text.rfind(' ', 0, MAX_CHUNK_LEN)
        if split_idx == -1:
            split_idx = MAX_CHUNK_LEN
        text_chunks.append(text[:split_idx + 1].strip())
        text = text[split_idx + 1:].strip()
    if text:
        text_chunks.append(text)

    try:
        audio_parts = []

        for chunk in text_chunks:
            payload = {
                "inputs": [chunk],
                "target_language_code": lang,
                "speaker": speaker,
                "model": "bulbul:v3"
            }

            headers = {
                "api-subscription-key": SARVAM_KEY,
                "Content-Type": "application/json"
            }

            response = req_lib.post(
                "https://api.sarvam.ai/text-to-speech",
                headers=headers,
                json=payload,
                timeout=30,
                verify=False
            )

            if response.status_code == 200:
                result = response.json()
                audios = result.get("audios", [])
                if audios and audios[0]:
                    audio_bytes = base64.b64decode(audios[0])
                    audio_parts.append(audio_bytes)
                else:
                    print(f"TTS: No audio in response for chunk: {chunk[:50]}...")
            else:
                print(f"TTS API error {response.status_code}: {response.text}")

        if not audio_parts:
            return jsonify({"error": "TTS generation failed - no audio produced"}), 500

        # Combine all audio parts
        combined_audio = b"".join(audio_parts)

        return Response(
            combined_audio,
            content_type="audio/mpeg",
            headers={
                "Content-Length": str(len(combined_audio)),
                "Cache-Control": "no-cache"
            }
        )

    except Exception as e:
        print(f"TTS error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5002, threaded=True)
