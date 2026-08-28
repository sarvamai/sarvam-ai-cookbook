"""Failing-first tests for the Indic sentence splitter.

The module under test is ``examples/indic-streaming-narration/indic_splitter.py``
and it does not exist yet. These tests were written before it, and every one of
them was watched failing first.

Every test maps to a numbered acceptance criterion or a numbered invariant in
``docs/specs/indic-streaming-narration.md``. The number is in the test name.

Nothing here needs an API key, a network connection, or the ``sarvamai`` package.

The function under test is reached through the ``split_for_tts`` fixture rather
than a module-level import on purpose. A module-level import of a module that
does not exist collapses the whole file into one collection error; the fixture
makes every single test report the absent module by its own name, which is what
the red run is meant to show.
"""
from __future__ import annotations

import ast
import inspect
import os
import subprocess
import sys
import unicodedata
from collections.abc import Callable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
RECIPE_DIR = REPO_ROOT / "examples" / "indic-streaming-narration"
SPLITTER_PATH = RECIPE_DIR / "indic_splitter.py"

sys.path.insert(0, str(RECIPE_DIR))

Splitter = Callable[..., "list[str]"]


@pytest.fixture(scope="session")
def split_for_tts() -> Splitter:
    """The function under test, imported late so each test names it when absent."""
    from indic_splitter import split_for_tts as fn

    return fn


# --------------------------------------------------------------------------
# Fixtures. All prose below was written for this recipe. Nothing is extracted
# from any corpus, so there is no licensing question. Spec section 6.
# --------------------------------------------------------------------------

#: Sentence terminators the splitter must recognise. Criteria 7 and 8.
TERMINATORS = "\u0964\u0965.?!"

ZWJ = "\u200d"
ZWNJ = "\u200c"

#: The eleven TTS language codes, verified against
#: ``typing.get_args`` on the SDK literal in sarvamai 0.1.30. Odia is ``od-IN``;
#: ``or-IN`` is NOT in the TTS enum even though it is valid for dubbing and
#: realtime streaming. Spec section 2.
TTS_LANGUAGE_CODES = (
    "bn-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN", "ml-IN",
    "mr-IN", "od-IN", "pa-IN", "ta-IN", "te-IN",
)

#: (language code, display name, passage). One per TTS language. Criterion 6.
#: Every sentence is shorter than 120 characters and every passage is longer
#: than 120 characters, so at PER_LANGUAGE_BUDGET each passage must split and
#: every split can land on a sentence terminator.
LANGUAGE_CASES = (
    ("hi-IN", "Hindi", "मौसम विभाग ने इस सप्ताह हल्की बारिश की जानकारी दी है। किसान अपने खेत में पानी की मात्रा पर ध्यान दें। बीज बोने से पहले मिट्टी की नमी जाँच लें। गाँव के केंद्र पर मुफ्त सलाह उपलब्ध है। मंडी में अनाज का भाव हर सुबह बताया जाता है। बारिश के बाद फसल की देखभाल जरूरी है। पानी की बचत करने से पैदावार बेहतर होती है। सिंचाई का समय सुबह या शाम रखें।"),
    ("bn-IN", "Bengali", "আবহাওয়া দপ্তর এই সপ্তাহে হালকা বৃষ্টির কথা জানিয়েছে। কৃষকেরা জমিতে জলের পরিমাণ দেখে নিন। বীজ বোনার আগে মাটির আর্দ্রতা পরীক্ষা করুন। গ্রামের কেন্দ্রে বিনামূল্যে পরামর্শ পাওয়া যায়। বাজারে শস্যের দাম প্রতিদিন সকালে জানানো হয়। বৃষ্টির পরে ফসলের যত্ন নেওয়া দরকার। জল সাশ্রয় করলে ফলন ভালো হয়।"),
    ("mr-IN", "Marathi", "हवामान विभागाने या आठवड्यात हलक्या पावसाची माहिती दिली आहे। शेतकऱ्यांनी शेतातील पाण्याचे प्रमाण पाहावे। बियाणे पेरण्यापूर्वी मातीतील ओलावा तपासा। गावाच्या केंद्रावर मोफत सल्ला मिळतो। बाजारात धान्याचा भाव दररोज सकाळी सांगितला जातो। पावसानंतर पिकाची काळजी घेणे गरजेचे आहे।"),
    ("od-IN", "Odia", "ପାଣିପାଗ ବିଭାଗ ଏହି ସପ୍ତାହରେ ହାଲୁକା ବର୍ଷା ବିଷୟରେ ଜଣାଇଛି। ଚାଷୀମାନେ ଜମିରେ ପାଣିର ପରିମାଣ ଦେଖନ୍ତୁ। ବିହନ ବୁଣିବା ପୂର୍ବରୁ ମାଟିର ଆର୍ଦ୍ରତା ପରୀକ୍ଷା କରନ୍ତୁ। ଗାଁ କେନ୍ଦ୍ରରେ ମାଗଣା ପରାମର୍ଶ ମିଳେ। ବଜାରରେ ଶସ୍ୟର ଦର ପ୍ରତିଦିନ ସକାଳେ କୁହାଯାଏ। ବର୍ଷା ପରେ ଫସଲର ଯତ୍ନ ନେବା ଦରକାର।"),
    ("pa-IN", "Punjabi", "ਮੌਸਮ ਵਿਭਾਗ ਨੇ ਇਸ ਹਫ਼ਤੇ ਹਲਕੀ ਬਾਰਿਸ਼ ਦੀ ਜਾਣਕਾਰੀ ਦਿੱਤੀ ਹੈ। ਕਿਸਾਨ ਖੇਤ ਵਿੱਚ ਪਾਣੀ ਦੀ ਮਾਤਰਾ ਵੇਖਣ। ਬੀਜ ਬੀਜਣ ਤੋਂ ਪਹਿਲਾਂ ਮਿੱਟੀ ਦੀ ਨਮੀ ਜਾਂਚ ਲਵੋ। ਪਿੰਡ ਦੇ ਕੇਂਦਰ ਉੱਤੇ ਮੁਫ਼ਤ ਸਲਾਹ ਮਿਲਦੀ ਹੈ। ਮੰਡੀ ਵਿੱਚ ਅਨਾਜ ਦਾ ਭਾਅ ਹਰ ਸਵੇਰ ਦੱਸਿਆ ਜਾਂਦਾ ਹੈ। ਬਾਰਿਸ਼ ਤੋਂ ਬਾਅਦ ਫ਼ਸਲ ਦੀ ਸੰਭਾਲ ਜ਼ਰੂਰੀ ਹੈ।"),
    ("gu-IN", "Gujarati", "હવામાન વિભાગે આ અઠવાડિયે હળવા વરસાદની માહિતી આપી છે। ખેડૂતો ખેતરમાં પાણીનું પ્રમાણ જુએ। બીજ વાવતા પહેલાં માટીની ભેજ તપાસો। ગામના કેન્દ્ર પર મફત સલાહ મળે છે। બજારમાં અનાજનો ભાવ દરરોજ સવારે જણાવવામાં આવે છે। વરસાદ પછી પાકની સંભાળ જરૂરી છે।"),
    ("te-IN", "Telugu", "వాతావరణ శాఖ ఈ వారం తేలికపాటి వర్షం గురించి తెలిపింది. రైతులు పొలంలో నీటి పరిమాణాన్ని చూసుకోవాలి. విత్తనాలు వేసే ముందు మట్టిలో తేమను పరిశీలించండి. గ్రామ కేంద్రంలో ఉచిత సలహా లభిస్తుంది. మార్కెట్లో ధాన్యం ధర ప్రతిరోజు ఉదయం చెబుతారు. వర్షం తరువాత పంట సంరక్షణ అవసరం."),
    ("ta-IN", "Tamil", "வானிலை ஆய்வு மையம் இந்த வாரம் லேசான மழை பற்றி தெரிவித்துள்ளது. விவசாயிகள் வயலில் நீரின் அளவைப் பாருங்கள். விதை விதைப்பதற்கு முன் மண்ணின் ஈரப்பதத்தைச் சரிபாருங்கள். கிராம மையத்தில் இலவச ஆலோசனை கிடைக்கும். சந்தையில் தானியத்தின் விலை தினமும் காலையில் அறிவிக்கப்படும். மழைக்குப் பிறகு பயிர் பராமரிப்பு அவசியம்."),
    ("kn-IN", "Kannada", "ಹವಾಮಾನ ಇಲಾಖೆ ಈ ವಾರ ಹಗುರ ಮಳೆಯ ಬಗ್ಗೆ ತಿಳಿಸಿದೆ. ರೈತರು ಹೊಲದಲ್ಲಿ ನೀರಿನ ಪ್ರಮಾಣವನ್ನು ನೋಡಿಕೊಳ್ಳಿ. ಬಿತ್ತನೆಗೆ ಮೊದಲು ಮಣ್ಣಿನ ತೇವಾಂಶವನ್ನು ಪರಿಶೀಲಿಸಿ. ಗ್ರಾಮ ಕೇಂದ್ರದಲ್ಲಿ ಉಚಿತ ಸಲಹೆ ಸಿಗುತ್ತದೆ. ಮಾರುಕಟ್ಟೆಯಲ್ಲಿ ಧಾನ್ಯದ ಬೆಲೆ ಪ್ರತಿದಿನ ಬೆಳಿಗ್ಗೆ ತಿಳಿಸಲಾಗುತ್ತದೆ. ಮಳೆಯ ನಂತರ ಬೆಳೆಯ ಆರೈಕೆ ಅಗತ್ಯ."),
    ("ml-IN", "Malayalam", "കാലാവസ്ഥാ വകുപ്പ് ഈ ആഴ്ച നേരിയ മഴയെക്കുറിച്ച് അറിയിച്ചു. കർഷകർ വയലിലെ വെള്ളത്തിന്റെ അളവ് നോക്കണം. വിത്ത് വിതയ്ക്കുന്നതിന് മുമ്പ് മണ്ണിലെ ഈർപ്പം പരിശോധിക്കുക. ഗ്രാമ കേന്ദ്രത്തിൽ സൗജന്യ ഉപദേശം ലഭിക്കും. വിപണിയിൽ ധാന്യത്തിന്റെ വില ദിവസവും രാവിലെ അറിയിക്കും. മഴയ്ക്ക് ശേഷം വിളയുടെ പരിചരണം ആവശ്യമാണ്."),
    ("en-IN", "English", "The weather office has reported light rain for this week. Farmers should check the amount of water standing in the field. Test the moisture in the soil before sowing any seed. Free advice is available at the village centre. Grain prices are announced at the market every morning. Crops need careful attention after the rain. Saving water improves the yield over a full season."),
)

