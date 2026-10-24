import json
import logging
import time

from ..config import settings
from ..db import SessionLocal
from ..models import Document, Profile
from ..rules import safety_text
from .llm import structured
from .prompts import SUMMARY_PROMPT, SUMMARY_RETRY, TRANSLATE_PROMPT
from .schemas import Summary

log = logging.getLogger(__name__)
CRITICAL_MSG = "This value is far outside the usual range. Please contact a doctor promptly."
CRITICAL_ACTIONS = [
    "The app flagged an extracted result as critically high or low. Check the value and date on the original report. If it is recent and has not already been addressed, contact the ordering clinician or an urgent medical service now for guidance.",
    "If you have severe or rapidly worsening symptoms, call local emergency services now. Do not wait for this app or change medicines based on this summary.",
]
STATUS = {"L": "Low", "H": "High", "LL": "Critically low", "HH": "Critically high"}
CRITICAL_ACTIONS_TRANSLATED = {
    "hi": [
        "ऐप ने रिपोर्ट से निकाले गए नतीजे को गंभीर रूप से कम या अधिक चिह्नित किया है। मूल रिपोर्ट और तारीख जाँचें। यदि यह हाल का नतीजा है और इस पर पहले कार्रवाई नहीं हुई है, तो सलाह के लिए अभी रिपोर्ट लिखने वाले डॉक्टर या तत्काल चिकित्सा सेवा से संपर्क करें।",
        "गंभीर या तेजी से बिगड़ते लक्षण हों तो स्थानीय आपातकालीन सेवा को अभी कॉल करें। इस ऐप का इंतज़ार न करें और इस सारांश के आधार पर दवा न बदलें।",
    ],
    "te": [
        "యాప్ నివేదిక నుంచి తీసిన ఫలితాన్ని విమర్శనాత్మకంగా ఎక్కువ లేదా తక్కువగా గుర్తించింది. అసలు నివేదిక, తేదీని తనిఖీ చేయండి. ఇది ఇటీవలి ఫలితం అయి, ఇంకా వైద్యుడితో చర్చించకపోతే, సూచనల కోసం ఇప్పుడే నివేదిక ఇచ్చిన వైద్యుడిని లేదా అత్యవసర వైద్య సేవను సంప్రదించండి.",
        "తీవ్రమైన లేదా వేగంగా పెరుగుతున్న లక్షణాలు ఉంటే స్థానిక అత్యవసర సేవలకు ఇప్పుడే కాల్ చేయండి. ఈ యాప్ కోసం వేచి ఉండకండి; ఈ సారాంశం ఆధారంగా మందులు మార్చవద్దు.",
    ],
    "ta": [
        "அறிக்கையிலிருந்து எடுக்கப்பட்ட முடிவு மிகக் குறைவாக அல்லது மிக அதிகமாக இருப்பதாக செயலி குறித்துள்ளது. அசல் அறிக்கையையும் தேதியையும் சரிபார்க்கவும். இது சமீபத்திய முடிவாக இருந்து, இதுவரை கவனிக்கப்படவில்லை என்றால், வழிகாட்டுதலுக்காக அறிக்கையை வழங்கிய மருத்துவர் அல்லது அவசர மருத்துவ சேவையை இப்போதே தொடர்புகொள்ளவும்.",
        "கடுமையான அல்லது வேகமாக மோசமடையும் அறிகுறிகள் இருந்தால், உள்ளூர் அவசர சேவையை இப்போதே அழைக்கவும். இந்தச் செயலிக்காகக் காத்திருக்க வேண்டாம்; இந்தச் சுருக்கத்தை வைத்து மருந்துகளை மாற்ற வேண்டாம்.",
    ],
}
LANGS = {"hi": "Hindi", "te": "Telugu", "ta": "Tamil"}


def _val(o: dict) -> str:
    return " ".join(str(x) for x in (o["value_num"], o["unit"]) if x is not None)


def _abnormal(record: dict) -> list[dict]:
    return [{"test": o["display_name"], "value": _val(o), "status": STATUS[o["interpretation"]],
             "code": o["interpretation"], "reference": [o["ref_low"], o["ref_high"]],
             "test_explainer": o["explainer"]}
            for o in record["observations"] if o["interpretation"] in STATUS]


