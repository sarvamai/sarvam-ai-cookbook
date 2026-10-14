"use client";

import { useState, useRef, useEffect } from "react";
import { Mic, Square, Loader2, IndianRupee, Store, Clock, Settings2, Check, User, Globe, X, History, Search, Calendar, Filter } from "lucide-react";

interface Transaction {
  id: number;
  customer_name: string;
  amount: number;
  item_description: string;
  transaction_type: string;
  created_at?: string;
}

const LANGUAGES = [
  { code: "hi-IN", name: "Hindi" },
  { code: "en-IN", name: "English" },
  { code: "ta-IN", name: "Tamil" },
  { code: "te-IN", name: "Telugu" },
  { code: "mr-IN", name: "Marathi" },
  { code: "bn-IN", name: "Bengali" },
  { code: "gu-IN", name: "Gujarati" },
  { code: "kn-IN", name: "Kannada" },
  { code: "ml-IN", name: "Malayalam" },
  { code: "pa-IN", name: "Punjabi" },
  { code: "or-IN", name: "Odia" }
];

const SPEAKERS = [
  { id: "shubh", name: "Shubh (Male)", type: "Male" },
  { id: "rahul", name: "Rahul (Male)", type: "Male" },
  { id: "priya", name: "Priya (Female)", type: "Female" },
  { id: "neha", name: "Neha (Female)", type: "Female" }
];