PER_LANGUAGE_BUDGET = 120

LANGUAGES = {code: text for code, _name, text in LANGUAGE_CASES}

#: The regression fixture. 3,240 characters, 36 dandas, zero ". " sequences.
#: The shipped narrator returns ONE chunk of 3240 for this input. Criterion 4.
HINDI_3240 = (
    "मानसून भारत की खेती की रीढ़ है और हर साल जून के पहले सप्ताह में केरल के तट से इसकी शुरुआत होती है। "
    "किसान इस बारिश का इंतजार महीनों पहले से करते हैं क्योंकि खरीफ की पूरी फसल इसी पानी पर टिकी होती है। "
    "मौसम विभाग हर सुबह और हर शाम अपने पूर्वानुमान को अद्यतन करता है ताकि गाँव तक सही जानकारी पहुँच सके। "
    "अगर बारिश तय समय से एक पखवाड़े देर से आती है तो धान की रोपाई पिछड़ जाती है और पैदावार घट जाती है। "
    "इसी वजह से राज्य सरकारें बुवाई का कार्यक्रम मौसम की चेतावनी के साथ जोड़कर तैयार करती हैं। "
    "छोटे किसानों के पास सिंचाई का अपना साधन नहीं होता इसलिए वे पूरी तरह आसमान पर निर्भर रहते हैं। "
    "कृषि विज्ञान केंद्र के कर्मचारी हर हफ्ते खेतों में जाकर मिट्टी की नमी की जाँच करते हैं। "
    "नमी कम मिलने पर वे कम पानी माँगने वाली फसलों की सलाह देते हैं जैसे बाजरा ज्वार और मूँग। "
    "बीज की गुणवत्ता भी उतनी ही अहम है जितना समय पर हुई बारिश और सही मात्रा में डाला गया खाद। "
    "सरकारी केंद्रों से प्रमाणित बीज लेने पर अंकुरण की दर बहुत बेहतर रहती है यह बात अनुभव से सिद्ध है। "
    "कीट लगने की शुरुआती पहचान कर लेने से दवा का खर्च आधा रह जाता है और फसल भी सुरक्षित बच जाती है। "
    "इसलिए विशेषज्ञ सलाह देते हैं कि हर तीसरे दिन खेत का एक चक्कर जरूर लगाना चाहिए। "
    "कटाई के बाद अनाज को अच्छी तरह सुखाना उतना ही जरूरी है वरना भंडारण में फफूँद लग जाती है। "
    "मंडी तक पहुँचने से पहले तौल और नमी की जाँच करा लेना किसान के हित में रहता है। "
    "बहुत से किसान अब मोबाइल पर ही मंडी के भाव देख लेते हैं और उसी हिसाब से बेचने का दिन तय करते हैं। "
    "यह बदलाव पिछले कुछ वर्षों में तेजी से आया है और इसका सीधा लाभ छोटे किसानों को मिला है। "
    "फिर भी सबसे बड़ी चुनौती यही है कि सही जानकारी उस भाषा में मिले जिसे किसान आसानी से समझ सके। "
    "इसीलिए मौसम और खेती की सलाह को स्थानीय भाषा में सुनाकर पहुँचाना सबसे कारगर तरीका माना जाता है। "
    "सुनकर समझने वाली सलाह पढ़ने वाली सलाह से कहीं ज्यादा लोगों तक पहुँचती है यह सर्वेक्षण में पाया गया। "
    "गाँव के चौपाल पर एक साथ बैठकर सुनी गई बात कई घरों तक अपने आप फैल जाती है। "
    "मानसून भारत की खेती की रीढ़ है और हर साल जून के पहले सप्ताह में केरल के तट से इसकी शुरुआत होती है। "
    "किसान इस बारिश का इंतजार महीनों पहले से करते हैं क्योंकि खरीफ की पूरी फसल इसी पानी पर टिकी होती है। "
    "मौसम विभाग हर सुबह और हर शाम अपने पूर्वानुमान को अद्यतन करता है ताकि गाँव तक सही जानकारी पहुँच सके। "
    "अगर बारिश तय समय से एक पखवाड़े देर से आती है तो धान की रोपाई पिछड़ जाती है और पैदावार घट जाती है। "
    "इसी वजह से राज्य सरकारें बुवाई का कार्यक्रम मौसम की चेतावनी के साथ जोड़कर तैयार करती हैं। "
    "छोटे किसानों के पास सिंचाई का अपना साधन नहीं होता इसलिए वे पूरी तरह आसमान पर निर्भर रहते हैं। "
    "कृषि विज्ञान केंद्र के कर्मचारी हर हफ्ते खेतों में जाकर मिट्टी की नमी की जाँच करते हैं। "
    "नमी कम मिलने पर वे कम पानी माँगने वाली फसलों की सलाह देते हैं जैसे बाजरा ज्वार और मूँग। "
    "बीज की गुणवत्ता भी उतनी ही अहम है जितना समय पर हुई बारिश और सही मात्रा में डाला गया खाद। "
    "सरकारी केंद्रों से प्रमाणित बीज लेने पर अंकुरण की दर बहुत बेहतर रहती है यह बात अनुभव से सिद्ध है। "
    "कीट लगने की शुरुआती पहचान कर लेने से दवा का खर्च आधा रह जाता है और फसल भी सुरक्षित बच जाती है। "
    "इसलिए विशेषज्ञ सलाह देते हैं कि हर तीसरे दिन खेत का एक चक्कर जरूर लगाना चाहिए। "
    "कटाई के बाद अनाज को अच्छी तरह सुखाना उतना ही जरूरी है वरना भंडारण में फफूँद लग जाती है। "
    "मंडी तक पहुँचने से पहले तौल और नमी की जाँच करा लेना किसान के हित में रहता है। "
    "बहुत से किसान अब मोबाइल पर ही मंडी के भाव देख लेते हैं और उसी हिसाब से बेचने का दिन तय करते हैं। "
    "किसान मौसम बारिश फसल खेत गाँव।"
)

