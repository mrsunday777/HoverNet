# Text Test Corpus

Strings for testing web components that render text. Adapted from Pretext's `test-data.ts` and extended with real-world edge cases.

Each entry: **string**, script/language, what it tests, expected behavior.

---

## Latin Strings

| # | String | Language | Tests | Expected |
|---|--------|----------|-------|----------|
| L1 | `OK` | English | Minimum viable text. Two characters. | Renders without excess whitespace. Container doesn't collapse. |
| L2 | `The quick brown fox jumps over the lazy dog.` | English | Standard sentence, all lowercase letters represented. ~45 chars. | Clean single-line rendering at wide viewports. Wraps naturally at narrow viewports. |
| L3 | `Pneumonoultramicroscopicsilicovolcanoconiosisandthenweappendsomemoretexttomakeit` | English | 80-char unbroken word. No hyphens, no spaces. | Must wrap or truncate. Must NOT overflow container. `overflow-wrap: break-word` should handle this. |
| L4 | `Invoice #INV-2026-03-28-00147 | Qty: 1,234.56 | Total: $98,765.43 (USD)` | English + numbers | Mixed alphanumeric with symbols, pipes, currency, decimals. | All characters render. Monospace alignment if in a table. Pipes don't trigger markdown rendering. |
| L5 | `Crème brûlée & "jalapeño" — it's naïve to skip diacritics…` | French/Spanish/English | Accented characters, curly quotes, em dash, ellipsis, ampersand. | All glyphs render correctly. No mojibake. Curly quotes don't become `â€œ`. |

---

## CJK Strings

| # | String | Language | Tests | Expected |
|---|--------|----------|-------|----------|
| C1 | `これは日本語のテストです。改行が正しく処理されることを確認します。` | Japanese | Hiragana + Katakana + Kanji + punctuation. ~28 chars but variable width. | Wraps at character boundaries (not mid-glyph). Japanese period `。` stays with preceding text. |
| C2 | `中文排版测试：这段文字用来验证中文文本在不同容器宽度下的换行和显示效果。` | Chinese (Simplified) | Chinese characters + Chinese punctuation (full-width colon). | Character-level wrapping. Full-width punctuation aligns correctly. No half-character rendering. |
| C3 | `한국어 테스트 문장입니다. 띄어쓰기와 줄바꿈이 올바르게 작동하는지 확인합니다.` | Korean | Hangul syllable blocks + spaces + Korean period. | Wraps at syllable boundaries. Spaces are respected. Line breaking follows Korean rules. |

---

## RTL Strings

| # | String | Language | Tests | Expected |
|---|--------|----------|-------|----------|
| R1 | `مرحبا بالعالم. هذا اختبار للنص العربي مع علامات الترقيم.` | Arabic | Pure RTL text with Arabic punctuation. | Text flows right-to-left. Period appears on left side of line. Ligatures render (letters connect). |
| R2 | `שלום עולם! זהו טקסט בדיקה בעברית עם מספרים: 12345 ותאריך 28/03/2026.` | Hebrew | RTL with embedded LTR numbers and date. Bidirectional text. | Hebrew flows RTL. Numbers `12345` and date `28/03/2026` render LTR within the RTL flow. No jumbled ordering. |
| R3 | `This is English مع بعض العربية mixed together in one sentence.` | Mixed LTR+RTL | Bidirectional text in a single line. The hardest rendering case. | English portions flow LTR. Arabic portions flow RTL. Word order is logical. No overlapping or reversed segments. |

---

## Thai Strings

| # | String | Language | Tests | Expected |
|---|--------|----------|-------|----------|
| T1 | `สวัสดีครับ นี่คือข้อความทดสอบภาษาไทย` | Thai | Thai script with spaces between phrases (but not between words within phrases). | Wraps at valid word boundaries (requires dictionary-based breaking or CSS `word-break`). No mid-syllable breaks. |
| T2 | `กรุงเทพมหานครเป็นเมืองหลวงของประเทศไทยมีประชากรมากกว่าสิบล้านคน` | Thai | Long unspaced Thai string (~60 chars, no spaces at all). | Browser's Thai line-breaking algorithm activates. If not available, wraps at container edge (acceptable fallback). Must not overflow. |
| T3 | `ราคา฿1,234.56บาทต่อหน่วยรวมภาษีมูลค่าเพิ่ม7%` | Thai + numbers | Thai with embedded numbers, currency symbol (฿), percentage. No spaces. | Numbers render inline. Thai baht symbol (฿) renders. Percentage sign doesn't detach from `7`. |

