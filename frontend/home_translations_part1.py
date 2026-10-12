import json
from pathlib import Path

folder = Path("src/i18n")

translations = {
    "en": {
        "brand": "Your Health, Clearly Connected",
        "logoAlt": "CuraMind logo",
        "welcomeTitle": "A healthier view starts here.",
        "welcomeText": "Keep your medical records, reports, and health history organised in one protected place.",
        "private": "Private",
        "personal": "Personal",
        "connected": "Connected",
        "language": "Language",
        "chooseProfile": "Choose your profile",
        "chooseProfileText": "Select whose health records you want to view. Each person should have a separate, protected health profile.",
        "profiles": "Your profiles",
        "profilesSub": "Start with your personal health records.",
        "loading": "Loading your profile…",
        "loadError": "We couldn't load your profile. Check that the health service is running.",
        "myProfile": "My Profile",
        "myRecords": "My health records",
        "continueRecords": "Continue to records",
        "profileSettings": "Profile settings",
        "profileSettingsText": "Update personal details, language, and ABHA information.",
        "manageProfile": "Manage profile",
        "profileUnavailable": "Your profile could not be loaded. Please check the backend connection and refresh this page.",
        "familyProfiles": "Family profiles",
        "familyText": "Keep each family member’s health history separate and protected.",
        "noFamily": "No linked family profiles yet",
        "noFamilyText": "Add a family member after secure account linking is available. A phone number alone will not grant access to anyone’s medical records.",
        "closeForm": "Close form",
        "addFamily": "Add family member",
        "familyNotReady": "Family profiles are not connected to secure account storage yet. Your details have not been saved. We will connect this form after the family-account backend is ready.",
        "familyDetails": "Family member details",
        "previewOnly": "Preview only. These details are not saved until secure family-account storage is implemented.",
        "basicInfo": "Basic information",
        "fullName": "Full name *",
        "fullNamePlaceholder": "Enter full name",
        "dob": "Date of birth",
        "age": "Age (optional if date of birth is entered)",
        "agePlaceholder": "Age in years",
        "gender": "Gender",
        "selectGender": "Select gender (optional)",
        "female": "Female",
        "male": "Male",
        "other": "Other",
        "preferNot": "Prefer not to say",
        "bloodType": "Blood type",
        "unknownBlood": "Unknown / not provided",
        "medicalInfo": "Medical information",
        "allergies": "Allergies",
        "allergiesPlaceholder": "Known allergies or reactions",
        "conditions": "Existing conditions and medical history",
        "conditionsPlaceholder": "Conditions, surgeries, fractures, or other relevant history",
        "medicines": "Current medicines and dosages",
        "medicinesPlaceholder": "Medicine names, dosages, and frequency if known",
        "previousRecords": "Previous medical records",
        "previousRecordsPlaceholder": "Previous reports, prescriptions, diagnoses, or record notes",
        "emergencyContact": "Emergency contact (optional)",
        "optionalFields": "Both fields can be left blank.",
        "contactName": "Contact name",
        "contactNamePlaceholder": "Emergency contact name",
        "contactPhone": "Contact phone number",
        "contactPhonePlaceholder": "Optional phone number",
        "requiredNote": "* Required fields. Family details are not saved yet. ABHA access requires secure identity verification and permission.",
        "reviewSetup": "Review setup requirements",
        "footer": "Family access and cross-device syncing require secure account verification and permission controls."
    }
}

# Save this starter dictionary separately.
Path("home_translations_part1.json").write_text(
    json.dumps(translations, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("Part 1 saved successfully. No existing translation files were changed.")
