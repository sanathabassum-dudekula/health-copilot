import json
from pathlib import Path

translations = {
    "hi": {
        "aria": "Lumi AI सहायक का पूर्वावलोकन",
        "name": "Lumi",
        "meet": "Lumi से मिलें",
        "tagline": "आपका स्वास्थ्य साथी",
        "description": "आपके स्वास्थ्य को बेहतर ढंग से समझने में मदद, जल्द आ रही है।",
        "comingSoon": "AI सहायक — जल्द आ रहा है",
        "mobileComingSoon": "आपका स्वास्थ्य साथी — जल्द आ रहा है",
        "preview": "पूर्वावलोकन",
    },
    "te": {
        "aria": "Lumi AI సహాయకుడి ప్రివ్యూ",
        "name": "Lumi",
        "meet": "Lumiని కలవండి",
        "tagline": "మీ ఆరోగ్య సహచరుడు",
        "description": "మీ ఆరోగ్యాన్ని మరింత స్పష్టంగా అర్థం చేసుకోవడంలో సహాయం త్వరలో అందుబాటులోకి వస్తుంది.",
        "comingSoon": "AI సహాయకుడు — త్వరలో",
        "mobileComingSoon": "మీ ఆరోగ్య సహచరుడు — త్వరలో",
        "preview": "ప్రివ్యూ",
    },
    "ta": {
        "aria": "Lumi AI உதவியாளர் முன்னோட்டம்",
        "name": "Lumi",
        "meet": "Lumi-ஐ சந்திக்கவும்",
        "tagline": "உங்கள் ஆரோக்கியத் துணை",
        "description": "உங்கள் ஆரோக்கியத்தை இன்னும் தெளிவாகப் புரிந்துகொள்ள உதவி விரைவில் வருகிறது.",
        "comingSoon": "AI உதவியாளர் — விரைவில்",
        "mobileComingSoon": "உங்கள் ஆரோக்கியத் துணை — விரைவில்",
        "preview": "முன்னோட்டம்",
    },
}

for lang, replacements in translations.items():
    path = Path("src/i18n") / f"{lang}.json"
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    data.setdefault("assistant", {}).update(replacements)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    json.loads(path.read_text(encoding="utf-8"))
    print(f"OK: {lang}.json updated and validated")

print("Done. Only the assistant translation labels were updated.")