#: Devanagari conjunct control characters. ZWNJ blocks the conjunct, ZWJ forces
#: the half form. Both are category Cf, so the Mn/Mc guard does not see them and
#: they need their own rule. Criterion 22, invariant I5.
_JOINER_SENTENCE = "\u092f\u0939 \u0936\u092c\u094d\u0926 \u0915\u094d" + ZWNJ + "\u0937 \u0914\u0930 \u0915\u094d" + ZWJ + "\u0937 \u0926\u094b\u0928\u094b\u0902 \u0930\u0942\u092a\u094b\u0902 \u092e\u0947\u0902 \u0932\u093f\u0916\u093e \u091c\u093e\u0924\u093e \u0939\u0948"
JOINER_TEXT = "\u0964 ".join([_JOINER_SENTENCE] * 8) + "\u0964"

#: Malayalam has THREE viramas, not one: U+0D3B and U+0D3C are missing from the
#: nine-code-point list everybody copies. A hardcoded list would mis-split this.
#: Criterion 23. The two rare signs are placed deliberately, not idiomatically.
_RARE_VIRAMA_SENTENCE = "\u0d08 \u0d35\u0d30\u0d3f\u0d2f\u0d3f\u0d7d \u0d15\u0d3b\u0d37 \u0d0e\u0d28\u0d4d\u0d28\u0d41\u0d02 \u0d15\u0d3c\u0d37 \u0d0e\u0d28\u0d4d\u0d28\u0d41\u0d02 \u0d1a\u0d47\u0d30\u0d41\u0d28\u0d4d\u0d28\u0d41"
MALAYALAM_RARE_VIRAMAS = ". ".join([_RARE_VIRAMA_SENTENCE] * 8) + "."

#: Malayalam KA. A run of these carries no whitespace and no terminator, so the
#: splitter cannot reach a sentence or word boundary and has to fall all the way
#: through to a grapheme boundary -- which makes its guard the only thing
#: deciding where the cut lands.
GRAPHEME_FALLBACK_BASE = "\u0d15"

#: Budgets the forcing cases sweep. Small on purpose: the cut has to land on the
#: interesting character, not near it.
FORCING_BUDGETS = tuple(range(6, 26))


def forcing_text(mark: str, max_chars: int) -> str:
    """A consonant run with ``mark`` sitting exactly on the budget edge.

    At ``max_chars`` the candidate scan in the splitter starts at the index
    straight after ``mark``, so the guard is what must reject it. There is no
    whitespace and no terminator anywhere to fall back on.

    This shape exists because of a real hole. The earlier fixtures merely
    CONTAINED U+0D3B, U+0D3C, ZWJ and ZWNJ, in ordinary spaced prose -- so the
    splitter always found a sentence or word boundary first and never had to
    decide about them. Replacing the derived virama rule with a hardcoded list
    of nine, or deleting the joiner rule outright, left the whole suite green.
    A fixture that contains a character is not a test of that character.
    """
    return GRAPHEME_FALLBACK_BASE * (max_chars - 1) + mark + GRAPHEME_FALLBACK_BASE * 10


#: Devanagari KA, the base for the terminator forcing case.
TERMINATOR_FALLBACK_BASE = "\u0915"


def terminator_forcing_text(terminator: str, max_chars: int) -> str:
    """A consonant run with ``terminator`` inside the budget and NO whitespace.

    Same lesson as :func:`forcing_text`. DANDA_TEXT put a space after every
    terminator, so the cut after a double danda was reachable as a word boundary
    too -- dropping U+0965 from the terminator set entirely left the suite green,
    because the split still landed in the same place for the wrong reason. With
    no whitespace anywhere, preferring the terminator is the only thing that can
    put the cut at ``TERMINATOR_OFFSET`` characters short of the budget edge.
    """
    head = max_chars - TERMINATOR_OFFSET
    return (
        TERMINATOR_FALLBACK_BASE * head
        + terminator
        + TERMINATOR_FALLBACK_BASE * (max_chars + 10)
    )


#: How far short of the budget edge the forced terminator sits.
TERMINATOR_OFFSET = 6

#: Budgets the terminator forcing case sweeps.
TERMINATOR_BUDGETS = tuple(range(12, 26))

