# Equation to speech

How do you say `(a+b)^2` out loud in Hindi?

A screen reader says "left paren a plus b right paren caret two". Or it says "a plus b to the
power of two", which is a different equation. Hand `(a+b)^2` to any text-to-speech engine,
Sarvam's included, and you get the *characters* read out, not the *maths* read out. The engine
has no idea the brackets change the answer.

This recipe is the step before the voice. It parses the expression itself and writes one
unambiguous sentence in English, Hindi, Tamil or Telugu, which you can then hand to
`text_to_speech.convert`.

```text
(a+b)^2   ->   koshthak a jod b koshthak samaapt ka varg
a+b^2     ->   a jod b ka varg
```

Those two are the whole point.

## Read this first

**The words are this recipe's own choices, not any syllabus.**

Every word this recipe speaks is a choice made here, not a quotation. There is no single
agreed way to say school algebra in Hindi, Tamil or Telugu. Classrooms mix English loanwords
with mother-tongue terms, and the mix changes by state, by board and by teacher. So this
recipe picks one word for every symbol, keeps all of them in one editable table per language,
and claims nothing about any syllabus, board or curriculum. No textbook text of any kind
ships here. Change a row in a table and the sentence changes with it.

**Nothing here has been spoken, and nobody has checked the words.**

No native speaker has reviewed these word tables, and no cell in this notebook has been run.
There was no Sarvam API key on the machine this was built on, so nothing was spoken and
nothing was heard. The parser and the tables are fully offline and fully tested; the two
functions that call the API have never met a live server.

If you have a key, run the notebook and listen. If you speak one of these languages, the
tables are the first place to look.

## What it produces

Twelve worked examples, in all four languages. Every sentence below came out of
`equation_speech.verbalise()`; none was written by hand.

| input | en-IN | hi-IN | ta-IN | te-IN |
|---|---|---|---|---|
| `(a+b)^2` | the quantity a plus b end quantity squared | कोष्ठक a जोड़ b कोष्ठक समाप्त का वर्ग | அடைப்பு a கூட்டல் b அடைப்பு முடிவு இன் வர்க்கம் | కుండలీకరణం a కూడిక b కుండలీకరణం ముగింపు యొక్క వర్గం |
| `a+b^2` | a plus b squared | a जोड़ b का वर्ग | a கூட்டல் b இன் வர்க்கம் | a కూడిక b యొక్క వర్గం |
| `3/4` | three quarters | तीन चौथाई | முக்கால் | ముప్పావు |
| `3.4` | three point four | तीन दशमलव चार | மூன்று புள்ளி நான்கு | మూడు దశాంశం నాలుగు |
| `34` | 34 | 34 | 34 | 34 |
| `x<=5` | x is less than or equal to five | x, पाँच से छोटा या बराबर है | x, ஐந்து ஐ விட சிறியது அல்லது சமம் | x, ఐదు కంటే తక్కువ లేదా సమానం |
| `x<5` | x is less than five | x, पाँच से छोटा है | x, ஐந்து ஐ விட சிறியது | x, ఐదు కంటే తక్కువ |
| `d/dx(x^2)` | the derivative of x squared with respect to x | x के सापेक्ष, x का वर्ग, इसका अवकलज | x ஐப் பொறுத்து, x இன் வர்க்கம், இதன் வகைக்கெழு | x దృష్ట్యా, x యొక్క వర్గం, దీని అవకలనం |
| `sqrt(x^2+1)` | the square root of the quantity x squared plus one end quantity | कोष्ठक x का वर्ग जोड़ एक कोष्ठक समाप्त का वर्गमूल | அடைப்பு x இன் வர்க்கம் கூட்டல் ஒன்று அடைப்பு முடிவு இன் வர்க்கமூலம் | కుండలీకరణం x యొక్క వర్గం కూడిక ఒకటి కుండలీకరణం ముగింపు యొక్క వర్గమూలం |
| `5.34` | five point three four | पाँच दशमलव तीन चार | ஐந்து புள்ளி மூன்று நான்கு | ఐదు దశాంశం మూడు నాలుగు |
| `-5+2*3` | negative five plus two times three | ऋण पाँच जोड़ दो गुणा तीन | எதிர்மறை ஐந்து கூட்டல் இரண்டு பெருக்கல் மூன்று | రుణ ఐదు కూడిక రెండు గుణకారం మూడు |
| `50%` | 50 percent | 50 प्रतिशत | 50 சதவீதம் | 50 శాతం |

`34` is deliberately the same in all four. That is the number convention below doing its job:
a two-digit integer is left for the voice, and the sentence around it is what changes.

## The choices, one by one

Every heading here is a decision. Each one is a table you can edit, or a named constant you
can change.

### Single digits become words. Longer numbers stay as digits.

`0` through `9` come from a ten-word table per language. An integer of two or more digits is
left in the sentence as digits and voiced by the speech layer.

This is honesty about scope. Naming an arbitrary integer in Hindi, Tamil or Telugu means
implementing Indian number naming: lakh, crore, the compound forms, the irregular teens in
three languages. That is a whole product on its own, it is easy to get subtly wrong, and
Sarvam already does it server-side. Ten digit words per language is a table a teacher can
check at a glance. A number-naming engine is not.