const UI_DICT: Record<string, Record<string, string>> = {
  "en-IN": { subtitle: "VendorVoice AI", recentActivity: "Recent Activity", allHistory: "All History", entries: "Entries", noTransactions: "No transactions yet.", tapMic: "Tap the mic and say 'Raju paid 50 rupees'", analyzing: "AI is analyzing...", translating: "Translating & updating database", udhaar: "CREDIT", paid: "PAID", generalItem: "General Item", releaseToSend: "Release to Send", holdToSpeak: "Hold to Speak", appSettings: "App Settings", aiLanguage: "AI Language", assistantVoice: "Assistant Voice", showRecent: "Show Recent", viewAll: "View All", howToUse: "How to use VendorVoice", step1Title: "Tap & Hold", step1Desc: "Press the large microphone button at the bottom of the screen.", step2Title: "Speak Entry", step2Desc: "Say the transaction naturally (e.g. 'Raju ka 50 rupaye jama karlo').", step3Title: "Auto Save", step3Desc: "Release the button. AI will instantly translate and save the record.", amount: "Amount", searchName: "Search by Name...", allMonths: "All Months", allYears: "All Years" },
  "hi-IN": { subtitle: "वेंडरवॉयस एआई", recentActivity: "हाल की गतिविधि", allHistory: "पूरा इतिहास", entries: "प्रविष्टियां", noTransactions: "कोई लेन-देन नहीं।", tapMic: "माइक दबाएं और बोलें 'राजू का 50 रुपये जमा करलो'", analyzing: "एआई विश्लेषण कर रहा है...", translating: "डेटाबेस अपडेट हो रहा है", udhaar: "उधार", paid: "जमा", generalItem: "सामान्य वस्तु", releaseToSend: "भेजने के लिए छोड़ें", holdToSpeak: "बोलने के लिए दबाए रखें", appSettings: "ऐप सेटिंग्स", aiLanguage: "एआई भाषा", assistantVoice: "सहायक की आवाज़", showRecent: "हाल का दिखाएं", viewAll: "सभी देखें", howToUse: "वेंडरवॉयस का उपयोग कैसे करें", step1Title: "दबाएं और पकड़ें", step1Desc: "स्क्रीन के नीचे बड़े माइक्रोफोन बटन को दबाएं।", step2Title: "एंट्री बोलें", step2Desc: "लेन-देन को स्वाभाविक रूप से बोलें (उदा. 'राजू का 50 रुपये जमा करलो')।", step3Title: "ऑटो सेव", step3Desc: "बटन छोड़ें। AI तुरंत अनुवाद करेगा और रिकॉर्ड सहेजेगा।", amount: "रकम", searchName: "नाम से खोजें...", allMonths: "सभी महीने", allYears: "सभी वर्ष" },
  "bn-IN": { subtitle: "ভেন্ডরভয়েস এআই", recentActivity: "সাম্প্রতিক কার্যকলাপ", allHistory: "সব ইতিহাস", entries: "এন্ট্রি", noTransactions: "কোনো লেনদেন নেই।", tapMic: "মাইক টিপে বলুন 'রাজুর ৫০ টাকা জমা করুন'", analyzing: "এআই বিশ্লেষণ করছে...", translating: "ডাটাবেস আপডেট হচ্ছে", udhaar: "বাকি", paid: "জমা", generalItem: "সাধারণ আইটেম", releaseToSend: "পাঠাতে ছেড়ে দিন", holdToSpeak: "বলতে চেপে ধরুন", appSettings: "অ্যাপ সেটিংস", aiLanguage: "এআই ভাষা", assistantVoice: "অ্যাসিস্ট্যান্ট ভয়েস", showRecent: "সাম্প্রতিক দেখান", viewAll: "সব দেখুন", howToUse: "ভেন্ডরভয়েস কীভাবে ব্যবহার করবেন", step1Title: "টিপুন এবং ধরে রাখুন", step1Desc: "পর্দার নীচে বড় মাইক্রোফোন বোতামটি টিপুন।", step2Title: "এন্ট্রি বলুন", step2Desc: "স্বাভাবিকভাবে লেনদেনটি বলুন (যেমন 'রাজুর ৫০ টাকা জমা করুন')।", step3Title: "অটো সেভ", step3Desc: "বোতামটি ছেড়ে দিন। AI তাত্ক্ষণিকভাবে অনুবাদ করে রেকর্ডটি সেভ করবে।", amount: "পরিমাণ", searchName: "নাম দিয়ে খুঁজুন...", allMonths: "সব মাস", allYears: "সব বছর" },
  "ta-IN": { subtitle: "வெண்டர்வாய்ஸ் ஏஐ", recentActivity: "சமீபத்திய செயல்பாடு", allHistory: "அனைத்து வரலாறு", entries: "உள்ளீடுகள்", noTransactions: "எந்த பரிவர்த்தனையும் இல்லை.", tapMic: "மைக்கை அழுத்தி 'ராஜு 50 ரூபாய் கொடுத்தார்' என்று சொல்லவும்", analyzing: "ஏஐ பகுப்பாய்வு செய்கிறது...", translating: "தரவுத்தளம் புதுப்பிக்கப்படுகிறது", udhaar: "கடன்", paid: "வரவு", generalItem: "பொதுவான பொருள்", releaseToSend: "அனுப்ப விடுங்கள்", holdToSpeak: "பேச அழுத்திப் பிடிக்கவும்", appSettings: "ஆப் அமைப்புகள்", aiLanguage: "ஏஐ மொழி", assistantVoice: "உதவியாளர் குரல்", showRecent: "சமீபத்தியதைக் காட்டு", viewAll: "அனைத்தையும் காண்", howToUse: "VendorVoice-வை எப்படி பயன்படுத்துவது", step1Title: "அழுத்திப் பிடிக்கவும்", step1Desc: "திரையின் கீழே உள்ள பெரிய மைக்ரோஃபோன் பொத்தானை அழுத்தவும்.", step2Title: "உள்ளீட்டை சொல்லவும்", step2Desc: "பரிவர்த்தனையை சொல்லவும் (எ.கா 'ராஜு 50 ரூபாய் கொடுத்தார்').", step3Title: "தானாக சேமி", step3Desc: "பொத்தானை விடவும். AI உடனடியாக மொழிபெயர்த்து பதிவு செய்யும்.", amount: "தொகை", searchName: "பெயரால் தேடு...", allMonths: "அனைத்து மாதங்கள்", allYears: "அனைத்து ஆண்டுகள்" },
  "te-IN": { subtitle: "వెండర్‌వాయిస్ ఏఐ", recentActivity: "ఇటీవలి కార్యాచరణ", allHistory: "మొత్తం చరిత్ర", entries: "నమోదులు", noTransactions: "లావాదేవీలు లేవు.", tapMic: "మైక్‌ను నొక్కి 'రాజు 50 రూపాయలు ఇచ్చాడు' అని చెప్పండి", analyzing: "ఏఐ విశ్లేషిస్తోంది...", translating: "డేటాబేస్ అప్‌డేట్ అవుతోంది", udhaar: "అప్పు", paid: "జమ", generalItem: "సాధారణ వస్తువు", releaseToSend: "పంపడానికి వదలండి", holdToSpeak: "మాట్లాడటానికి నొక్కి ఉంచండి", appSettings: "యాప్ సెట్టింగ్‌లు", aiLanguage: "ఏఐ భాష", assistantVoice: "సహాయకుడి వాయిస్", showRecent: "ఇటీవలివి చూపు", viewAll: "అన్నీ చూడు", howToUse: "VendorVoice ఎలా ఉపయోగించాలి", step1Title: "నొక్కి పట్టుకోండి", step1Desc: "స్క్రీన్ దిగువన ఉన్న పెద్ద మైక్రోఫోన్ బటన్‌ను నొక్కండి.", step2Title: "ఎంట్రీ చెప్పండి", step2Desc: "లావాదేవీని చెప్పండి (ఉదా. 'రాజు 50 రూపాయలు ఇచ్చాడు').", step3Title: "ఆటో సేవ్", step3Desc: "బటన్ వదలండి. AI వెంటనే అనువదించి రికార్డ్ చేస్తుంది.", amount: "మొత్తం", searchName: "పేరుతో వెతకండి...", allMonths: "అన్ని నెలలు", allYears: "అన్ని సంవత్సరాలు" },
  "mr-IN": { subtitle: "व्हेंडरव्हॉइस एआय", recentActivity: "अलीकडील घडामोडी", allHistory: "संपूर्ण इतिहास", entries: "नोंदी", noTransactions: "कोणतेही व्यवहार नाहीत.", tapMic: "माईक दाबा आणि सांगा 'राजूने 50 रुपये दिले'", analyzing: "एआय विश्लेषण करत आहे...", translating: "डेटाबेस अपडेट होत आहे", udhaar: "उधार", paid: "जमा", generalItem: "सामान्य वस्तू", releaseToSend: "पाठवण्यासाठी सोडा", holdToSpeak: "बोलण्यासाठी दाबून ठेवा", appSettings: "अॅप सेटिंग्ज", aiLanguage: "एआय भाषा", assistantVoice: "सहाय्यकाचा आवाज", showRecent: "अलीकडील दाखवा", viewAll: "सर्व पहा", howToUse: "VendorVoice कसे वापरावे", step1Title: "दाबा आणि धरून ठेवा", step1Desc: "स्क्रीनच्या तळाशी असलेले मोठे मायक्रोफोन बटण दाबा.", step2Title: "नोंद सांगा", step2Desc: "व्यवहार सांगा (उदा. 'राजूने 50 रुपये दिले').", step3Title: "ऑटो सेव्ह", step3Desc: "बटण सोडा. AI त्वरित भाषांतर करेल आणि सेव्ह करेल.", amount: "रक्कम", searchName: "नावाने शोधा...", allMonths: "सर्व महिने", allYears: "सर्व वर्षे" },
  "gu-IN": { subtitle: "વેન્ડરવોઇસ એઆઇ", recentActivity: "તાજેતરની પ્રવૃત્તિ", allHistory: "તમામ ઇતિહાસ", entries: "એન્ટ્રીઓ", noTransactions: "કોઈ લેવડદેવડ નથી.", tapMic: "માઇક દબાવો અને કહો 'રાજુએ 50 રૂપિયા આપ્યા'", analyzing: "એઆઇ વિશ્લેષણ કરી રહ્યું છે...", translating: "ડેટાબેઝ અપડેટ થઈ રહ્યો છે", udhaar: "ઉધાર", paid: "જમા", generalItem: "સામાન્ય વસ્તુ", releaseToSend: "મોકલવા માટે છોડો", holdToSpeak: "બોલવા માટે પકડી રાખો", appSettings: "એપ સેટિંગ્સ", aiLanguage: "એઆઇ ભાષા", assistantVoice: "સહાયકનો અવાજ", showRecent: "તાજેતરનું બતાવો", viewAll: "બધું જુઓ", howToUse: "VendorVoice નો ઉપયોગ કેવી રીતે કરવો", step1Title: "દબાવો અને પકડી રાખો", step1Desc: "સ્ક્રીનના તળિયે આપેલ મોટા માઇક્રોફોન બટનને દબાવો.", step2Title: "એન્ટ્રી બોલો", step2Desc: "લેવડદેવડ બોલો (દા.ત. 'રાજુએ 50 રૂપિયા આપ્યા').", step3Title: "ઓટો સેવ", step3Desc: "બટન છોડો. AI તરત જ અનુવાદ કરશે અને રેકોર્ડ સેવ કરશે.", amount: "રકમ", searchName: "નામથી શોધો...", allMonths: "તમામ મહિના", allYears: "તમામ વર્ષ" },
  "kn-IN": { subtitle: "ವೆಂಡರ್ವಾಯ್ಸ್ ಎಐ", recentActivity: "ಇತ್ತೀಚಿನ ಚಟುವಟಿಕೆ", allHistory: "ಎಲ್ಲಾ ಇತಿಹಾಸ", entries: "ನಮೂದುಗಳು", noTransactions: "ಯಾವುದೇ ವಹಿವಾಟುಗಳಿಲ್ಲ.", tapMic: "ಮೈಕ್ ಒತ್ತಿ ಮತ್ತು 'ರಾಜು 50 ರೂಪಾಯಿ ಕೊಟ್ಟರು' ಎಂದು ಹೇಳಿ", analyzing: "ಎಐ ವಿಶ್ಲೇಷಿಸುತ್ತಿದೆ...", translating: "ಡೇಟಾಬೇಸ್ ಅಪ್ಡೇಟ್ ಆಗುತ್ತಿದೆ", udhaar: "ಸಾಲ", paid: "ಜಮಾ", generalItem: "ಸಾಮಾನ್ಯ ವಸ್ತು", releaseToSend: "ಕಳುಹಿಸಲು ಬಿಡಿ", holdToSpeak: "ಮಾತನಾಡಲು ಒತ್ತಿ ಹಿಡಿಯಿರಿ", appSettings: "ಆ್ಯಪ್ ಸೆಟ್ಟಿಂಗ್‌ಗಳು", aiLanguage: "ಎಐ ಭಾಷೆ", assistantVoice: "ಸಹಾಯಕನ ಧ್ವನಿ", showRecent: "ಇತ್ತೀಚಿನದನ್ನು ತೋರಿಸಿ", viewAll: "ಎಲ್ಲವನ್ನೂ ವೀಕ್ಷಿಸಿ", howToUse: "VendorVoice ಅನ್ನು ಹೇಗೆ ಬಳಸುವುದು", step1Title: "ಒತ್ತಿ ಮತ್ತು ಹಿಡಿಯಿರಿ", step1Desc: "ಪರದೆಯ ಕೆಳಭಾಗದಲ್ಲಿರುವ ದೊಡ್ಡ ಮೈಕ್ರೊಫೋನ್ ಬಟನ್ ಒತ್ತಿ.", step2Title: "ನಮೂದು ಹೇಳಿ", step2Desc: "ವಹಿವಾಟನ್ನು ಹೇಳಿ (ಉದಾ. 'ರಾಜು 50 ರೂಪಾಯಿ ಕೊಟ್ಟರು').", step3Title: "ಆಟೋ ಸೇವ್", step3Desc: "ಬಟನ್ ಬಿಡಿ. AI ತಕ್ಷಣ ಅನುವಾದಿಸಿ ರೆಕಾರ್ಡ್ ಮಾಡುತ್ತದೆ.", amount: "ಮೊತ್ತ", searchName: "ಹೆಸರಿನಿಂದ ಹುಡುಕಿ...", allMonths: "ಎಲ್ಲಾ ತಿಂಗಳುಗಳು", allYears: "ಎಲ್ಲಾ ವರ್ಷಗಳು" },
  "ml-IN": { subtitle: "വെൻഡർവോയ്സ് എഐ", recentActivity: "സമീപകാല പ്രവർത്തനം", allHistory: "മുഴുവൻ ചരിത്രവും", entries: "എൻട്രികൾ", noTransactions: "ഇടപാടുകൾ ഒന്നുമില്ല.", tapMic: "മൈക്ക് അമർത്തി 'രാജു 50 രൂപ തന്നു' എന്ന് പറയുക", analyzing: "എഐ വിശകലനം ചെയ്യുന്നു...", translating: "ഡാറ്റാബേസ് അപ്‌ഡേറ്റ് ചെയ്യുന്നു", udhaar: "കടം", paid: "വരവ്", generalItem: "സാധാരണ ഇനം", releaseToSend: "അയക്കാൻ വിടുക", holdToSpeak: "സംസാരിക്കാൻ അമർത്തിപ്പിടിക്കുക", appSettings: "ആപ്പ് ക്രമീകരണങ്ങൾ", aiLanguage: "എഐ ഭാഷ", assistantVoice: "സഹായിയുടെ ശബ്ദം", showRecent: "സമീപകാലത്തേത് കാണിക്കുക", viewAll: "എല്ലാം കാണുക", howToUse: "VendorVoice എങ്ങനെ ഉപയോഗിക്കാം", step1Title: "അമർത്തിപ്പിടിക്കുക", step1Desc: "സ്ക്രീനിന്റെ താഴെയുള്ള വലിയ മൈക്രോഫോൺ ബട്ടൺ അമർത്തുക.", step2Title: "എൻട്രി പറയുക", step2Desc: "ഇടപാട് പറയുക (ഉദാഹരണത്തിന് 'രാജു 50 രൂപ തന്നു').", step3Title: "ഓട്ടോ സേവ്", step3Desc: "ബട്ടൺ വിടുക. AI പെട്ടെന്ന് പരിഭാഷപ്പെടുത്തി സേവ് ചെയ്യും.", amount: "തുക", searchName: "പേര് വഴി തിരയുക...", allMonths: "എല്ലാ മാസങ്ങളും", allYears: "എല്ലാ വർഷങ്ങളും" },
  "pa-IN": { subtitle: "ਵੈਂਡਰਵਾਇਸ ਏਆਈ", recentActivity: "ਹਾਲੀਆ ਗਤੀਵਿਧੀ", allHistory: "ਸਾਰਾ ਇਤਿਹਾਸ", entries: "ਐਂਟਰੀਆਂ", noTransactions: "ਕੋਈ ਲੈਣ-ਦੇਣ ਨਹੀਂ।", tapMic: "ਮਾਈਕ ਦਬਾਓ ਅਤੇ ਕਹੋ 'ਰਾਜੂ ਨੇ 50 ਰੁਪਏ ਦਿੱਤੇ'", analyzing: "ਏਆਈ ਵਿਸ਼ਲੇਸ਼ਣ ਕਰ ਰਿਹਾ ਹੈ...", translating: "ਡਾਟਾਬੇਸ ਅੱਪਡੇਟ ਹੋ ਰਿਹਾ ਹੈ", udhaar: "ਉਧਾਰ", paid: "ਜਮ੍ਹਾਂ", generalItem: "ਆਮ ਵਸਤੂ", releaseToSend: "ਭੇਜਣ ਲਈ ਛੱਡੋ", holdToSpeak: "ਬੋਲਣ ਲਈ ਦਬਾ ਕੇ ਰੱਖੋ", appSettings: "ਐਪ ਸੈਟਿੰਗਾਂ", aiLanguage: "ਏਆਈ ਭਾਸ਼ਾ", assistantVoice: "ਸਹਾਇਕ ਦੀ ਆਵਾਜ਼", showRecent: "ਹਾਲੀਆ ਦਿਖਾਓ", viewAll: "ਸਭ ਦੇਖੋ", howToUse: "VendorVoice ਕਿਵੇਂ ਵਰਤਣਾ ਹੈ", step1Title: "ਦਬਾਓ ਅਤੇ ਫੜੋ", step1Desc: "ਸਕਰੀਨ ਦੇ ਹੇਠਾਂ ਵੱਡੇ ਮਾਈਕ੍ਰੋਫੋਨ ਬਟਨ ਨੂੰ ਦਬਾਓ।", step2Title: "ਐਂਟਰੀ ਬੋਲੋ", step2Desc: "ਲੈਣ-ਦੇਣ ਬੋਲੋ (ਜਿਵੇਂ ਕਿ 'ਰਾਜੂ ਨੇ 50 ਰੁਪਏ ਦਿੱਤੇ').", step3Title: "ਆਟੋ ਸੇਵ", step3Desc: "ਬਟਨ ਛੱਡੋ। AI ਤੁਰੰਤ ਅਨੁਵਾਦ ਕਰੇਗਾ ਅਤੇ ਰਿਕਾਰਡ ਕਰੇਗਾ।", amount: "ਰਕਮ", searchName: "ਨਾਮ ਨਾਲ ਖੋਜੋ...", allMonths: "ਸਾਰੇ ਮਹੀਨੇ", allYears: "ਸਾਰੇ ਸਾਲ" },
  "or-IN": { subtitle: "ଭେଣ୍ଡରଭଏସ୍ ଏଆଇ", recentActivity: "ସାମ୍ପ୍ରତିକ କାର୍ଯ୍ୟକଳାପ", allHistory: "ସମସ୍ତ ଇତିହାସ", entries: "ଏଣ୍ଟ୍ରିଗୁଡିକ", noTransactions: "କୌଣସି କାରବାର ନାହିଁ |", tapMic: "ମାଇକ୍ ଦବାନ୍ତୁ ଏବଂ କୁହନ୍ତୁ 'ରାଜୁ ୫୦ ଟଙ୍କା ଦେଲେ'", analyzing: "ଏଆଇ ବିଶ୍ଳେଷଣ କରୁଛି...", translating: "ଡାଟାବେସ୍ ଅପଡେଟ୍ ହେଉଛି", udhaar: "ବାକି", paid: "ଜମା", generalItem: "ସାଧାରଣ ଆଇଟମ୍", releaseToSend: "ପଠାଇବାକୁ ଛାଡିଦିଅନ୍ତୁ", holdToSpeak: "କହିବାକୁ ଧରି ରଖନ୍ତୁ", appSettings: "ଆପ୍ ସେଟିଂସ", aiLanguage: "ଏଆଇ ଭାଷା", assistantVoice: "ସହାୟକ ସ୍ୱର", showRecent: "ସାମ୍ପ୍ରତିକ ଦେଖାନ୍ତୁ", viewAll: "ସବୁ ଦେଖନ୍ତୁ", howToUse: "VendorVoice କିପରି ବ୍ୟବହାର କରିବେ", step1Title: "ଦବାନ୍ତୁ ଏବଂ ଧରି ରଖନ୍ତୁ", step1Desc: "ସ୍କ୍ରିନର ତଳେ ଥିବା ବଡ଼ ମାଇକ୍ରୋଫୋନ୍ ବଟନ୍ ଦବାନ୍ତୁ।", step2Title: "ଏଣ୍ଟ୍ରି କୁହନ୍ତୁ", step2Desc: "କାରବାର କୁହନ୍ତୁ (ଉଦାହରଣ ସ୍ୱରୂପ 'ରାଜୁ ୫୦ ଟଙ୍କା ଦେଲେ').", step3Title: "ଅଟୋ ସେଭ୍", step3Desc: "ବଟନ୍ ଛାଡନ୍ତୁ। AI ସାଙ୍ଗେ ସାଙ୍ଗେ ଅନୁବାଦ କରି ସେଭ୍ କରିବ।", amount: "ପରିମାଣ", searchName: "ନାମ ଦ୍ୱାରା ଖୋଜନ୍ତୁ...", allMonths: "ସମସ୍ତ ମାସ", allYears: "ସମସ୍ତ ବର୍ଷ" }
};

