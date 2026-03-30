# Pretext Integration Snippets

Copy-paste-ready TypeScript snippets for `@chenglou/pretext`.

```bash
npm install @chenglou/pretext
```

---

## 1. React Virtualized List — Variable Height Rows

Uses `react-window` with Pretext to calculate row heights without rendering.

```tsx
// VirtualizedTextList.tsx
import React, { useRef, useEffect, useMemo, useCallback } from "react";
import { VariableSizeList as List } from "react-window";
import { prepare, layout, type PreparedText } from "@chenglou/pretext";

interface TextItem {
  id: string;
  text: string;
}

interface VirtualizedTextListProps {
  items: TextItem[];
  width: number;
  height: number;
  font: string; // Canvas font string, e.g. "16px Inter, sans-serif"
  lineHeight: number; // in px, e.g. 22.4
  padding: number; // horizontal padding inside each row
}

export function VirtualizedTextList({
  items,
  width,
  height,
  font,
  lineHeight,
  padding,
}: VirtualizedTextListProps) {
  const listRef = useRef<List>(null);

  // Prepare all text items once (expensive step — done upfront)
  const prepared = useMemo<PreparedText[]>(
    () => items.map((item) => prepare(item.text, font)),
    [items, font]
  );

  // Compute row height using Pretext layout (cheap per call)
  const contentWidth = width - padding * 2;
  const getItemSize = useCallback(
    (index: number): number => {
      const result = layout(prepared[index], contentWidth, lineHeight);
      // Add vertical padding (12px top + 12px bottom)
      return result.height + 24;
    },
    [prepared, contentWidth, lineHeight]
  );

  // Reset cached sizes when width changes (triggers re-measure)
  useEffect(() => {
    listRef.current?.resetAfterIndex(0);
  }, [width]);

  const Row = ({
    index,
    style,
  }: {
    index: number;
    style: React.CSSProperties;
  }) => (
    <div
      style={{
        ...style,
        padding: `12px ${padding}px`,
        boxSizing: "border-box",
        borderBottom: "1px solid #eee",
      }}
    >
      <p style={{ margin: 0, font, lineHeight: `${lineHeight}px` }}>
        {items[index].text}
      </p>
    </div>
  );

  return (
    <List
      ref={listRef}
      height={height}
      width={width}
      itemCount={items.length}
      itemSize={getItemSize}
    >
      {Row}
    </List>
  );
}

// Usage:
// <VirtualizedTextList
//   items={[{ id: "1", text: "Long paragraph..." }, ...]}
//   width={600}
//   height={800}
//   font="16px Inter, sans-serif"
//   lineHeight={22.4}
//   padding={16}
// />
```

---

## 2. Canvas Text Renderer — Multiline with Line Breaking

Renders text on an HTML5 Canvas using Pretext for line-break positions.

```tsx
// CanvasTextRenderer.tsx
import React, { useRef, useEffect } from "react";
import {
  prepareWithSegments,
  layoutWithLines,
  type PreparedTextWithSegments,
  type LayoutLine,
} from "@chenglou/pretext";

interface CanvasTextRendererProps {
  text: string;
  fontFamily: string; // e.g. "Inter"
  fontSize: number; // e.g. 16
  lineHeight: number; // e.g. 24
  width: number;
  color?: string;
  backgroundColor?: string;
}

// Load a web font and resolve when it's ready for Canvas use.
async function loadFont(family: string, url: string): Promise<void> {
  const face = new FontFace(family, `url(${url})`);
  const loaded = await face.load();
  document.fonts.add(loaded);
  await document.fonts.ready;
}

export function CanvasTextRenderer({
  text,
  fontFamily,
  fontSize,
  lineHeight,
  width,
  color = "#000",
  backgroundColor = "#fff",
}: CanvasTextRendererProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const fontStr = `${fontSize}px ${fontFamily}`;

    // prepareWithSegments (not prepare) — needed for layoutWithLines
    const prepared: PreparedTextWithSegments = prepareWithSegments(text, fontStr);

    // layoutWithLines returns line objects with .text for each line
    const result = layoutWithLines(prepared, width, lineHeight);

    const canvasHeight = result.height;

    // Set canvas dimensions (accounting for device pixel ratio)
    canvas.width = width * dpr;
    canvas.height = canvasHeight * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${canvasHeight}px`;
    ctx.scale(dpr, dpr);

    // Clear and fill background
    ctx.fillStyle = backgroundColor;
    ctx.fillRect(0, 0, width, canvasHeight);

    // Draw text line by line
    ctx.fillStyle = color;
    ctx.font = fontStr;
    ctx.textBaseline = "top";

    result.lines.forEach((line: LayoutLine, i: number) => {
      const y = i * lineHeight;
      ctx.fillText(line.text.trimEnd(), 0, y);
    });
  }, [text, fontFamily, fontSize, lineHeight, width, color, backgroundColor]);

  return <canvas ref={canvasRef} />;
}

