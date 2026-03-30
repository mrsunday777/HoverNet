# Text Quality Gate

Checklist for any web component that renders text. Copy this into your completion proof and check off each item.

---

## Must Pass (Blocking)

These are hard failures. If any of these fail, the component is not shippable.

- [ ] **No overflow at 320px viewport** -- Set viewport to 320px wide. No text escapes its container. No horizontal scrollbar appears. Test with the longest string the component will realistically receive.
- [ ] **Long unbroken words don't break layout** -- Paste a 50+ character unbroken string (e.g. `Pneumonoultramicroscopicsilicovolcanoconiosis_and_then_some_more_text_appended`) into every text field. Layout must not break. The word should wrap or truncate, not push siblings offscreen.
- [ ] **Empty string / null text doesn't crash** -- Pass `""`, `null`, and `undefined` as text input. Component renders without error. No blank white box, no NaN, no "undefined" literal displayed.
- [ ] **Font fallback chain specified** -- Every `font-family` declaration includes at least two named fonts plus a generic family. Example: `font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif`. Never a bare single font.

---

## Should Pass (Warning)

These won't block merge but will be flagged in review. Fix them before calling the component "done."

- [ ] **Line length 50-75 characters** -- At 768px and 1440px viewport widths, measure the character count per line of body text. Optimal reading range is 50-75 characters. Narrower is acceptable for UI labels; wider is a readability problem.
- [ ] **Readable at 200% zoom** -- Browser zoom to 200%. Text reflows. Nothing is clipped. No overlapping elements. Interactive targets remain tappable.
- [ ] **RTL text renders correctly** -- Test with Arabic: `مرحبا بالعالم`. Text should flow right-to-left. Punctuation should appear on the correct side. If the component uses directional CSS (margins, padding, text-align), verify `dir="rtl"` or logical properties (`margin-inline-start`) work.
- [ ] **CJK text wraps correctly** -- Test with: `これは日本語のテストです`. Characters should wrap at container edge, not mid-glyph. Line-breaking should follow CJK rules (no break before certain punctuation). Verify `word-break: normal` or `word-break: break-all` is intentional.
- [ ] **Emoji doesn't break layout** -- Test with: `Hello 👋🏽 World 🌍`. Emoji should render inline with text. Skin-tone modifiers (👋🏽) should render as a single glyph, not two. Line height should accommodate emoji without clipping.
- [ ] **`overflow-wrap: break-word` set on text containers** -- Any container that receives dynamic or user-generated text should have `overflow-wrap: break-word` (or the equivalent `word-wrap: break-word`). This prevents long URLs and token strings from overflowing.
- [ ] **`white-space` property is intentional** -- If any text element uses `white-space: nowrap`, `pre`, or `pre-wrap`, confirm it is deliberate. Default (`normal`) is correct for most body text. `nowrap` on a dynamic string is almost always a bug.

---

## Nice to Have (Info)

Not required for merge. Track as follow-up if relevant.

- [ ] **Pretext validation passes** -- If the component uses dynamic text that changes size or content at runtime, run it through Pretext validation. This catches overflow and truncation issues that static tests miss.
- [ ] **Text truncation has ellipsis treatment** -- If text is truncated, it uses `text-overflow: ellipsis` (single line) or `-webkit-line-clamp` (multi-line). Raw clipping without visual indicator is a UX failure.
- [ ] **Multi-line clamping uses `-webkit-line-clamp` or Pretext** -- For "show 3 lines then cut off" patterns, use the standard approach: `display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;`. Or use Pretext's layout engine for more control.

---

## How to Use This

1. Copy this checklist into your build completion proof.
2. Check off each item as you verify it.
3. For any "Must Pass" failure, fix before requesting review.
4. For "Should Pass" warnings, note the reason if you're intentionally skipping (e.g., "RTL not applicable -- English-only marketing page").
5. Include test viewport widths used: `320px`, `768px`, `1440px` minimum.

### Quick Test Commands

```bash
# Resize browser to 320px width
# Chrome DevTools: Cmd+Shift+M -> set width to 320

# Test with long unbroken string
# Paste into any text input: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

# Test with empty/null
# In console: element.textContent = ""
# In console: element.textContent = null

# Test with RTL
# In console: element.textContent = "مرحبا بالعالم"

# Test with emoji
# In console: element.textContent = "Hello 👋🏽 World 🌍 Test 🇯🇵"
```
