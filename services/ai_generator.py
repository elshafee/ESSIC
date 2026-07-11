"""
services/ai_generator.py
Multi-provider AI text generation with automatic rate-limit failover.
Provider order: Gemini → Groq → DeepSeek
"""
import os
import re
import logging

logger = logging.getLogger(__name__)

# ─── Recipient normalization ──────────────────────────────────────────────────
RECIPIENT_MAP = {
    "it department": "إدارة تقنية المعلومات",
    "it": "إدارة تقنية المعلومات",
    "hr": "إدارة الموارد البشرية",
    "hr department": "إدارة الموارد البشرية",
    "finance department": "الإدارة المالية",
    "finance": "الإدارة المالية",
    "president": "السيد الأستاذ الدكتور/ رئيس الجامعة",
    "dean": "السيد الأستاذ الدكتور/ عميد الكلية",
    "vice dean": "السيد الأستاذ الدكتور/ وكيل الكلية",
}


def normalize_recipient(recipient: str) -> str:
    key = recipient.strip().lower()
    if key in RECIPIENT_MAP:
        return RECIPIENT_MAP[key]
    return recipient


# ─── System prompts ────────────────────────────────────────────────────────────
STYLE_DESCRIPTION = """الأسلوب الرسمي المطلوب: يبدأ بتحية افتتاحية دبلوماسية ("يسعدنا أن نتوجه لشخصكم الكريم بخالص آيات التحية والتقدير...")،
ثم ينتقل بعبارات وصل رسمية مثل "نود أن نلفت عنايتكم الكريمة إلى ..." أو "نتشرف بإحاطة سيادتكم بـ ..." لعرض السياق،
ثم يستخدم صيغة التماس مهذبة مثل "نلتمس من سيادتكم التكرم بـ ..." أو "نرجو التكرم بالموافقة على ..." لصياغة الطلب،
ثم جملة تؤكد الفائدة أو الأثر المتوقع،
وينتهي بجملة شكر وتطلع للرد مثل "نشكركم على اهتمامكم ودعمكم المستمر، ونأمل التكرم بالرد في أقرب وقت ممكن."
التزم بهذا الإيقاع والمفردات الرسمية العامة، لكن ابنِ كل جملة من جديد بناءً على محتوى المسودة الفعلي أدناه — لا يوجد نص جاهز لنسخه هنا."""

LETTER_SYSTEM = f"""أنت محرر مراسلات رسمية محترف متخصص في صياغة الخطابات الإدارية باللغة العربية الفصحى الرسمية.
مهمتك: إعادة صياغة وتحرير النص المقدم إليك ليكون خطاباً رسمياً متكاملاً ومضبوطاً.

{STYLE_DESCRIPTION}

يجب أن يتكون جسم الخطاب من الفقرات التالية بالترتيب، ولا يجوز حذف أي منها أو دمجها في فقرة واحدة مختصرة:
1. فقرة افتتاحية قصيرة (جملة أو جملتان) للتحية والتقديم.
2. فقرة السياق: اشرح خلفية الموضوع وسببه بالتفصيل، مستندًا حصريًا إلى كل ما ورد في "المسودة / الفكرة الرئيسية" — لا تختصر أو تُسقط أي تفصيل تقني أو رقم أو اسم ورد فيها.
3. فقرة الطلب: صغ الطلب أو المطلوب تحديدًا بوضوح تام، بحيث يفهم القارئ بالضبط ماذا يُطلب منه أن يفعل.
4. فقرة الأثر/الفائدة: اشرح بجملتين على الأقل الفائدة المتوقعة من تلبية هذا الطلب، بما يتعلق تحديدًا بموضوع الطلب نفسه (وليس بموضوع عام آخر).
5. فقرة ختامية: الشكر والتطلع للرد.

القواعد الصارمة:
- استخدم اللغة العربية الفصحى الرسمية فقط
- الأسلوب: رسمي، مهذب، محترم، دبلوماسي
- لا تكتب خطابًا مختصرًا — يجب تغطية الفقرات الخمس أعلاه جميعها بالتفصيل
- لا تضف أي نص خارج الخطاب نفسه
- لا تضف تعليقات أو ملاحظات أو عناوين أو أرقام الفقرات
- لا تكتب أسطر المرسل أو المرسل إليه أو الموضوع أو التوقيع
- أعد فقط نص جسم الخطاب
- حافظ على جميع المعلومات التقنية والأسماء والأرقام كما هي"""

REQUEST_SYSTEM = f"""أنت محرر مراسلات رسمية محترف متخصص في صياغة المذكرات والطلبات الإدارية باللغة العربية الفصحى الرسمية.
مهمتك: إعادة صياغة وتحرير النص المقدم إليك ليكون طلباً رسمياً متكاملاً ومضبوطاً.

{STYLE_DESCRIPTION}

يجب أن يتكون جسم الطلب من الفقرات التالية بالترتيب:
1. فقرة افتتاحية قصيرة للتحية والتقديم.
2. فقرة السياق بالتفصيل.
3. فقرة الطلب بوضوح تام.
4. فقرة الأثر/الفائدة بجملتين على الأقل.
5. فقرة ختامية: الشكر والتطلع للرد.

القواعد الصارمة:
- استخدم اللغة العربية الفصحى الرسمية فقط
- الأسلوب: رسمي، واضح، مباشر، مهذب
- لا تكتب طلبًا مختصرًا — يجب تغطية الفقرات الخمس جميعها
- لا تضف تعليقات أو أرقام فقرات
- لا تكتب أسطر المرسل أو المرسل إليه أو التوقيع
- أعد فقط نص جسم الطلب
- حافظ على جميع الأرقام والأسماء كما هي"""