// Usage:
// First load the font, then render:
//
// await loadFont("Inter", "/fonts/Inter-Regular.woff2");
//
// <CanvasTextRenderer
//   text="Your long text goes here..."
//   fontFamily="Inter"
//   fontSize={16}
//   lineHeight={24}
//   width={600}
// />
```

---

## 3. Responsive Card Grid — Dynamic Heights per Breakpoint

CSS Grid where card heights are pre-calculated at each breakpoint using Pretext.

```tsx
// ResponsiveCardGrid.tsx
import React, { useState, useEffect, useMemo } from "react";
import { prepare, layout, type PreparedText } from "@chenglou/pretext";

interface Card {
  id: string;
  title: string;
  body: string;
}

interface Breakpoint {
  name: string;
  minWidth: number;
  columns: number;
  cardPadding: number; // horizontal padding inside each card
  gridGap: number;
}

const BREAKPOINTS: Breakpoint[] = [
  { name: "mobile", minWidth: 0, columns: 1, cardPadding: 12, gridGap: 12 },
  { name: "tablet", minWidth: 640, columns: 2, cardPadding: 16, gridGap: 16 },
  { name: "desktop", minWidth: 1024, columns: 3, cardPadding: 20, gridGap: 20 },
];

const TITLE_FONT = "bold 18px Inter, sans-serif";
const BODY_FONT = "14px Inter, sans-serif"; // no /lineHeight — canvas doesn't support it
const TITLE_LINE_HEIGHT = 24;
const BODY_LINE_HEIGHT = 21;

function getBreakpoint(viewportWidth: number): Breakpoint {
  // Walk backwards to find the largest matching breakpoint
  for (let i = BREAKPOINTS.length - 1; i >= 0; i--) {
    if (viewportWidth >= BREAKPOINTS[i].minWidth) return BREAKPOINTS[i];
  }
  return BREAKPOINTS[0];
}

function calculateCardHeight(
  card: Card,
  contentWidth: number,
  titlePrepared: PreparedText,
  bodyPrepared: PreparedText
): number {
  const titleLayout = layout(titlePrepared, contentWidth, TITLE_LINE_HEIGHT);
  const bodyLayout = layout(bodyPrepared, contentWidth, BODY_LINE_HEIGHT);
  // title + 8px gap + body + 24px vertical padding (12 top + 12 bottom)
  return titleLayout.height + 8 + bodyLayout.height + 24;
}