#: Devanagari and Latin in one passage, with both danda and ". " terminators.
#: Criterion 16.
MIXED_SCRIPT = (
    "\u092f\u0939 \u092a\u0939\u0932\u093e \u0939\u093f\u0902\u0926\u0940 \u0935\u093e\u0915\u094d\u092f \u0939\u0948\u0964 "
    "This is an English sentence in the middle. "
    "\u092b\u093f\u0930 \u0938\u0947 \u0939\u093f\u0902\u0926\u0940 \u092e\u0947\u0902 \u090f\u0915 \u0914\u0930 \u0935\u093e\u0915\u094d\u092f\u0964 "
    "And one more English sentence at the end. "
) * 3

#: A single sentence with no terminator anywhere, longer than any budget the
#: tests use. Word boundaries exist, so it must split at them. Criterion 10.
LONG_UNBROKEN_SENTENCE = " ".join(
    [
        "\u0915\u093f\u0938\u093e\u0928", "\u092e\u094c\u0938\u092e", "\u092c\u093e\u0930\u093f\u0936", "\u092b\u0938\u0932", "\u0916\u0947\u0924",
        "\u0917\u093e\u0901\u0935", "\u0938\u0932\u093e\u0939", "\u092a\u093e\u0928\u0940", "\u092c\u0940\u091c", "\u092e\u093f\u091f\u094d\u091f\u0940",
        "\u0938\u092e\u092f", "\u092d\u093e\u0937\u093e", "\u091c\u093e\u0928\u0915\u093e\u0930\u0940", "\u092a\u0948\u0926\u093e\u0935\u093e\u0930", "\u0938\u093f\u0902\u091a\u093e\u0908",
        "\u0905\u0928\u093e\u091c", "\u092e\u0902\u0921\u0940", "\u092d\u093e\u0935", "\u0928\u092e\u0940", "\u091a\u0947\u0924\u093e\u0935\u0928\u0940",
    ]
    * 6
)

#: "shimla" -- one word, two places a naive guard would happily break it.
#: Criterion 21.
SHIMLA = "\u0936\u093f\u092e\u0932\u093e"
SHIMLA_TEXT = ("\u0936\u093f\u092e\u0932\u093e \u092e\u0947\u0902 \u0906\u091c \u092c\u093e\u0930\u093f\u0936 \u0939\u0948\u0964 " * 12)

#: One base consonant plus forty vowel signs: a single grapheme cluster that
#: cannot be broken anywhere. Criterion 19.
INDIVISIBLE_CLUSTER = "\u0915" + "\u093e" * 40

#: Terminator at the very end with no trailing space. Criterion 9.
TERMINATOR_AT_END = "\u0935\u093e\u0915\u094d\u092f \u090f\u0915\u0964 \u0935\u093e\u0915\u094d\u092f \u0926\u094b\u0964"

#: Criterion 7. Three identical 19-character sentences, closed by danda,
#: double danda and danda.
_SENT = "\u092f\u0939 \u090f\u0915 \u091b\u094b\u091f\u093e \u0935\u093e\u0915\u094d\u092f \u0939\u0948"
DANDA_TEXT = _SENT + "\u0964 " + _SENT + "\u0965 " + _SENT + "\u0964"

#: Criterion 8. The English path must not regress.
ASCII_TEXT = "Alpha bravo charlie. Delta echo foxtrot? Golf hotel india! Juliet kilo lima."

NO_TERMINATOR = "\u092f\u0939 \u090f\u0915 \u091b\u094b\u091f\u093e \u0935\u093e\u0915\u094d\u092f \u0939\u0948 \u091c\u093f\u0938\u092e\u0947\u0902 \u0915\u094b\u0908 \u0935\u093f\u0930\u093e\u092e \u091a\u093f\u0939\u094d\u0928 \u0928\u0939\u0940\u0902 \u0939\u0948"

ALL_PUNCTUATION = "\u0964\u0964\u0964 ... !!! ??? \u0965\u0965\u0965 ,,, ;;; --- ()"

WHITESPACE_ONLY = "   \n\t  "

#: Everything the invariants are checked over. Spec section 4.
INVARIANT_CORPUS = {
    **{f"lang:{code}": text for code, text in LANGUAGES.items()},
    "hindi-3240": HINDI_3240,
    "joiners": JOINER_TEXT,
    "malayalam-rare-viramas": MALAYALAM_RARE_VIRAMAS,
    "mixed-script": MIXED_SCRIPT,
    "long-unbroken-sentence": LONG_UNBROKEN_SENTENCE,
    "shimla": SHIMLA_TEXT,
    "terminator-at-end": TERMINATOR_AT_END,
    "danda-and-double-danda": DANDA_TEXT,
    "ascii": ASCII_TEXT,
    "no-terminator": NO_TERMINATOR,
    "all-punctuation": ALL_PUNCTUATION,
    "whitespace-only": WHITESPACE_ONLY,
    "single-char": "\u0915",
    "empty": "",
}

#: Budgets the invariants are checked at. The floor is 24 because the longest
#: whitespace-delimited token in the corpus is 16 characters, so no budget here
#: can trip the criterion-19 ValueError.
BUDGETS = (24, 40, 120, 250, 500, 1000, 2500, 3499)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def invariant_problems(chunks: list[str], text: str, max_chars: int) -> list[str]:
    """Every spec-section-4 invariant checkable on one result. Empty list is good."""
    problems: list[str] = []

    if chunks and max(len(c) for c in chunks) > max_chars:
        problems.append(f"I1 budget: longest chunk is {max(len(c) for c in chunks)} > {max_chars}")
    if "".join(chunks) != text:
        problems.append("I2 lossless: rejoined chunks do not equal the input exactly")
    if any(c == "" for c in chunks):
        problems.append("I3 empty: an empty string is present in the output")

    for i, c in enumerate(chunks):
        if not c:
            continue
        if unicodedata.category(c[0]) in ("Mn", "Mc"):
            problems.append(
                f"I4 grapheme: chunk {i} starts on U+{ord(c[0]):04X} "
                f"(category {unicodedata.category(c[0])}) -- an orphaned combining mark"
            )
        if unicodedata.combining(c[-1]) == 9:
            problems.append(f"I4 grapheme: chunk {i} ends on virama U+{ord(c[-1]):04X}")
        if c[0] in (ZWJ, ZWNJ):
            problems.append(f"I5 joiner: chunk {i} starts with U+{ord(c[0]):04X}")
        if c[-1] in (ZWJ, ZWNJ):
            problems.append(f"I5 joiner: chunk {i} ends with U+{ord(c[-1]):04X}")

    return problems