# ─── Text cleanup ─────────────────────────────────────────────────────────────
_GLITCH_SCRIPT_RE = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]')
_GLUED_LATIN_RE = re.compile(r'(?<=[\u0600-\u06FF])[a-zA-Z]{1,6}(?=[\u0600-\u06FF])')


def _clean_output(text: str) -> str:
    text = _GLITCH_SCRIPT_RE.sub('', text)
    text = _GLUED_LATIN_RE.sub('', text)
    # Extract from <text>...</text> tags if present
    match = re.search(r'<text>(.*?)</text>', text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text


# ─── API Key helpers ──────────────────────────────────────────────────────────
def _get_fernet():
    """Return a Fernet cipher for encrypting/decrypting API keys."""
    from cryptography.fernet import Fernet
    key = os.environ.get("FERNET_KEY")
    if not key:
        # Auto-generate on first run and write to .env
        new_key = Fernet.generate_key().decode()
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        with open(env_path, "a") as f:
            f.write(f"\nFERNET_KEY={new_key}\n")
        os.environ["FERNET_KEY"] = new_key
        key = new_key
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_api_key(raw_key: str) -> str:
    """Encrypt a plaintext API key for storage in the DB."""
    if not raw_key or not raw_key.strip():
        return ""
    return _get_fernet().encrypt(raw_key.strip().encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    """Decrypt a stored API key. Returns empty string on failure."""
    if not encrypted:
        return ""
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except Exception:
        return ""


def get_user_keys(user_email: str) -> dict:
    """Load and decrypt API keys for the given user from the DB."""
    try:
        from models import User
        user = User.query.filter_by(email=user_email).first()
        if not user:
            return {}
        return {
            "gemini": decrypt_api_key(user.gemini_api_key or ""),
            "groq": decrypt_api_key(user.groq_api_key or ""),
            "deepseek": decrypt_api_key(user.deepseek_api_key or ""),
        }
    except Exception:
        return {}


# ─── Provider callers ─────────────────────────────────────────────────────────
def _call_gemini(api_key: str, system: str, user_msg: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash-latest",
        system_instruction=system,
    )
    response = model.generate_content(user_msg)
    return response.text


def _call_groq(api_key: str, system: str, user_msg: str) -> str:
    from groq import Groq
    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=2048,
        temperature=0.4,
    )
    return resp.choices[0].message.content


def _call_deepseek(api_key: str, system: str, user_msg: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=2048,
        temperature=0.4,
    )
    return resp.choices[0].message.content


def _is_rate_limit_error(e: Exception) -> bool:
    """Check if an exception is a rate-limit / quota error."""
    err_str = str(e).lower()
    return any(kw in err_str for kw in [
        "rate limit", "ratelimit", "429", "quota", "resource_exhausted",
        "too many requests", "rateLimitExceeded", "tokens per"
    ])


# ─── Main generation function ─────────────────────────────────────────────────
def generate_arabic_text(
    doc_type: str,
    sender: str,
    recipient: str,
    subject: str,
    raw_draft: str,
    user_email: str = "",
) -> dict:
    """
    Generate formal Arabic letter/request body text using cloud AI providers.
    Tries Gemini → Groq → DeepSeek, failing over on rate-limit errors.
    """
    system_prompt = LETTER_SYSTEM if doc_type == "letter" else REQUEST_SYSTEM
    type_label = "خطاب رسمي" if doc_type == "letter" else "طلب رسمي"
    recipient_ar = normalize_recipient(recipient)

    user_message = f"""قم بصياغة {type_label} رسمي بناءً على المعلومات التالية:

المرسل: {sender}
المرسل إليه: {recipient_ar}
الموضوع: {subject}

المسودة / الفكرة الرئيسية:
{raw_draft}

اكتب {type_label} كاملاً يغطي الفقرات الخمس المطلوبة بالتفصيل.
تذكر وضع النص النهائي بين <text> و </text> ولا تكتب أي كلمة أخرى خارجها."""

    # Load user API keys
    keys = get_user_keys(user_email) if user_email else {}

    PROVIDERS = [
        ("Gemini",   keys.get("gemini", ""),   _call_gemini),
        ("Groq",     keys.get("groq", ""),     _call_groq),
        ("DeepSeek", keys.get("deepseek", ""), _call_deepseek),
    ]

    last_error = None
    tried = []

    for name, api_key, caller in PROVIDERS:
        if not api_key:
            logger.info(f"Skipping {name}: no API key configured.")
            continue
        try:
            logger.info(f"Trying provider: {name}")
            raw = caller(api_key, system_prompt, user_message)
            text = _clean_output(raw)
            if len(text.split()) < 30:
                raise ValueError(f"Output too short ({len(text.split())} words)")
            return {"success": True, "text": text, "model": name}
        except Exception as e:
            tried.append(name)
            if _is_rate_limit_error(e):
                logger.warning(f"{name} rate limited, failing over. Error: {e}")
                last_error = f"{name} rate limited"
                continue
            else:
                logger.error(f"{name} failed with non-rate-limit error: {e}")
                last_error = str(e)
                continue

    # All providers failed or had no keys
    if not tried:
        return {
            "success": False,
            "error": "لم يتم تكوين أي مفاتيح API. يرجى إضافة مفتاح API في صفحة الإعدادات.",
        }
    return {
        "success": False,
        "error": f"فشل الاتصال بجميع مزودي الذكاء الاصطناعي. آخر خطأ: {last_error}",
    }


def get_available_models() -> list:
    return ["Gemini 1.5 Flash", "Groq LLaMA-3.1-70B", "DeepSeek Chat"]


def build_full_document_text(generated_body: str) -> str:
    text = generated_body.strip()
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text