For the longer ones, `spoken_numerals()` hands the job to `text.transliterate` with
`spoken_form=True` and `spoken_form_numerals_language="native"`, which turns `34` into the
target language's word for it. That step needs a key, is clearly marked in the notebook, and
is entirely optional -- the sentence is complete and speakable without it.

Integers of five digits or more are comma-grouped from the right: `12000` becomes `12,000`.
The vendor's own documentation asks for this, with `'10,000'` as its example, so the voice
reads a long number as one number. `COMMA_GROUPING_MIN_DIGITS` is the one constant to change
if you learn otherwise. Note that this is international grouping, not Indian grouping
(`1,00,000`); the vendor's example is the international form.

### Decimals are read digit by digit

`5.34` becomes "five point three four", not "five point thirty-four".

**The whole-number reading is equally valid and is used by real people.** This is a choice,
not a correction. Digit-wise was picked because it stays sane for long decimals -- `3.14159`
digit-wise is one rule, where as a whole number it is "fourteen thousand one hundred
fifty-nine hundred-thousandths", which nobody says -- and because it needs only the same ten
digit words. Both readings are named in the module as `DECIMAL_READING` and
`DECIMAL_READING_ALTERNATIVE`, so nobody swaps the convention while thinking they are fixing
a bug.

The integer part before the point follows the rule above, so `12.5` is "12 point five".

### Five named fractions per language, and everything else is a division

| | 1/2 | 1/3 | 2/3 | 1/4 | 3/4 |
|---|---|---|---|---|---|
| en-IN | one half | one third | two thirds | one quarter | three quarters |
| hi-IN | आधा | एक तिहाई | दो तिहाई | एक चौथाई | तीन चौथाई |
| ta-IN | அரை | மூன்றில் ஒன்று | மூன்றில் இரண்டு | கால் | முக்கால் |
| te-IN | సగం | మూడో వంతు | మూడింట రెండు | పావు | ముప్పావు |

So `3/4` is "three quarters" and `6/2` is "six divided by two". Adding a sixth named fraction
is one row in `fraction_words`.

### Bracket words come from the structure, never from where you typed a parenthesis

The renderer does not remember your parentheses. It puts bracket words wherever the sentence
would otherwise be ambiguous by ear, so `((((1))))` reads as plainly as `1`, and
`a-(b-c)` gets the words while `(a-b)-c` does not.

| | open | close |
|---|---|---|
| en-IN | the quantity | end quantity |
| hi-IN | कोष्ठक | कोष्ठक समाप्त |
| ta-IN | அடைப்பு | அடைப்பு முடிவு |
| te-IN | కుండలీకరణం | కుండలీకరణం ముగింపు |

This is the rule that keeps `(a+b)^2` and `a+b^2` apart, which is the reason the recipe exists.

### Powers, roots and calculus carry the possessive inside the stored word

Hindi, Tamil and Telugu put the possessive before the operation: `x^2` is "x **का** वर्ग", not
"वर्ग x". The particle also has to agree with the noun it attaches to -- Hindi वर्ग is
masculine and takes का, घात is feminine and takes की.

Rather than build a gender-agreement engine, the particle is part of the stored string.
`power_words["square"]` for Hindi is the whole phrase `का वर्ग`, and the renderer only
concatenates. Fixing an agreement error means editing one string; no code changes.

Calculus uses a two-slot template for the same reason, for instance
`{var} के सापेक्ष, {expr}, इसका अवकलज`.

### Comparisons follow the word order of the language

English is subject-verb-object: `x < 5` is "x is less than five". Hindi, Tamil and Telugu are
subject-object-verb, so the compared value comes first: "x, पाँच से छोटा है". Each table
carries `comparison_order`, either `svo` or `sov`. The comma in the SOV form is deliberate --
it is what keeps the sentence parseable by ear.

### `x` is always a variable, and `*` is the only multiplication sign

`x` cannot also mean "times". It is the commonest variable name in school algebra, and a
parser that guesses will guess wrong in front of a student. So `2 x 3` is a syntax error,
reported at the position of the `x`, with a message that says to use `*`:

```text
unexpected 'x'; this grammar has no implicit multiplication, so a variable or a
bracket cannot follow a complete term -- write '*' between the two parts (position 2)
```

Implicit multiplication (`2x`, `2(a+b)`, `ab`) is out of the grammar for the same reason. This
is a deliberate refusal to guess.

### Variables are spoken as the Latin letter

`x` inside a Hindi sentence is written as `x`, because the speech model handles code-mixed
text. If you would rather it said एक्स, every table has an empty `variable_words` dictionary:
add one row per letter you want changed. This has never been heard through a real voice -- see
the open questions below.

## The grammar it accepts

ASCII only. `{ }` is zero or more, `[ ]` is optional.