def template_summary(record: dict, abnormal: list[dict]) -> dict:
    """Deterministic fallback built straight from the record: no LLM, nothing to get wrong."""
    kind = record["doc_type"].replace("_", " ")
    meds = record["medications"]
    fracture_points = []
    for injury in record.get("fractures_or_injuries") or []:
        if not isinstance(injury, dict):
            continue
        details = [
            str(injury.get("side")) if injury.get("side") and injury.get("side") != "not_stated" else "",
            str(injury.get("body_site")) if injury.get("body_site") else "",
            str(injury.get("injury_type")) if injury.get("injury_type") else "",
        ]
        description = " ".join(part for part in details if part)
        finding = injury.get("reported_findings")
        if finding:
            description = f"{description}: {finding}" if description else str(finding)
        if description:
            fracture_points.append(f"Reported injury finding (review original report): {description}")

    women = record.get("womens_health")
    women_points = []
    if isinstance(women, dict):
        for field, label in (
            ("pregnancy_status", "Pregnancy status reported"),
            ("last_menstrual_period", "Last menstrual period reported"),
            ("estimated_due_date", "Estimated due date reported"),
            ("gestational_age", "Gestational age reported"),
            ("trimester", "Trimester reported"),
            ("gravida", "Gravida reported"),
            ("para", "Para reported"),
            ("pregnancy_complications", "Reported pregnancy complications"),
            ("prenatal_visits_or_tests", "Prenatal visits or tests reported"),
            ("delivery_date", "Delivery date reported"),
            ("postpartum_notes", "Postpartum notes"),
            ("menstrual_history", "Menstrual history reported"),
            ("reproductive_health_notes", "Reproductive-health notes"),
            ("cervical_screening", "Cervical screening reported"),
            ("breast_health_notes", "Breast-health notes"),
            ("menopause_or_fertility_notes", "Menopause or fertility notes"),
        ):
            value = women.get(field)
            if value is not None and value != "" and value != [] and value != "unknown":
                women_points.append(f"{label}: {value}")
        if women_points:
            women_points.append("Women's-health information requires clinician review.")

    return {
        "headline": f"Summary of your {kind}" + (f" dated {record['doc_date']}" if record["doc_date"] else ""),
        "key_points": ([f"{len(record['observations'])} test result(s) were read."] if record["observations"] else [])
                      + ([f"{len(meds)} medicine(s) were listed."] if meds else [])
                      + [f"Diagnosis listed: {c['name']}" for c in record["conditions"]]
                      + ([f"{len(abnormal)} result(s) are outside the usual range."] if abnormal else [])
                      + fracture_points + women_points,
        "abnormal_explanations": [
            {"test": a["test"], "value": a["value"], "status": a["status"],
             "what_it_means": a["test_explainer"] or "This result is outside the reference range.",
             "common_reasons": "", "question_for_doctor": f"What could explain my {a['test']} result?"}
            for a in abnormal],
        "medicines_explained": [
            {"name": m["brand_name"], "general_purpose": m["salt"] or "",
             "how_to_take": " ".join(x for x in [m["dose_pattern"], m["timing"], m["duration_days"] and f"for {m['duration_days']} days"] if x)}
            for m in meds],
        "urgent_actions": CRITICAL_ACTIONS.copy() if any(
            a["code"] in ("LL", "HH") for a in abnormal
        ) else [],
        "next_steps": ["Discuss this document with your doctor."] + ([record["follow_up"]] if record["follow_up"] else []),
    }


def build_summary(record: dict) -> dict:
    abnormal = _abnormal(record)
    critical = [a for a in abnormal if a["code"] in ("LL", "HH")]
    rest = [a for a in abnormal if a["code"] not in ("LL", "HH")]
    # the LLM only ever sees non-critical values; critical ones get the fixed message
    llm_in = {k: record[k] for k in ("doc_type", "doc_date", "impression", "follow_up")}
    llm_in |= {
        "diagnoses": [c["name"] for c in record["conditions"]],
        "abnormal": rest,
        "medicines": [
            {k: m[k] for k in ("brand_name", "salt", "strength", "dose_pattern", "timing", "duration_days")}
            for m in record["medications"]
        ],
        # Include only facts already extracted from the source document.
        "fractures_or_injuries": record.get("fractures_or_injuries") or [],
        "womens_health": record.get("womens_health"),
    }
    prompt = SUMMARY_PROMPT.format(record=json.dumps(llm_in, default=str, ensure_ascii=False))
    summary = None
    try:
        llm = structured(settings.TEXT_MODEL, Summary)
        for attempt in range(2):  # regenerate once on a banned phrase
            t0 = time.time()
            out = llm.invoke(prompt).model_dump()
            log.info("summary call %s took %.1fs", attempt + 1, time.time() - t0)
            hits = safety_text.check(out)
            if not hits:
                summary = out
                break
            prompt += SUMMARY_RETRY.format(hits=", ".join(hits))
    except Exception:
        log.exception("summary LLM failed; using template")
    if summary is None:
        return template_summary(record, abnormal)
    summary["urgent_actions"] = CRITICAL_ACTIONS.copy() if critical else []
    allowed = {a["test"] for a in rest}
    summary["abnormal_explanations"] = [
        {"test": c["test"], "value": c["value"], "status": c["status"], "what_it_means": CRITICAL_MSG,
         "common_reasons": "", "question_for_doctor": f"What should I do about my {c['test']} result?"}
        for c in critical
    ] + [e for e in summary["abnormal_explanations"] if e["test"] in allowed]
    return summary


def translate_summary(summary: dict, lang: str) -> dict:
    out = structured(settings.TEXT_MODEL, Summary).invoke(TRANSLATE_PROMPT.format(language=LANGS[lang], summary=json.dumps(summary, ensure_ascii=False)))
    translated = out.model_dump()
    if summary.get("urgent_actions"):
        translated["urgent_actions"] = CRITICAL_ACTIONS_TRANSLATED[lang]
    return translated


def summarize(state):
    summary = build_summary(state["record"])  # model calls happen outside any DB session, so SQLite isn't locked
    with SessionLocal() as db:
        lang = db.get(Profile, state["profile_id"]).user.preferred_language
    i18n = None
    if lang in LANGS:  # translate now so the reader's language is ready when they open it
        try:
            i18n = {lang: translate_summary(summary, lang)}
        except Exception:
            log.exception("pre-translation failed; it will run on demand")
    with SessionLocal() as db:
        doc = db.get(Document, state["document_id"])
        doc.summary, doc.summary_i18n, doc.status = summary, i18n, "done"
        db.commit()
    return {}