def module_import_names(path: Path) -> set[str]:
    """Top-level module names imported by a source file, read statically."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def run_without_key(source: str) -> subprocess.CompletedProcess[str]:
    """Run a snippet in a clean subprocess with SARVAM_API_KEY removed."""
    env = os.environ.copy()
    env.pop("SARVAM_API_KEY", None)
    return subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )


def shipped_narrator_split(text: str, max_length: int) -> list[str]:
    """The splitter that ships today, from examples/tts/book__summary_narrator.ipynb
    cell 15, copied verbatim minus its logging call. It is here so the regression
    test can show the bug rather than assert it. Do NOT fix this function."""
    sentences = text.replace("\n", " ").split(". ")
    chunks: list[str] = []
    current_chunk = ""

    for sentence in sentences:
        if sentence != sentences[-1]:
            sentence += "."

        if len(current_chunk) + len(sentence) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "
        else:
            current_chunk += sentence + " "

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def naive_guard_blocks(text: str, index: int) -> bool:
    """The guard everybody reaches for first. It is wrong. Criterion 21."""
    return unicodedata.combining(text[index]) != 0


def correct_guard_blocks(text: str, index: int) -> bool:
    """The guard that actually works on Indic text. Criterion 21."""
    return unicodedata.category(text[index]) in ("Mn", "Mc")


# --------------------------------------------------------------------------
# 1. Unit tests -- one behaviour each, criteria 1 to 19
# --------------------------------------------------------------------------


class TestModuleSurface:
    def test_criterion_01_split_for_tts_exists_with_type_hints(self, split_for_tts: Splitter) -> None:
        sig = inspect.signature(split_for_tts)
        assert list(sig.parameters)[:2] == ["text", "max_chars"]
        assert sig.parameters["text"].annotation is not inspect.Parameter.empty
        assert sig.parameters["max_chars"].annotation is not inspect.Parameter.empty
        assert sig.return_annotation is not inspect.Signature.empty

    def test_criterion_02_module_imports_stdlib_only(self, split_for_tts: Splitter) -> None:
        # Criterion 2 and out-of-scope item 5: full UAX #29 would need `regex`,
        # and the whole point of the Mn/Mc guard is that nothing has to be added
        # to requirements.txt.
        imported = module_import_names(SPLITTER_PATH)
        third_party = imported - sys.stdlib_module_names
        assert third_party == set(), f"non-stdlib imports: {sorted(third_party)}"
        assert "regex" not in imported

    def test_criterion_03_imports_with_no_api_key(self, split_for_tts: Splitter) -> None:
        result = run_without_key(
            "import os, sys\n"
            "assert 'SARVAM_API_KEY' not in os.environ\n"
            f"sys.path.insert(0, {str(RECIPE_DIR)!r})\n"
            "import indic_splitter\n"
            "print(indic_splitter.split_for_tts('a', 10))\n"
        )
        assert result.returncode == 0, result.stderr

    def test_criterion_17_default_budget_is_under_the_api_cap(self, split_for_tts: Splitter) -> None:
        # 3500 is the cap in the convert_stream docstring, verbatim:
        # "The text to be converted into streamed speech. Features: Max 3500 characters".
        default = inspect.signature(split_for_tts).parameters["max_chars"].default
        assert isinstance(default, int)
        assert default >= 1
        assert default < 3500, f"default budget {default} is at or over the documented cap"

    def test_criterion_18_max_chars_below_one_raises_value_error(self, split_for_tts: Splitter) -> None:
        for bad in (0, -1, -2500):
            with pytest.raises(ValueError) as excinfo:
                split_for_tts(LANGUAGES["hi-IN"], bad)
            # It must say the ARGUMENT is wrong. Falling through to the
            # criterion-19 "indivisible grapheme cluster" path also raises
            # ValueError, but blames the caller's text for a bad parameter.
            message = str(excinfo.value).lower()
            assert "max_chars" in message, message
            assert "cluster" not in message, (
                f"max_chars={bad} was reported as an unsplittable-text error "
                f"rather than a bad argument: {message}"
            )


class TestSplittingBehaviour:
    def test_criterion_07_danda_and_double_danda_are_terminators(self, split_for_tts: Splitter) -> None:
        max_chars = 21
        chunks = split_for_tts(DANDA_TEXT, max_chars)
        assert invariant_problems(chunks, DANDA_TEXT, max_chars) == []
        assert len(chunks) == 3, chunks
        assert chunks[0].rstrip()[-1] == "\u0964"
        assert chunks[1].rstrip()[-1] == "\u0965"

    def test_criterion_08_ascii_terminators_still_work(self, split_for_tts: Splitter) -> None:
        max_chars = 25
        chunks = split_for_tts(ASCII_TEXT, max_chars)
        assert invariant_problems(chunks, ASCII_TEXT, max_chars) == []
        ends = {c.rstrip()[-1] for c in chunks[:-1]}
        assert ends == {".", "?", "!"}, ends

    @pytest.mark.parametrize(
        "terminator",
        ["\u0964", "\u0965", ".", "?", "!"],
        ids=["U+0964-danda", "U+0965-double-danda", "full-stop", "question", "exclamation"],
    )
    def test_criteria_07_08_terminator_is_preferred_when_nothing_else_is_reachable(
        self, split_for_tts: Splitter, terminator: str
    ) -> None:
        """Force the terminator to be the ONLY reason the cut lands where it does.

        Criteria 7 and 8 as originally written used spaced prose, so every
        terminator was also a word boundary and the two preferences could not be
        told apart: removing U+0965 from the terminator set changed nothing the
        suite could see. Here there is no whitespace at all, so a splitter that
        does not recognise this terminator falls through to the grapheme
        boundary at the budget edge instead.
        """
        for max_chars in TERMINATOR_BUDGETS:
            text = terminator_forcing_text(terminator, max_chars)
            chunks = split_for_tts(text, max_chars)
            assert invariant_problems(chunks, text, max_chars) == []
            expected = max_chars - TERMINATOR_OFFSET + 1
            assert len(chunks[0]) == expected and chunks[0].endswith(terminator), (
                f"max_chars={max_chars}: expected the first cut right after "
                f"U+{ord(terminator):04X} at {expected} characters, got {len(chunks[0])} "
                f"ending {chunks[0][-3:]!r}. The terminator is not in the terminator set, "
                "so the split fell through to the budget edge."
            )

    def test_criterion_09_terminator_at_end_without_trailing_space(self, split_for_tts: Splitter) -> None:
        max_chars = 12
        chunks = split_for_tts(TERMINATOR_AT_END, max_chars)
        assert invariant_problems(chunks, TERMINATOR_AT_END, max_chars) == []
        assert len(chunks) == 2, chunks
        assert "".join(chunks).count("\u0964") == 2, "a danda was lost or duplicated"
        assert chunks[-1].endswith("\u0964")

    def test_criterion_10_sentence_longer_than_budget_splits_at_word_boundary(
        self, split_for_tts: Splitter
    ) -> None:
        max_chars = 100
        assert len(LONG_UNBROKEN_SENTENCE) > max_chars
        chunks = split_for_tts(LONG_UNBROKEN_SENTENCE, max_chars)
        assert invariant_problems(chunks, LONG_UNBROKEN_SENTENCE, max_chars) == []
        assert len(chunks) > 1
        for left, right in zip(chunks, chunks[1:]):
            assert left[-1].isspace() or right[0].isspace(), (
                f"split fell inside a word: ...{left[-6:]!r} | {right[:6]!r}..."
            )

    def test_criterion_16_mixed_script_splits_on_both_terminators(self, split_for_tts: Splitter) -> None:
        max_chars = 70
        chunks = split_for_tts(MIXED_SCRIPT, max_chars)
        assert invariant_problems(chunks, MIXED_SCRIPT, max_chars) == []
        ends = {c.rstrip()[-1] for c in chunks[:-1]}
        assert "\u0964" in ends, f"never split on a danda: {ends}"
        assert "." in ends, f"never split on a full stop: {ends}"

    def test_criterion_06_language_matrix_is_exactly_the_tts_enum(self, split_for_tts: Splitter) -> None:
        codes = tuple(sorted(code for code, _name, _text in LANGUAGE_CASES))
        assert codes == tuple(sorted(TTS_LANGUAGE_CODES))
        assert len(codes) == 11
        assert "or-IN" not in codes, "or-IN is not a TTS language code; Odia is od-IN"
        # Cross-check against the installed SDK when it is present. It is not in
        # requirements-dev.txt, so this half is skipped where it is absent.
        try:
            import typing

            from sarvamai.types.text_to_speech_language import TextToSpeechLanguage
        except ImportError:  # pragma: no cover - depends on the environment
            pass
        else:
            enum = typing.get_args(typing.get_args(TextToSpeechLanguage)[0])
            assert tuple(sorted(enum)) == codes

    @pytest.mark.parametrize(
        "code,name,text",
        LANGUAGE_CASES,
        ids=[name for _code, name, _text in LANGUAGE_CASES],
    )
    def test_criterion_06_each_language_splits_on_sentence_terminators(
        self, split_for_tts: Splitter, code: str, name: str, text: str
    ) -> None:
        max_chars = PER_LANGUAGE_BUDGET
        assert len(text) > max_chars, f"{name} fixture is not longer than the budget"
        chunks = split_for_tts(text, max_chars)
        assert invariant_problems(chunks, text, max_chars) == []
        assert len(chunks) >= 2, f"{name} did not split at all"
        for i, chunk in enumerate(chunks[:-1]):
            assert chunk.rstrip()[-1] in TERMINATORS, (
                f"{name} chunk {i} does not end on a sentence terminator: {chunk[-20:]!r}"
            )


# --------------------------------------------------------------------------
# 2. Invariants -- properties over the whole corpus at every budget
# --------------------------------------------------------------------------


class TestInvariants:
    @pytest.mark.parametrize("label", sorted(INVARIANT_CORPUS))
    def test_invariants_i1_to_i5_hold_over_the_corpus(
        self, split_for_tts: Splitter, label: str
    ) -> None:
        """I1 budget, I2 lossless, I3 no empty chunk, I4 grapheme safety, I5 joiner safety."""
        text = INVARIANT_CORPUS[label]
        for max_chars in BUDGETS:
            chunks = split_for_tts(text, max_chars)
            problems = invariant_problems(chunks, text, max_chars)
            assert problems == [], f"{label} at max_chars={max_chars}: {problems}"

    @pytest.mark.parametrize("label", sorted(INVARIANT_CORPUS))
    def test_invariant_i6_chunks_appear_in_input_order(
        self, split_for_tts: Splitter, label: str
    ) -> None:
        text = INVARIANT_CORPUS[label]
        for max_chars in BUDGETS:
            offset = 0
            for i, chunk in enumerate(split_for_tts(text, max_chars)):
                assert text[offset : offset + len(chunk)] == chunk, (
                    f"{label} chunk {i} is not at offset {offset} in the input"
                )
                offset += len(chunk)
            assert offset == len(text), f"{label} consumed {offset} of {len(text)} characters"

    @pytest.mark.parametrize("label", sorted(INVARIANT_CORPUS))
    def test_invariant_i7_splitting_is_deterministic(
        self, split_for_tts: Splitter, label: str
    ) -> None:
        text = INVARIANT_CORPUS[label]
        for max_chars in BUDGETS:
            assert split_for_tts(text, max_chars) == split_for_tts(text, max_chars), label

    @pytest.mark.parametrize("label", sorted(INVARIANT_CORPUS))
    def test_invariant_i8_a_bigger_budget_never_makes_more_chunks(
        self, split_for_tts: Splitter, label: str
    ) -> None:
        text = INVARIANT_CORPUS[label]
        counts = [len(split_for_tts(text, max_chars)) for max_chars in BUDGETS]
        for (small, few), (large, many) in zip(zip(BUDGETS, counts), zip(BUDGETS[1:], counts[1:])):
            assert many <= few, (
                f"{label}: budget {large} produced {many} chunks but budget {small} produced {few}"
            )

    def test_invariant_i9_the_splitter_never_reaches_sarvamai(self, split_for_tts: Splitter) -> None:
        result = run_without_key(
            "import sys\n"
            f"sys.path.insert(0, {str(RECIPE_DIR)!r})\n"
            "before = set(sys.modules)\n"
            "import indic_splitter\n"
            "pulled = set(sys.modules) - before\n"
            "assert not any(m.split('.')[0] == 'sarvamai' for m in pulled), sorted(pulled)\n"
            "assert 'regex' not in pulled, sorted(pulled)\n"
        )
        assert result.returncode == 0, result.stderr


# --------------------------------------------------------------------------
# 3. Regression -- the exact failure that motivated this product
# --------------------------------------------------------------------------


class TestHindiRegression:
    def test_the_fixture_still_reproduces_the_bug(self, split_for_tts: Splitter) -> None:
        """The fixture must keep the shape that breaks the shipped splitter.

        If this ever goes green-by-accident it means the fixture drifted, not
        that the bug is fixed, so it is pinned by exact numbers.
        """
        assert len(HINDI_3240) == 3240
        assert HINDI_3240.count("\u0964") == 36
        assert HINDI_3240.count(". ") == 0

        old = shipped_narrator_split(HINDI_3240, 2500)
        assert len(old) == 1, "the shipped narrator no longer returns one chunk"
        assert len(old[0]) == 3240, "the shipped narrator no longer blows the budget"

    def test_criterion_04_hindi_3240_at_2500_splits_and_fits(self, split_for_tts: Splitter) -> None:
        max_chars = 2500
        chunks = split_for_tts(HINDI_3240, max_chars)
        assert len(chunks) > 1, "still one lump, exactly the bug this product fixes"
        assert max(len(c) for c in chunks) <= max_chars
        assert invariant_problems(chunks, HINDI_3240, max_chars) == []

    def test_criterion_05_hindi_3240_at_the_notebook_budget_of_500(self, split_for_tts: Splitter) -> None:
        max_chars = 500  # MAX_CHUNK_LENGTH in book__summary_narrator.ipynb cell 9
        chunks = split_for_tts(HINDI_3240, max_chars)
        assert len(chunks) > 1
        assert max(len(c) for c in chunks) <= max_chars
        assert invariant_problems(chunks, HINDI_3240, max_chars) == []


# --------------------------------------------------------------------------
# 4. Edge cases -- criteria 11 to 15 and 19
# --------------------------------------------------------------------------


class TestEdgeCases:
    def test_criterion_11_empty_input_returns_empty_list(self, split_for_tts: Splitter) -> None:
        assert split_for_tts("", 2500) == []

    def test_criterion_12_whitespace_only_returns_one_chunk_equal_to_the_input(
        self, split_for_tts: Splitter
    ) -> None:
        # It cannot return [] without breaking I2, so it is exactly one chunk.
        assert split_for_tts(WHITESPACE_ONLY, 2500) == [WHITESPACE_ONLY]

    def test_criterion_13_no_terminator_and_under_budget_returns_one_chunk(
        self, split_for_tts: Splitter
    ) -> None:
        assert len(NO_TERMINATOR) < 2500
        assert split_for_tts(NO_TERMINATOR, 2500) == [NO_TERMINATOR]

    @pytest.mark.parametrize("ch", ["\u0915", "a", "\u0964", " ", "\u0c4a"])
    def test_criterion_14_single_character_returns_that_character(
        self, split_for_tts: Splitter, ch: str
    ) -> None:
        assert split_for_tts(ch, 2500) == [ch]

    def test_criterion_15_all_punctuation_does_not_raise(self, split_for_tts: Splitter) -> None:
        for max_chars in BUDGETS:
            chunks = split_for_tts(ALL_PUNCTUATION, max_chars)
            assert invariant_problems(chunks, ALL_PUNCTUATION, max_chars) == []

    def test_criterion_19_indivisible_cluster_over_budget_raises_value_error(
        self, split_for_tts: Splitter
    ) -> None:
        # One base consonant plus forty vowel signs. There is no legal split
        # point anywhere inside it, so honouring I1 and I4 at the same time is
        # impossible and the splitter must say so instead of emitting an
        # over-budget chunk or breaking the cluster.
        assert len(INDIVISIBLE_CLUSTER) == 41
        assert all(unicodedata.category(c) in ("Mn", "Mc") for c in INDIVISIBLE_CLUSTER[1:])
        with pytest.raises(ValueError) as excinfo:
            split_for_tts(INDIVISIBLE_CLUSTER, 10)
        message = str(excinfo.value).lower()
        assert message, "the ValueError must name the problem, not be raised bare"
        assert any(word in message for word in ("cluster", "grapheme", "max_chars", "indivisible"))

    def test_criterion_19_is_not_triggered_when_the_cluster_fits(self, split_for_tts: Splitter) -> None:
        chunks = split_for_tts(INDIVISIBLE_CLUSTER, 41)
        assert chunks == [INDIVISIBLE_CLUSTER]

    @pytest.mark.parametrize("max_chars,marks", [(3, 2), (4, 3), (5, 4), (6, 5)])
    def test_criterion_19_does_not_raise_when_the_only_legal_split_is_one_character(
        self, split_for_tts: Splitter, max_chars: int, marks: int
    ) -> None:
        """A one-character first chunk is a legal split, not an indivisible cluster.

        KA, then KHA carrying `marks` vowel signs. Every candidate above index 1
        lands on a combining mark and is correctly refused, so index 1 -- a
        single-character chunk -- is the only legal cut in the window. It is a
        real cut and the remainder fits, so the splitter must take it.

        A scan that stops one index early (``range(..., start + 1, -1)``) never
        considers it and raises the criterion-19 ValueError on text that splits
        perfectly well. That is a false "your text is unsplittable" on input that
        is not, which is worse than a wrong chunk boundary because it is fatal.
        """
        text = "\u0915\u0916" + "\u093e" * marks
        assert len(text) > max_chars

        chunks = split_for_tts(text, max_chars)
        assert invariant_problems(chunks, text, max_chars) == []
        assert chunks[0] == "\u0915", (
            f"expected a one-character first chunk, got {chunks[0]!r}"
        )
        assert len(chunks) == 2, chunks


# --------------------------------------------------------------------------
# 5. Guard traps -- criteria 20 to 23
#
# These exist so that nobody can "simplify" the grapheme guard back into the
# broken form without a red test explaining why it is broken. Each one asserts
# the platform fact first and then that the splitter actually honours it.
# --------------------------------------------------------------------------


#: Verified on Python 3.13.12 / unicodedata 15.1.0.
INDIC_VOWEL_SIGNS = ("\u093e", "\u093f", "\u0c4a", "\u09be")

#: The nine viramas everybody lists, plus the two Malayalam ones nearly every
#: list omits. Criterion 23.
BRIEF_VIRAMAS = (
    "\u094d", "\u09cd", "\u0a4d", "\u0acd", "\u0b4d",
    "\u0bcd", "\u0c4d", "\u0ccd", "\u0d4d",
)
OMITTED_MALAYALAM_VIRAMAS = ("\u0d3b", "\u0d3c")

INDIC_BLOCKS = {
    "Devanagari": (0x0900, 0x097F),
    "Bengali": (0x0980, 0x09FF),
    "Gurmukhi": (0x0A00, 0x0A7F),
    "Gujarati": (0x0A80, 0x0AFF),
    "Oriya": (0x0B00, 0x0B7F),
    "Tamil": (0x0B80, 0x0BFF),
    "Telugu": (0x0C00, 0x0C7F),
    "Kannada": (0x0C80, 0x0CFF),
    "Malayalam": (0x0D00, 0x0D7F),
}


class TestGuardTraps:
    def test_criterion_20_combining_is_zero_for_indic_vowel_signs(self) -> None:
        """DO NOT replace the Mn/Mc guard with unicodedata.combining().

        combining() returns 0 for every Indic vowel sign, so a guard written as
        `combining(ch) != 0` is a no-op on exactly the scripts this product is
        for. It looks right, it runs, and it orphans matras. The only guard that
        works is category(ch) in ("Mn", "Mc"). This test is the tripwire.

        This test takes no fixture and asserts nothing about the splitter, on
        purpose. It is a standing record of WHY the guard is written the way it
        is, so it must keep running and passing even if the module is deleted.
        That the splitter actually honours the guard is invariant I4, checked
        over the whole corpus at every budget by
        TestInvariants::test_invariants_i1_to_i5_hold_over_the_corpus.
        """
        for ch in INDIC_VOWEL_SIGNS:
            assert unicodedata.combining(ch) == 0, (
                f"U+{ord(ch):04X} {unicodedata.name(ch)} now reports a combining class; "
                "re-read the guard before trusting combining()"
            )
            assert unicodedata.category(ch) in ("Mn", "Mc"), (
                f"U+{ord(ch):04X} {unicodedata.name(ch)} is no longer Mn/Mc"
            )

    def test_criterion_21_naive_guard_would_break_a_real_word(self, split_for_tts: Splitter) -> None:
        """The word is shimla. A combining()-based guard permits two splits that
        both orphan a vowel sign; the category()-based guard blocks both."""
        assert SHIMLA == "\u0936\u093f\u092e\u0932\u093e"
        for index in (1, 4):
            assert naive_guard_blocks(SHIMLA, index) is False, (
                f"index {index}: the naive guard is supposed to be wrong here"
            )
            assert correct_guard_blocks(SHIMLA, index) is True, (
                f"index {index}: the correct guard must block this split"
            )

        for max_chars in (24, 40, 120, 250):
            chunks = split_for_tts(SHIMLA_TEXT, max_chars)
            assert invariant_problems(chunks, SHIMLA_TEXT, max_chars) == []
            for chunk in chunks:
                assert not chunk.startswith("\u093f"), "orphaned vowel sign I at the head of a chunk"
                assert not chunk.startswith("\u093e"), "orphaned vowel sign AA at the head of a chunk"

    def test_criterion_22_zwj_and_zwnj_are_cf_and_need_their_own_rule(self) -> None:
        """The Mn/Mc guard does not cover the joiners. This is a real hole in the
        guard as usually written, and this test keeps it shut.

        Like criterion 20 this takes no fixture and asserts nothing about the
        splitter, so it survives the module being deleted. That the splitter
        honours the separate joiner rule is invariant I5, checked over the whole
        corpus -- including the `joiners` fixture, which contains both ZWJ and
        ZWNJ -- by TestInvariants::test_invariants_i1_to_i5_hold_over_the_corpus.
        """
        for ch in (ZWJ, ZWNJ):
            assert unicodedata.category(ch) == "Cf", unicodedata.name(ch)
            assert unicodedata.category(ch) not in ("Mn", "Mc"), (
                f"U+{ord(ch):04X} is now Mn/Mc, so the Mn/Mc guard would cover it "
                "and the separate joiner rule may be redundant -- re-check I5"
            )
            assert unicodedata.combining(ch) == 0

        # The fixture the I5 invariant leans on must actually contain both.
        assert ZWJ in JOINER_TEXT and ZWNJ in JOINER_TEXT

    def test_criterion_23_virama_set_is_derived_not_hardcoded(self, split_for_tts: Splitter) -> None:
        """Malayalam has THREE viramas. A hardcoded list of nine silently
        mis-splits any Malayalam text containing U+0D3B or U+0D3C, so the
        splitter must derive viramas from combining(ch) == 9."""
        derived = {
            chr(cp)
            for _block, (lo, hi) in INDIC_BLOCKS.items()
            for cp in range(lo, hi + 1)
            if unicodedata.combining(chr(cp)) == 9
        }
        for ch in BRIEF_VIRAMAS:
            assert ch in derived, f"U+{ord(ch):04X} is not derivable from combining() == 9"
        for ch in OMITTED_MALAYALAM_VIRAMAS:
            assert ch in derived, (
                f"U+{ord(ch):04X} {unicodedata.name(ch)} is missing from the derived set; "
                "the usual nine-item hardcoded list omits it"
            )
        malayalam = {c for c in derived if 0x0D00 <= ord(c) <= 0x0D7F}
        assert len(malayalam) == 3, sorted(f"U+{ord(c):04X}" for c in malayalam)

        # Sinhala U+0DCA SINHALA SIGN AL-LAKUNA is also combining class 9, and it
        # is deliberately NOT in INDIC_BLOCKS: Sinhala is not one of the eleven
        # TTS languages, so this suite does not fixture or assert it. Note this
        # is a statement about the TEST's sweep, not about the implementation --
        # a splitter that derives viramas from combining(ch) == 9 rather than a
        # block list will handle U+0DCA correctly and for free, which is the
        # whole argument for deriving instead of hardcoding.
        assert unicodedata.combining("\u0dca") == 9
        assert "\u0dca" not in derived, "Sinhala is out of scope; keep it out of the sweep"

        assert "\u0d3b" in MALAYALAM_RARE_VIRAMAS and "\u0d3c" in MALAYALAM_RARE_VIRAMAS
        for max_chars in (24, 40, 120, 250):
            chunks = split_for_tts(MALAYALAM_RARE_VIRAMAS, max_chars)
            assert invariant_problems(chunks, MALAYALAM_RARE_VIRAMAS, max_chars) == []
            for i, chunk in enumerate(chunks):
                assert unicodedata.combining(chunk[-1]) != 9, (
                    f"chunk {i} ends on virama U+{ord(chunk[-1]):04X}"
                )

    @pytest.mark.parametrize(
        "mark",
        ["\u0d3b", "\u0d3c", "\u0d4d"],
        ids=["U+0D3B-vertical-bar", "U+0D3C-circular", "U+0D4D-ordinary"],
    )
    def test_criterion_23_a_virama_on_the_budget_edge_is_never_cut_across(
        self, split_for_tts: Splitter, mark: str
    ) -> None:
        """Force the splitter to decide about a virama instead of merely seeing one.

        A hardcoded list of nine viramas passes every other test in this file.
        It fails this one on U+0D3B and U+0D3C, because here the only candidate
        boundary in reach sits directly after the virama. U+0D4D is swept too,
        as a control: it IS in the usual nine-item list, so it must stay green
        under that mutation and only go red if virama handling breaks wholesale.
        """
        assert unicodedata.combining(mark) == 9, unicodedata.name(mark)

        for max_chars in FORCING_BUDGETS:
            text = forcing_text(mark, max_chars)
            chunks = split_for_tts(text, max_chars)
            assert invariant_problems(chunks, text, max_chars) == []
            for i, chunk in enumerate(chunks):
                assert chunk[-1] != mark, (
                    f"max_chars={max_chars}: chunk {i} ends on "
                    f"U+{ord(mark):04X} {unicodedata.name(mark)} -- a dangling virama "
                    f"with its conjunct broken: ...{chunk[-6:]!r}. The virama set is "
                    "hardcoded rather than derived from combining(ch) == 9."
                )
                assert chunk[0] != mark, (
                    f"max_chars={max_chars}: chunk {i} starts on U+{ord(mark):04X}"
                )

    @pytest.mark.parametrize("mark", [ZWJ, ZWNJ], ids=["U+200D-ZWJ", "U+200C-ZWNJ"])
    def test_criterion_22_a_joiner_on_the_budget_edge_is_never_cut_across(
        self, split_for_tts: Splitter, mark: str
    ) -> None:
        """Same hole, same fix, for invariant I5.

        JOINER_TEXT contains both joiners but is ordinary spaced prose, so the
        splitter never had to decide about them: deleting the joiner rule from
        the implementation altogether left every test green. Here the only
        candidate boundary in reach is adjacent to the joiner, so the rule is
        the only thing that can reject it.
        """
        assert unicodedata.category(mark) == "Cf", unicodedata.name(mark)

        for max_chars in FORCING_BUDGETS:
            text = forcing_text(mark, max_chars)
            chunks = split_for_tts(text, max_chars)
            assert invariant_problems(chunks, text, max_chars) == []
            for i, chunk in enumerate(chunks):
                assert chunk[-1] != mark, (
                    f"max_chars={max_chars}: chunk {i} ends on "
                    f"U+{ord(mark):04X} {unicodedata.name(mark)}. The joiner rule is "
                    "missing -- Mn/Mc does not cover category Cf."
                )
                assert chunk[0] != mark, (
                    f"max_chars={max_chars}: chunk {i} starts on "
                    f"U+{ord(mark):04X} {unicodedata.name(mark)}"
                )