export function ResponsiveCardGrid({ cards }: { cards: Card[] }) {
  const [viewportWidth, setViewportWidth] = useState(window.innerWidth);

  useEffect(() => {
    const onResize = () => setViewportWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // Prepare text once (expensive — memoized)
  const preparedCards = useMemo(
    () =>
      cards.map((card) => ({
        title: prepare(card.title, TITLE_FONT),
        body: prepare(card.body, BODY_FONT),
      })),
    [cards]
  );

  const bp = getBreakpoint(viewportWidth);

  // Calculate content width per card for this breakpoint
  const totalGaps = (bp.columns - 1) * bp.gridGap;
  const cardWidth = (viewportWidth - totalGaps - 32) / bp.columns; // 32 = page margin
  const contentWidth = cardWidth - bp.cardPadding * 2;

  // Pre-calculate heights (cheap layout calls)
  const cardHeights = cards.map((card, i) =>
    calculateCardHeight(card, contentWidth, preparedCards[i].title, preparedCards[i].body)
  );

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${bp.columns}, 1fr)`,
        gap: `${bp.gridGap}px`,
        padding: "16px",
      }}
    >
      {cards.map((card, i) => (
        <div
          key={card.id}
          style={{
            height: `${cardHeights[i]}px`,
            padding: `12px ${bp.cardPadding}px`,
            border: "1px solid #ddd",
            borderRadius: 8,
            overflow: "hidden",
            boxSizing: "border-box",
          }}
        >
          <h3
            style={{
              margin: "0 0 8px 0",
              font: TITLE_FONT,
              lineHeight: `${TITLE_LINE_HEIGHT}px`,
            }}
          >
            {card.title}
          </h3>
          <p
            style={{
              margin: 0,
              font: BODY_FONT,
              lineHeight: `${BODY_LINE_HEIGHT}px`,
            }}
          >
            {card.body}
          </p>
        </div>
      ))}
    </div>
  );
}

// Usage:
// const cards = [
//   { id: "1", title: "Card Title", body: "Long body text..." },
//   ...
// ];
// <ResponsiveCardGrid cards={cards} />
```

---

## 4. Overflow Detector — Will Text Fit?

Utility that checks if text overflows a container at a given font/size/width/maxHeight.

```tsx
// overflowDetector.ts
import { prepare, layout } from "@chenglou/pretext";

interface OverflowResult {
  overflows: boolean;
  lineCount: number;
  height: number; // total rendered height in px
  excessHeight: number; // how many px past maxHeight (0 if fits)
}

/**
 * Check if text will overflow a container WITHOUT rendering it.
 *
 * @param text       - The text content to measure
 * @param font       - Canvas font string, e.g. "14px Inter, sans-serif"
 * @param width      - Available container width in px
 * @param lineHeight - Line height in px
 * @param maxHeight  - Maximum container height in px
 * @returns          - Overflow analysis
 */
export function detectOverflow(
  text: string,
  font: string,
  width: number,
  lineHeight: number,
  maxHeight: number
): OverflowResult {
  const prepared = prepare(text, font);
  const result = layout(prepared, width, lineHeight);

  const overflows = result.height > maxHeight;

  return {
    overflows,
    lineCount: result.lineCount,
    height: result.height,
    excessHeight: overflows ? result.height - maxHeight : 0,
  };
}

/**
 * Batch-check overflow for multiple text items with a shared font.
 * Useful for validating a list of items against a uniform container size.
 *
 * @param items      - Array of { id, text } to check
 * @param font       - CSS font shorthand
 * @param width      - Container width in px
 * @param lineHeight - Line height in px
 * @param maxHeight  - Max container height in px
 * @returns          - Map of id -> OverflowResult
 */
export function batchDetectOverflow(
  items: { id: string; text: string }[],
  font: string,
  width: number,
  lineHeight: number,
  maxHeight: number
): Map<string, OverflowResult> {
  const results = new Map<string, OverflowResult>();

  for (const item of items) {
    results.set(item.id, detectOverflow(item.text, font, width, lineHeight, maxHeight));
  }

  return results;
}

// --- Example usage ---

// Single check
// const result = detectOverflow(
//   "Some potentially long text...",
//   "14px Inter, sans-serif",
//   300,  // container width
//   21,   // line height
//   63    // max height (3 lines)
// );
// console.log(result);
// => { overflows: true, lineCount: 5, height: 105, excessHeight: 42 }

// Batch check (e.g. validating a card grid)
// const results = batchDetectOverflow(
//   [
//     { id: "card-1", text: "Short text" },
//     { id: "card-2", text: "Very long text that will definitely wrap..." },
//   ],
//   "14px Inter, sans-serif",
//   300,
//   21,
//   63
// );
// for (const [id, r] of results) {
//   if (r.overflows) console.warn(`${id} overflows by ${r.excessHeight}px`);
// }
```

---

## 5. Masonry Layout — Pretext-Predicted Heights

Variable-height masonry where item heights are known before any DOM paint.

```tsx
// MasonryLayout.tsx
import React, { useState, useEffect, useMemo } from "react";
import { prepare, layout, type PreparedText } from "@chenglou/pretext";

interface MasonryItem {
  id: string;
  title: string;
  body: string;
  imageHeight?: number; // optional image above the text
}

interface PositionedItem {
  item: MasonryItem;
  x: number;
  y: number;
  width: number;
  height: number;
}

const TITLE_FONT = "bold 16px Inter, sans-serif";
const BODY_FONT = "14px Inter, sans-serif"; // no /lineHeight — canvas doesn't support it
const TITLE_LH = 22;
const BODY_LH = 21;
const CARD_PADDING = 16;
const GAP = 12;

/**
 * Predict the pixel height of a masonry card using Pretext.
 * No DOM needed — pure calculation.
 */
function predictCardHeight(
  item: MasonryItem,
  titlePrepared: PreparedText,
  bodyPrepared: PreparedText,
  contentWidth: number
): number {
  const titleResult = layout(titlePrepared, contentWidth, TITLE_LH);
  const bodyResult = layout(bodyPrepared, contentWidth, BODY_LH);

  let height = CARD_PADDING; // top padding
  if (item.imageHeight) height += item.imageHeight + 12; // image + gap
  height += titleResult.height; // title
  height += 8; // gap between title and body
  height += bodyResult.height; // body
  height += CARD_PADDING; // bottom padding

  return Math.ceil(height);
}

/**
 * Place items into columns, always adding to the shortest column.
 * All heights are pre-calculated via Pretext (zero layout thrash).
 */
function computeMasonryPositions(
  items: MasonryItem[],
  preparedItems: { title: PreparedText; body: PreparedText }[],
  containerWidth: number,
  columns: number
): { positions: PositionedItem[]; totalHeight: number } {
  const colWidth = (containerWidth - GAP * (columns - 1)) / columns;
  const contentWidth = colWidth - CARD_PADDING * 2;

  // Track the bottom edge of each column
  const colHeights = new Array(columns).fill(0);
  const positions: PositionedItem[] = [];

  for (let i = 0; i < items.length; i++) {
    // Find the shortest column
    const col = colHeights.indexOf(Math.min(...colHeights));

    const cardHeight = predictCardHeight(
      items[i],
      preparedItems[i].title,
      preparedItems[i].body,
      contentWidth
    );

    positions.push({
      item: items[i],
      x: col * (colWidth + GAP),
      y: colHeights[col],
      width: colWidth,
      height: cardHeight,
    });

    colHeights[col] += cardHeight + GAP;
  }

  return {
    positions,
    totalHeight: Math.max(...colHeights),
  };
}

export function MasonryLayout({
  items,
  columns = 3,
}: {
  items: MasonryItem[];
  columns?: number;
}) {
  const [containerWidth, setContainerWidth] = useState(0);
  const containerRef = React.useRef<HTMLDivElement>(null);

  // Observe container width
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver(([entry]) => {
      setContainerWidth(entry.contentRect.width);
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Prepare text once (expensive)
  const preparedItems = useMemo(
    () =>
      items.map((item) => ({
        title: prepare(item.title, TITLE_FONT),
        body: prepare(item.body, BODY_FONT),
      })),
    [items]
  );

  // Compute positions (cheap — runs on resize)
  const { positions, totalHeight } = useMemo(() => {
    if (containerWidth === 0) return { positions: [], totalHeight: 0 };
    return computeMasonryPositions(items, preparedItems, containerWidth, columns);
  }, [items, preparedItems, containerWidth, columns]);

  return (
    <div ref={containerRef} style={{ position: "relative", width: "100%" }}>
      <div style={{ height: totalHeight, position: "relative" }}>
        {positions.map((pos) => (
          <div
            key={pos.item.id}
            style={{
              position: "absolute",
              left: pos.x,
              top: pos.y,
              width: pos.width,
              height: pos.height,
              padding: CARD_PADDING,
              boxSizing: "border-box",
              border: "1px solid #e0e0e0",
              borderRadius: 8,
              background: "#fff",
            }}
          >
            {pos.item.imageHeight && (
              <div
                style={{
                  height: pos.item.imageHeight,
                  background: "#f0f0f0",
                  borderRadius: 4,
                  marginBottom: 12,
                }}
              />
            )}
            <h4
              style={{
                margin: "0 0 8px 0",
                font: TITLE_FONT,
                lineHeight: `${TITLE_LH}px`,
              }}
            >
              {pos.item.title}
            </h4>
            <p
              style={{
                margin: 0,
                font: BODY_FONT,
                lineHeight: `${BODY_LH}px`,
              }}
            >
              {pos.item.body}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

// Usage:
// <MasonryLayout
//   columns={3}
//   items={[
//     { id: "1", title: "Post Title", body: "Content...", imageHeight: 200 },
//     { id: "2", title: "Another", body: "More content..." },
//     ...
//   ]}
// />
```

---

## 6. Multilingual Text Validator

Tests text measurement across multiple Unicode scripts. Catches layout bugs that only appear with non-Latin text.

```tsx
// multilingualValidator.ts
import { prepare, layout, setLocale } from "@chenglou/pretext";

/** A script test case */
interface ScriptTestCase {
  script: string;
  locale: string;
  sample: string;
  description: string;
}

/** Result for a single script test */
interface ScriptTestResult {
  script: string;
  locale: string;
  pass: boolean;
  lineCount: number;
  height: number;
  error?: string;
}

/** Aggregate validation report */
interface ValidationReport {
  allPassed: boolean;
  results: ScriptTestResult[];
  failures: ScriptTestResult[];
}

// Representative samples for each script.
// These are chosen to exercise word-breaking, BiDi, combining marks, and segmentation.
const SCRIPT_TESTS: ScriptTestCase[] = [
  {
    script: "Latin",
    locale: "en",
    sample:
      "The quick brown fox jumps over the lazy dog. Typography involves careful attention to spacing, kerning, and line breaking across variable-width containers.",
    description: "Basic Latin with long words and punctuation",
  },
  {
    script: "CJK (Chinese)",
    locale: "zh",
    sample:
      "\u6392\u7248\u5f15\u64ce\u9700\u8981\u6b63\u786e\u5904\u7406\u4e2d\u6587\u6587\u672c\u7684\u6362\u884c\u3002\u4e2d\u6587\u6ca1\u6709\u7a7a\u683c\u5206\u9694\u8bcd\u8bed\uff0c\u56e0\u6b64\u6362\u884c\u89c4\u5219\u4e0e\u82f1\u6587\u4e0d\u540c\u3002\u6bcf\u4e2a\u5b57\u7b26\u90fd\u53ef\u4ee5\u4f5c\u4e3a\u6362\u884c\u70b9\u3002",
    description: "CJK characters with no word-space boundaries",
  },
  {
    script: "CJK (Japanese)",
    locale: "ja",
    sample:
      "\u30c6\u30ad\u30b9\u30c8\u306e\u30ec\u30a4\u30a2\u30a6\u30c8\u306f\u3001\u65e5\u672c\u8a9e\u306e\u6587\u5b57\u4f53\u7cfb\u306b\u304a\u3044\u3066\u7279\u6b8a\u306a\u8003\u616e\u304c\u5fc5\u8981\u3067\u3059\u3002\u3072\u3089\u304c\u306a\u3001\u30ab\u30bf\u30ab\u30ca\u3001\u6f22\u5b57\u304c\u6df7\u5728\u3057\u307e\u3059\u3002",
    description: "Japanese mixed scripts (hiragana, katakana, kanji)",
  },
  {
    script: "Arabic (RTL)",
    locale: "ar",
    sample:
      "\u0627\u0644\u0646\u0635 \u0627\u0644\u0639\u0631\u0628\u064a \u064a\u064f\u0643\u062a\u0628 \u0645\u0646 \u0627\u0644\u064a\u0645\u064a\u0646 \u0625\u0644\u0649 \u0627\u0644\u064a\u0633\u0627\u0631. \u064a\u062c\u0628 \u0623\u0646 \u064a\u062a\u0639\u0627\u0645\u0644 \u0645\u062d\u0631\u0643 \u0627\u0644\u062a\u062e\u0637\u064a\u0637 \u0645\u0639 \u0627\u0644\u062d\u0631\u0648\u0641 \u0627\u0644\u0645\u062a\u0635\u0644\u0629 \u0648\u0627\u0644\u062a\u0634\u0643\u064a\u0644.",
    description: "RTL with connected letters and diacritical marks (tashkeel)",
  },
  {
    script: "Thai",
    locale: "th",
    sample:
      "\u0e20\u0e32\u0e29\u0e32\u0e44\u0e17\u0e22\u0e44\u0e21\u0e48\u0e21\u0e35\u0e0a\u0e48\u0e2d\u0e07\u0e27\u0e48\u0e32\u0e07\u0e23\u0e30\u0e2b\u0e27\u0e48\u0e32\u0e07\u0e04\u0e33 \u0e01\u0e32\u0e23\u0e15\u0e31\u0e14\u0e04\u0e33\u0e15\u0e49\u0e2d\u0e07\u0e43\u0e0a\u0e49\u0e01\u0e32\u0e23\u0e27\u0e34\u0e40\u0e04\u0e23\u0e32\u0e30\u0e2b\u0e4c\u0e17\u0e32\u0e07\u0e20\u0e32\u0e29\u0e32\u0e28\u0e32\u0e2a\u0e15\u0e23\u0e4c\u0e40\u0e1e\u0e37\u0e48\u0e2d\u0e2b\u0e32\u0e08\u0e38\u0e14\u0e15\u0e31\u0e14\u0e04\u0e33\u0e17\u0e35\u0e48\u0e40\u0e2b\u0e21\u0e32\u0e30\u0e2a\u0e21",
    description: "Thai with no spaces between words (requires segmenter)",
  },
  {
    script: "Emoji + Mixed",
    locale: "en",
    sample:
      "Performance test \ud83d\ude80\ud83d\udcca with emoji sequences: \ud83d\udc68\u200d\ud83d\udc69\u200d\ud83d\udc67\u200d\ud83d\udc66 family, \ud83c\udff3\ufe0f\u200d\ud83c\udf08 flag, and \ud83e\uddd1\ud83c\udffd\u200d\ud83d\udcbb technologist. Plus numbers: 42 \u00d7 \u03c0 \u2248 131.95",
    description: "Emoji with ZWJ sequences, modifiers, and mixed scripts",
  },
];

/**
 * Validate text layout across multiple scripts.
 *
 * Tests that Pretext can measure text in each script without errors
 * and produces reasonable results (height > 0, lineCount > 0).
 *
 * @param font       - CSS font shorthand (must support all tested scripts)
 * @param width      - Container width in px
 * @param lineHeight - Line height in px
 * @returns          - Validation report with pass/fail per script
 */
export function validateMultilingualLayout(
  font: string,
  width: number,
  lineHeight: number
): ValidationReport {
  const results: ScriptTestResult[] = [];

  for (const test of SCRIPT_TESTS) {
    try {
      // Set locale for proper segmentation (important for Thai, CJK)
      setLocale(test.locale);

      const prepared = prepare(test.sample, font);
      const result = layout(prepared, width, lineHeight);

      // Sanity checks:
      // 1. Must produce at least 1 line
      // 2. Height must be positive
      // 3. Height must equal lineCount * lineHeight (consistency check)
      const heightConsistent =
        Math.abs(result.height - result.lineCount * lineHeight) < 1;

      const pass =
        result.lineCount > 0 && result.height > 0 && heightConsistent;

      results.push({
        script: test.script,
        locale: test.locale,
        pass,
        lineCount: result.lineCount,
        height: result.height,
        error: pass
          ? undefined
          : `Sanity failed: lines=${result.lineCount}, height=${result.height}, consistent=${heightConsistent}`,
      });
    } catch (err) {
      results.push({
        script: test.script,
        locale: test.locale,
        pass: false,
        lineCount: 0,
        height: 0,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  }

  // Reset locale to default.
  // WARNING: setLocale() calls clearCache() internally — all previously
  // prepared text becomes stale. Re-prepare after calling this.
  setLocale("en");

  const failures = results.filter((r) => !r.pass);

  return {
    allPassed: failures.length === 0,
    results,
    failures,
  };
}

/**
 * Pretty-print the validation report to console.
 */
export function printValidationReport(report: ValidationReport): void {
  console.log("\n=== Multilingual Text Layout Validation ===\n");

  for (const r of report.results) {
    const status = r.pass ? "PASS" : "FAIL";
    const icon = r.pass ? "[OK]" : "[!!]";
    console.log(
      `${icon} ${status}  ${r.script} (${r.locale}) — ${r.lineCount} lines, ${r.height}px`
    );
    if (r.error) console.log(`         Error: ${r.error}`);
  }

  console.log(
    `\nResult: ${report.results.length - report.failures.length}/${report.results.length} passed`
  );
  if (!report.allPassed) {
    console.log("Failed scripts:", report.failures.map((f) => f.script).join(", "));
  }
}

// Usage:
// const report = validateMultilingualLayout(
//   "16px 'Noto Sans', sans-serif",  // use a font that covers all scripts
//   400,
//   24
// );
// printValidationReport(report);
//
// // Or in a test runner:
// import { expect, test } from "vitest";
// test("text layout handles all scripts", () => {
//   const report = validateMultilingualLayout("16px sans-serif", 400, 24);
//   expect(report.allPassed).toBe(true);
// });
```