export default function Home() {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [errorMsg, setErrorMsg] = useState("");

  // Settings State
  const [showSettings, setShowSettings] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [searchName, setSearchName] = useState("");
  const [searchMonth, setSearchMonth] = useState("");
  const [searchYear, setSearchYear] = useState("");
  const [language, setLanguage] = useState("en-IN");
  const [speaker, setSpeaker] = useState("shubh");

  const t = UI_DICT[language] || UI_DICT["en-IN"];

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);

  // Fetch initial transactions
  useEffect(() => {
    const fetchTransactions = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const res = await fetch(`${apiUrl}/transactions/`);
        if (res.ok) {
          const data = await res.json();
          setTransactions(data.reverse());
        }
      } catch (error) {
        console.error("Failed to fetch transactions:", error);
      }
    };
    fetchTransactions();
  }, []);

  const startRecording = async () => {
    if (showSettings) setShowSettings(false);
    setErrorMsg("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(chunksRef.current, { type: "audio/wav" });
        await sendAudioToBackend(audioBlob);
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error("Error accessing microphone:", error);
      setErrorMsg("Please allow microphone access to use this feature.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
    }
  };

  const sendAudioToBackend = async (audioBlob: Blob) => {
    setIsProcessing(true);
    const formData = new FormData();
    formData.append("file", audioBlob, "recording.wav");
    formData.append("language", language);
    formData.append("speaker", speaker);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const res = await fetch(`${apiUrl}/voice-transaction/`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();

      if (data.audio_base64) {
        const audio = new Audio(`data:audio/wav;base64,${data.audio_base64}`);
        audio.play();
      }

      if (data.success) {
        setTransactions((prev) => [data.transaction, ...prev]);
      } else {
        setErrorMsg(data.error_message || "Something went wrong.");
        setTimeout(() => setErrorMsg(""), 5000);
      }
    } catch (error) {
      console.error("Error uploading audio:", error);
      setErrorMsg("Failed to connect to the backend server.");
      setTimeout(() => setErrorMsg(""), 5000);
    } finally {
      setIsProcessing(false);
    }
  };

  const displayedTransactions = showHistory
    ? transactions.filter(tx => {
      let matches = true;
      if (searchName && !tx.customer_name.toLowerCase().includes(searchName.toLowerCase())) matches = false;
      if (tx.created_at) {
        const date = new Date(tx.created_at);
        if (searchMonth && (date.getMonth() + 1).toString() !== searchMonth) matches = false;
        if (searchYear && date.getFullYear().toString() !== searchYear) matches = false;
      } else if (searchMonth || searchYear) {
        matches = false;
      }
      return matches;
    })
    : transactions.slice(0, 5);

  return (
    <div className="min-h-screen bg-[#050B14] text-slate-200 font-sans selection:bg-cyan-500/30 overflow-x-hidden">
      {/* Background Glows */}
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-full max-w-[1000px] h-[500px] bg-cyan-500/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[800px] h-[400px] bg-indigo-500/10 rounded-full blur-[100px] pointer-events-none" />

      {/* Header */}
      <header className="sticky top-0 z-50 bg-[#0A101D]/80 backdrop-blur-2xl border-b border-white/5">
        <div className="max-w-7xl mx-auto px-5 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 lg:w-12 lg:h-12 bg-gradient-to-br from-cyan-400 to-blue-600 rounded-xl flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <Store className="w-5 h-5 lg:w-6 lg:h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl lg:text-2xl font-bold text-white tracking-tight leading-tight">VendorVoice</h1>
              <p className="text-[10px] lg:text-xs text-cyan-400 font-bold tracking-widest uppercase">{t.subtitle}</p>
            </div>
          </div>
          <button
            onClick={() => setShowSettings(!showSettings)}
            className={`p-2.5 lg:px-4 lg:py-2.5 rounded-full lg:rounded-xl flex items-center gap-2 transition-all duration-300 ${showSettings ? 'bg-cyan-500/20 text-cyan-400' : 'bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white'}`}
          >
            <Settings2 className="w-5 h-5" />
            <span className="hidden lg:block text-sm font-semibold">{t.appSettings}</span>
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-5 py-6 lg:py-12 pb-40 relative z-10">

        {/* Quick Start Guide */}
        {!showHistory && (
          <div className="mb-10 p-6 lg:p-8 rounded-3xl bg-gradient-to-br from-cyan-500/10 via-[#0A101D] to-indigo-500/10 border border-cyan-500/20 backdrop-blur-md shadow-lg shadow-cyan-900/20">
            <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-3">
              <span className="p-2 bg-cyan-500/20 rounded-xl"><Mic className="w-5 h-5 text-cyan-400" /></span>
              {t.howToUse || "How to use VendorVoice"}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 relative">
              {/* Connecting line for desktop */}
              <div className="hidden md:block absolute top-6 left-[15%] right-[15%] h-[2px] bg-gradient-to-r from-transparent via-cyan-500/20 to-transparent z-0" />
              
              <div className="flex flex-col items-center text-center gap-3 relative z-10">
                <div className="w-12 h-12 rounded-full bg-[#050B14] border-2 border-cyan-500/30 flex items-center justify-center text-cyan-400 font-bold text-lg shadow-[0_0_15px_rgba(6,182,212,0.2)]">1</div>
                <h3 className="font-semibold text-slate-200">{t.step1Title || "Tap & Hold"}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{t.step1Desc || "Press the large microphone button at the bottom of the screen."}</p>
              </div>
              <div className="flex flex-col items-center text-center gap-3 relative z-10">
                <div className="w-12 h-12 rounded-full bg-[#050B14] border-2 border-cyan-500/30 flex items-center justify-center text-cyan-400 font-bold text-lg shadow-[0_0_15px_rgba(6,182,212,0.2)]">2</div>
                <h3 className="font-semibold text-slate-200">{t.step2Title || "Speak Entry"}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{t.step2Desc || "Say the transaction naturally (e.g. \"Raju ka 50 rupaye jama karlo\")."}</p>
              </div>
              <div className="flex flex-col items-center text-center gap-3 relative z-10">
                <div className="w-12 h-12 rounded-full bg-[#050B14] border-2 border-cyan-500/30 flex items-center justify-center text-cyan-400 font-bold text-lg shadow-[0_0_15px_rgba(6,182,212,0.2)]">3</div>
                <h3 className="font-semibold text-slate-200">{t.step3Title || "Auto Save"}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{t.step3Desc || "Release the button. AI will instantly translate and save the record."}</p>
              </div>
            </div>
          </div>
        )}

        {/* Simple Error Popup (Toast) */}
        {errorMsg && (
          <div className="fixed top-24 left-1/2 -translate-x-1/2 z-50 w-[90%] max-w-md p-4 rounded-2xl bg-rose-500/90 backdrop-blur-xl border border-rose-400/50 text-white text-sm shadow-2xl flex items-center justify-center gap-3 animate-[bounce_0.5s_ease-out]">
            <div className="w-2 h-2 rounded-full bg-white animate-pulse" />
            <p className="font-medium text-center">{errorMsg}</p>
          </div>
        )}

        <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
          <div className="flex items-center gap-3">
            <h2 className="text-base lg:text-lg font-bold text-slate-300 tracking-wider uppercase flex items-center gap-2">
              <Clock className="w-5 h-5 text-cyan-500" /> {showHistory ? t.allHistory : t.recentActivity}
            </h2>
            {transactions.length > 0 && (
              <button
                onClick={() => setShowHistory(!showHistory)}
                className="flex items-center gap-1.5 px-4 py-1.5 bg-cyan-500/10 text-cyan-400 hover:bg-cyan-500/20 rounded-full text-xs font-semibold transition-colors border border-cyan-500/20"
              >
                <History className="w-4 h-4" />
                {showHistory ? t.showRecent : t.viewAll}
              </button>
            )}
          </div>
          <div className="flex items-center gap-3">
            <div className="px-4 py-1.5 bg-white/5 rounded-full text-sm font-semibold text-cyan-400 border border-white/5 shadow-inner">
              {showHistory ? displayedTransactions.length : transactions.length} {t.entries}
            </div>
          </div>
        </div>

        {/* Filters (Only visible when showing history) */}
        {showHistory && (
          <div className="mb-8 grid grid-cols-1 md:grid-cols-3 gap-4 animate-in fade-in slide-in-from-top-4 duration-300">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="text"
                placeholder={t.searchName || "Search by Name..."}
                value={searchName}
                onChange={(e) => setSearchName(e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-xl py-2.5 pl-10 pr-4 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/50 transition-all"
              />
            </div>
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <select
                value={searchMonth}
                onChange={(e) => setSearchMonth(e.target.value)}
                className="w-full bg-[#0A101D] border border-white/10 rounded-xl py-2.5 pl-10 pr-4 text-sm text-white focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/50 transition-all appearance-none"
              >
                <option value="">{t.allMonths || "All Months"}</option>
                <option value="1">January</option>
                <option value="2">February</option>
                <option value="3">March</option>
                <option value="4">April</option>
                <option value="5">May</option>
                <option value="6">June</option>
                <option value="7">July</option>
                <option value="8">August</option>
                <option value="9">September</option>
                <option value="10">October</option>
                <option value="11">November</option>
                <option value="12">December</option>
              </select>
            </div>
            <div className="relative">
              <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <select
                value={searchYear}
                onChange={(e) => setSearchYear(e.target.value)}
                className="w-full bg-[#0A101D] border border-white/10 rounded-xl py-2.5 pl-10 pr-4 text-sm text-white focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/50 transition-all appearance-none"
              >
                <option value="">{t.allYears || "All Years"}</option>
                <option value="2026">2026</option>
                <option value="2025">2025</option>
                <option value="2024">2024</option>
              </select>
            </div>
          </div>
        )}

        {/* Transactions Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 lg:gap-6">
          {displayedTransactions.length === 0 && !isProcessing && (
            <div className="col-span-full text-center py-20 px-4 rounded-3xl border border-dashed border-white/10 bg-white/5 backdrop-blur-sm">
              <div className="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mx-auto mb-4">
                <Mic className="w-8 h-8 text-slate-500" />
              </div>
              <p className="text-lg text-slate-300 font-medium">{t.noTransactions}</p>
              <p className="text-sm text-slate-500 mt-2 max-w-md mx-auto">{t.tapMic}</p>
            </div>
          )}

          {isProcessing && (
            <div className="p-6 rounded-3xl bg-gradient-to-r from-cyan-500/10 to-blue-500/10 border border-cyan-500/20 flex flex-col items-center justify-center gap-4 animate-pulse backdrop-blur-md min-h-[160px]">
              <div className="w-12 h-12 rounded-full bg-cyan-500/20 flex items-center justify-center shadow-[0_0_15px_rgba(6,182,212,0.3)]">
                <Loader2 className="w-6 h-6 text-cyan-400 animate-spin" />
              </div>
              <div className="text-center">
                <p className="text-cyan-300 font-semibold">{t.analyzing}</p>
                <p className="text-xs text-cyan-400/70 mt-1">{t.translating}</p>
              </div>
            </div>
          )}

          {displayedTransactions.map((tx) => (
            <div
              key={tx.id}
              className="p-6 rounded-3xl bg-white/[0.03] border border-white/5 hover:bg-white/[0.08] transition-all duration-300 flex flex-col justify-between group backdrop-blur-md hover:border-white/20 hover:shadow-[0_8px_30px_rgb(0,0,0,0.5)] hover:-translate-y-1 relative overflow-hidden min-h-[160px]"
            >
              {/* Subtle gradient overlay on hover */}
              <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/5 to-purple-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

              <div className="flex justify-between items-start mb-6 relative z-10">
                <div className="flex flex-col gap-1.5">
                  <span className="text-lg font-bold text-white tracking-wide group-hover:text-cyan-100 transition-colors">{tx.customer_name}</span>
                  <span className="text-xs text-slate-400 capitalize bg-black/30 self-start px-2.5 py-1 rounded-md border border-white/5">
                    {tx.item_description || t.generalItem}
                  </span>
                </div>
                <span
                  className={`text-[10px] font-bold uppercase tracking-widest px-3 py-1.5 rounded-lg ${tx.transaction_type === "credit"
                    ? "bg-rose-500/15 text-rose-400 border border-rose-500/30 shadow-[0_0_15px_rgba(244,63,94,0.15)]"
                    : "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.15)]"
                    }`}
                >
                  {tx.transaction_type === "credit" ? t.udhaar : t.paid}
                </span>
              </div>

              <div className="flex items-end justify-between relative z-10 mt-auto">
                <span className="text-sm text-slate-500 font-medium">{t.amount || "Amount"}</span>
                <span className="text-3xl font-black text-white flex items-center tracking-tight drop-shadow-md">
                  <IndianRupee className="w-5 h-5 mr-1 text-cyan-500" />
                  {tx.amount}
                </span>
              </div>
            </div>
          ))}
        </div>
      </main>

      {/* Floating Action Button for Recording */}
      <div className="fixed bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-[#050B14] via-[#050B14]/90 to-transparent pointer-events-none flex flex-col items-center justify-end pb-8 lg:pb-12 z-50">
        <button
          onMouseDown={startRecording}
          onMouseUp={stopRecording}
          onMouseLeave={stopRecording}
          onTouchStart={startRecording}
          onTouchEnd={stopRecording}
          disabled={isProcessing}
          className={`pointer-events-auto relative group flex items-center justify-center w-[96px] h-[96px] lg:w-[110px] lg:h-[110px] rounded-full shadow-2xl transition-all duration-500 ${isProcessing
            ? "bg-slate-800 cursor-not-allowed scale-90 border border-white/5"
            : isRecording
              ? "bg-gradient-to-br from-rose-500 to-red-600 scale-110 shadow-[0_0_50px_rgba(244,63,94,0.8)]"
              : "bg-gradient-to-br from-cyan-400 to-blue-600 hover:scale-105 hover:-translate-y-2 shadow-[0_0_40px_rgba(6,182,212,0.5)] border-4 border-[#050B14]"
            }`}
        >
          {/* Pulsing rings when recording */}
          {isRecording && (
            <>
              <span className="absolute w-full h-full rounded-full bg-rose-500/50 animate-ping" />
              <span className="absolute w-[140%] h-[140%] rounded-full border-2 border-rose-500/40 animate-[ping_1.5s_cubic-bezier(0,0,0.2,1)_infinite]" />
            </>
          )}

          {isProcessing ? (
            <Loader2 className="w-12 h-12 text-white animate-spin" />
          ) : isRecording ? (
            <Square className="w-12 h-12 text-white fill-white" />
          ) : (
            <Mic className="w-12 h-12 lg:w-14 lg:h-14 text-white drop-shadow-xl group-hover:scale-110 transition-transform duration-300" />
          )}
        </button>
        {/* Instructional text below button */}
        <div className="mt-4 pointer-events-none text-center">
          <span className="text-xs lg:text-sm text-cyan-100 font-bold uppercase tracking-[0.2em] bg-black/50 px-5 py-1.5 rounded-full backdrop-blur-md border border-white/10 shadow-lg">
            {isRecording ? t.releaseToSend : t.holdToSpeak}
          </span>
        </div>
      </div>

      {/* Settings Modal */}
      {showSettings && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-5">
          <div className="absolute inset-0 bg-black/80 backdrop-blur-md" onClick={() => setShowSettings(false)} />
          <div className="relative w-full max-w-lg p-8 rounded-3xl bg-[#0A101D] border border-white/10 shadow-[0_0_50px_rgba(0,0,0,0.8)] animate-in zoom-in-95 duration-200">
            <div className="flex justify-between items-center mb-8">
              <h2 className="text-xl font-bold text-white flex items-center gap-3">
                <div className="p-2 bg-cyan-500/20 rounded-xl">
                  <Settings2 className="w-6 h-6 text-cyan-400" />
                </div>
                {t.appSettings}
              </h2>
              <button onClick={() => setShowSettings(false)} className="p-2 bg-white/5 rounded-full hover:bg-white/10 text-slate-400 hover:text-white transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-8">
              <div>
                <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2 mb-4 uppercase tracking-wider">
                  <Globe className="w-4 h-4 text-cyan-400" /> {t.aiLanguage}
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {LANGUAGES.map(lang => (
                    <button
                      key={lang.code}
                      onClick={() => setLanguage(lang.code)}
                      className={`px-4 py-3 rounded-xl text-sm font-medium transition-all flex justify-between items-center ${language === lang.code ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 shadow-[0_0_15px_rgba(6,182,212,0.2)]' : 'bg-black/40 text-slate-400 border border-white/5 hover:bg-white/10 hover:text-white'}`}
                    >
                      {lang.name}
                      {language === lang.code && <Check className="w-4 h-4" />}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2 mb-4 uppercase tracking-wider">
                  <User className="w-4 h-4 text-indigo-400" /> {t.assistantVoice}
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  {SPEAKERS.map(spk => (
                    <button
                      key={spk.id}
                      onClick={() => setSpeaker(spk.id)}
                      className={`px-4 py-3 rounded-xl text-sm font-medium transition-all flex justify-between items-center ${speaker === spk.id ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/50 shadow-[0_0_15px_rgba(99,102,241,0.2)]' : 'bg-black/40 text-slate-400 border border-white/5 hover:bg-white/10 hover:text-white'}`}
                    >
                      {spk.name}
                      {speaker === spk.id && <Check className="w-4 h-4" />}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