```text
equation    := comparison EOF
comparison  := sum [ compare_op sum ]
compare_op  := "=" | "!=" | "<" | "<=" | ">" | ">="
sum         := product { ("+" | "-") product }
product     := unary { ("*" | "/") unary }
unary       := "-" unary | power
power       := postfix [ "^" unary ]
postfix     := atom [ "%" ]
atom        := NUMBER
             | VARIABLE
             | "sqrt" "(" comparison ")"
             | DERIV_HEAD "(" comparison ")"
             | "integral" "(" comparison "," "d" VARIABLE ")"
             | "(" comparison ")"

NUMBER      := DIGIT { DIGIT } [ "." DIGIT { DIGIT } ]
DIGIT       := "0" | "1" | ... | "9"
VARIABLE    := one letter, "a".."z" or "A".."Z"
DERIV_HEAD  := "d" "/" "d" VARIABLE
```

Whitespace between tokens is ignored. `^` is right-associative, so `2^3^2` is `2^(3^2)`, and
unary minus sits outside the power, so `-x^2` means `-(x^2)`.

The parser is hand-written recursive descent, and it has to be. Python's own `^` is bitwise
XOR and binds *lower* than `+`, so `ast.parse("(a+b)^2")` and `ast.parse("a+b^2")` return
structurally identical trees. Borrowing Python's parser would silently destroy the one
distinction this recipe exists to make.

### Anything else is an error with a position

Students paste from word processors and textbook PDFs, so the ten commonest near misses come
back with the ASCII to type instead:

| pasted | message suggests |
|---|---|
| `×` | `*` |
| `÷` | `/` |
| `≤` | `<=` |
| `≥` | `>=` |
| `≠` | `!=` |
| `−` (U+2212) | `-` |
| `²` | `^2` |
| `³` | `^3` |
| `½` | `1/2` |
| `√` | `sqrt(...)` |

Devanagari, Tamil and Telugu digits are rejected too. The input side is ASCII; the output side
is not. This matters more than it looks: `"२".isdecimal()` is `True` and `int("२")` returns
`2`, so a tokeniser that trusted Python's own predicates would accept out-of-grammar input in
silence. The tokeniser here matches digits against the explicit set `0123456789` and nothing
else.

Brackets nested deeper than `MAX_NESTING_DEPTH` (32) come back as this recipe's own error with
a position, never as a `RecursionError` traceback.

## Language codes

Four codes ship: `en-IN`, `hi-IN`, `ta-IN`, `te-IN`. Anything else raises
`UnsupportedLanguageError` before a client is ever constructed.

One thing to know if you add a language. For Odia the speech API accepts **`od-IN`** and does
not accept `or-IN`, even though `scripts/sarvam_api_rules.json` in this repo lists `or-IN` for
text-to-speech. That contradiction is tracked as issue #157. Do not "correct" a recipe from the
rules file and ship `or-IN`; the server will reject it. Odia is not among the four languages
here in any case.

## What it deliberately does not do

Each of these is a parse error with a position, not a silent guess: matrices and vectors;
limits, summations and products; definite integrals with bounds; `sin`, `cos`, `log`, `ln`;
subscripts; multi-letter variables and Greek letters; implicit multiplication; scientific
notation; complex numbers; factorials; absolute value.

And out of the product entirely: naming integers beyond 0 to 9 offline; languages beyond the
four (adding one is one more `RuleTable`, and guessing one without a speaker of the language
is not a favour to anybody); evaluating the expression, because this reads maths aloud and
never computes an answer; LaTeX or MathML input; speech back to an equation; and splitting an
over-long sentence across two audio files, which is a worse answer than telling the caller.

## Files

```text
equation_speech.py          the parser, the rule tables, the renderer, the two API calls
equation_to_speech.ipynb    the walk-through; the speech cells are marked and need a key
requirements.txt            sarvamai and python-dotenv; the core itself is standard library
.env.example                copy to .env and put your key in it
sample_data/                nothing to download; the inputs are twelve short strings
outputs/                    where a .wav lands if you run the speech cell
```

## Running it

```bash
cp .env.example .env        # then edit .env and add your key
pip install -r requirements.txt
jupyter notebook equation_to_speech.ipynb
```

The first two thirds of the notebook need no key, no network and not even `sarvamai`
installed. Only the two speech cells at the end do, and they say so.

Using the module on its own:

```python
from equation_speech import verbalise, speak

sentence = verbalise("(a+b)^2", "hi-IN")
audio = speak(sentence, "hi-IN", api_key)      # needs a key
```

The API key is passed explicitly on every call. The client's own default is read once, when
the SDK is imported, so setting the environment variable afterwards is already too late and
you get an `ApiError` that looks like a missing key.

## Open questions

Honest gaps, all of them because there was no key here.

- Whether `bulbul:v3` voices कोष्ठक and கூட்டல் clearly enough to be understood at speed.
- Whether a Latin `x` inside a Devanagari sentence sounds right, or whether `variable_words`
  should be filled in by default.
- Whether the comma in the SOV comparison form produces a useful pause or is ignored.
- Whether a native speaker would keep these fraction and calculus words. Tamil and Telugu
  fraction words vary regionally, and Hindi genitive agreement is the likeliest error.