---

## Emoji Strings

| # | String | Language | Tests | Expected |
|---|--------|----------|-------|----------|
| E1 | `🔥` | Emoji | Single emoji, no text. Minimum emoji case. | Renders as one glyph. Container doesn't collapse to zero width. Correct vertical alignment. |
| E2 | `👨‍👩‍👧‍👦` | Emoji (ZWJ sequence) | Family emoji — 4 code points joined by zero-width joiners. | Renders as ONE glyph (family), not four separate people. `string.length` will be misleading (11 UTF-16 code units). Layout treats it as one character. |
| E3 | `👋🏽` | Emoji (skin tone) | Wave with medium skin tone. Two code points, one glyph. | Renders as single hand with correct skin tone. Does NOT render as hand + brown square. |
| E4 | `🇯🇵🇧🇷🇺🇸` | Emoji (flags) | Three flag sequences. Each flag = 2 regional indicator symbols. | Renders as three flag emojis. Does NOT render as six letter glyphs (JP, BR, US). |
| E5 | `Price is 🔥🔥🔥 right now! Up 📈 50% in 24h ⏰` | Mixed text + emoji | Emoji inline with English text, numbers, symbols. | Emoji renders inline. Line height accommodates emoji without clipping tops/bottoms. Text baseline stays consistent. |

---

## Edge Cases

| # | String | Language | Tests | Expected |
|---|--------|----------|-------|----------|
| X1 | `` (empty string) | None | Zero-length input. | Component renders. No crash, no "undefined", no "null" literal. Container may collapse to minimum height -- that's acceptable. |
| X2 | `A` | Latin | Single character. | Renders. Container doesn't have excessive width from padding/min-width fighting with content. |
| X3 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | Latin | 500-char unbroken string. Stress test for overflow-wrap. | MUST wrap. MUST NOT overflow. MUST NOT cause horizontal scrollbar. This is the canonical overflow test. |

---

## URL Strings

| # | String | Language | Tests | Expected |
|---|--------|----------|-------|----------|
| U1 | `https://www.example.com/very/long/path/that/keeps/going/and/going/until/it/exceeds/any/reasonable/container/width/especially/on/mobile/devices/at/320px?query=parameter&another=value&token=abc123def456ghi789` | URL | Long URL with path segments, query params. ~200 chars unbroken by spaces. | URL wraps within container. `overflow-wrap: break-word` or `word-break: break-all` activates. No horizontal overflow. |
| U2 | `Check out https://subdomain.example-site.co.uk/path?ref=123#section and let me know` | Mixed text + URL | URL embedded in sentence. | Text wraps normally. URL portion wraps if needed. Link remains visually identifiable if styled as `<a>`. |

---

## Code Strings

| # | String | Language | Tests | Expected |
|---|--------|----------|-------|----------|
| D1 | `` `const result = await fetch('/api/v2/tokens', { headers: { 'Authorization': `Bearer ${token}` } });` `` | JavaScript | Inline code with backticks, template literal, nested quotes. | Renders in monospace. Backticks visible. No markdown parsing artifacts. No syntax highlighting unless explicitly enabled. |
| D2 | `error: cannot find module '@vessel/core' in /Users/sunday/Vessel/Projects/HoverNet[TruthFiles]/[OPs]/node_modules` | Error message | Path with brackets, forward slashes, @ symbol. | All characters render literally. Brackets `[]` not interpreted as markdown links. `@` not interpreted as mention. |

---

## Usage

1. Pick the categories relevant to your component (at minimum: Latin + Edge Cases).
2. For each string, paste it into the component's text input.
3. Verify the "Expected" column holds true.
4. Screenshot failures and attach to your completion proof.
5. If a "Must Pass" string from `text_quality_gate.md` fails, the component is not shippable.

### Quick Copy Block

For rapid testing, here are the most critical strings to paste in sequence:

```
OK
The quick brown fox jumps over the lazy dog.
Pneumonoultramicroscopicsilicovolcanoconiosisandthenweappendsomemoretexttomakeit
مرحبا بالعالم
これは日本語のテストです。
👨‍👩‍👧‍👦
aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa

A
Hello 👋🏽 World 🌍
```
